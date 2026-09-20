"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { ArrowLeft, Download } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";

export default function RecordDetailPage() {
  const params = useParams();
  const router = useRouter();
  const recordId = params.id as string;
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const { data: record, isLoading } = useQuery({
    queryKey: ["record", recordId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/patients/records/${recordId}`);
      return res.data;
    },
  });

  // document_url stores the uploads object key; the file endpoint requires
  // auth, so download via axios blob instead of a plain <a href>.
  const handleDownload = async () => {
    if (!record?.document_url || downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const res = await api.get(`/api/v1/uploads/${record.document_url}`, {
        responseType: "blob",
      });
      const filename =
        record.document_url.split("/").pop() || `${record.title || "document"}`;
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("Failed to download the document. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: "Record Detail" },
        ]}
      />

      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-dreams-textSecondary hover:text-dreams-blue transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Timeline
      </button>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : record ? (
        <div className="bg-white rounded-lg shadow-card p-6 max-w-3xl">
          <div className="mb-4 flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${recordTypeColor(record.record_type)}`}
            >
              {recordTypeLabel(record.record_type)}
            </span>
            <span className="text-sm text-dreams-textSecondary">
              {formatDate(record.created_at)}
            </span>
          </div>

          <h1 className="mb-2 text-xl font-bold text-dreams-textPrimary">{record.title}</h1>

          {record.description && (
            <div className="mb-6">
              <h2 className="mb-1 text-sm font-medium text-dreams-textSecondary uppercase tracking-wide">
                Description
              </h2>
              <p className="text-dreams-textPrimary">{record.description}</p>
            </div>
          )}

          {record.document_url && (
            <div className="mb-6">
              <h2 className="mb-2 text-sm font-medium text-dreams-textSecondary uppercase tracking-wide">
                Attached Document
              </h2>
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                className="inline-flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                <Download className="h-4 w-4" />
                {downloading ? "Downloading…" : "Download Document"}
              </button>
              {downloadError && (
                <p className="mt-2 text-sm text-red-600">{downloadError}</p>
              )}
            </div>
          )}

          <div className="border-t border-dreams-border pt-4 text-xs text-dreams-textSecondary">
            <p>Record ID: {record.id}</p>
            <p>Source: {record.source}</p>
            <p>Last updated: {formatDate(record.updated_at)}</p>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-dreams-textSecondary">Record not found.</p>
        </div>
      )}
    </div>
  );
}

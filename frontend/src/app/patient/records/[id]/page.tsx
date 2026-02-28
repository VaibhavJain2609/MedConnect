"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";

export default function RecordDetailPage() {
  const params = useParams();
  const router = useRouter();
  const recordId = params.id as string;

  const { data: record, isLoading } = useQuery({
    queryKey: ["record", recordId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/patients/records/${recordId}`);
      return res.data;
    },
  });

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

          {record.fhir_bundle && (
            <div className="mb-6">
              <h2 className="mb-2 text-sm font-medium text-dreams-textSecondary uppercase tracking-wide">
                FHIR R4 Bundle
              </h2>
              <pre className="max-h-96 overflow-auto rounded-lg bg-dreams-lightBg border border-dreams-border p-4 text-xs text-dreams-textPrimary">
                {JSON.stringify(record.fhir_bundle, null, 2)}
              </pre>
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

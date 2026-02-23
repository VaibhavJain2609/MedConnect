"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";

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
    <AuthGuard requiredRole="patient">
      <Navbar />
      <main className="mx-auto max-w-3xl px-4 py-6">
        <button
          onClick={() => router.back()}
          className="mb-4 flex items-center gap-1 text-sm text-gray-600 hover:text-primary-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Timeline
        </button>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : record ? (
          <div className="rounded-xl border bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${recordTypeColor(record.record_type)}`}
              >
                {recordTypeLabel(record.record_type)}
              </span>
              <span className="text-sm text-gray-500">
                {formatDate(record.created_at)}
              </span>
            </div>

            <h1 className="mb-2 text-xl font-bold text-gray-900">{record.title}</h1>

            {record.description && (
              <div className="mb-6">
                <h2 className="mb-1 text-sm font-medium text-gray-500">Description</h2>
                <p className="text-gray-700">{record.description}</p>
              </div>
            )}

            {record.fhir_bundle && (
              <div className="mb-6">
                <h2 className="mb-2 text-sm font-medium text-gray-500">
                  FHIR R4 Bundle
                </h2>
                <pre className="max-h-96 overflow-auto rounded-lg bg-gray-50 p-4 text-xs text-gray-700">
                  {JSON.stringify(record.fhir_bundle, null, 2)}
                </pre>
              </div>
            )}

            <div className="border-t pt-4 text-xs text-gray-400">
              <p>Record ID: {record.id}</p>
              <p>Source: {record.source}</p>
              <p>Last updated: {formatDate(record.updated_at)}</p>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border bg-white p-12 text-center">
            <p className="text-gray-500">Record not found.</p>
          </div>
        )}
      </main>
    </AuthGuard>
  );
}

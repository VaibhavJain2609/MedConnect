"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ClipboardList, Loader2 } from "lucide-react";
import { getMyLabOrders, type LabOrder } from "@/lib/api/lab-orders";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<LabOrder["status"], string> = {
  ordered: "bg-amber-100 text-amber-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-600",
};

function formatDate(iso: string | null | undefined) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * "Lab Orders" panel for the patient lab-results page — read-only list of
 * tests doctors have ordered for the patient.
 */
export function PatientLabOrdersList() {
  const t = useTranslations("labOrders");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["patient-lab-orders"],
    queryFn: getMyLabOrders,
  });

  const orders = data?.data ?? [];

  return (
    <section className="bg-white rounded-lg shadow-card border border-dreams-border p-4">
      <div className="mb-3 flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-dreams-textSecondary" />
        <h2 className="text-base font-semibold text-dreams-textPrimary">
          {t("patientTitle")}
        </h2>
      </div>
      {isLoading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin text-dreams-blue" />
        </div>
      ) : isError ? (
        <p className="text-sm text-red-600">{t("loadFailed")}</p>
      ) : orders.length === 0 ? (
        <p className="text-sm text-dreams-textSecondary">{t("emptyPatient")}</p>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <div
              key={order.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-dreams-border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-dreams-textPrimary">
                  {order.test_name}
                </p>
                <p className="mt-0.5 text-xs text-dreams-textSecondary">
                  {formatDate(order.created_at)}
                  {order.doctor_name ? ` · Dr. ${order.doctor_name}` : ""}
                  {order.notes ? ` · ${order.notes}` : ""}
                </p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                  STATUS_STYLES[order.status]
                )}
              >
                {t(`status.${order.status}`)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

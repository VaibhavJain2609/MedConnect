"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { FlaskConical, Plus, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  createLabOrder,
  getDoctorLabOrders,
  updateLabOrderStatus,
  type LabOrder,
} from "@/lib/api/lab-orders";

const STATUS_BADGE: Record<LabOrder["status"], "pending" | "completed" | "cancelled"> = {
  ordered: "pending",
  completed: "completed",
  cancelled: "cancelled",
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * "Lab Orders" panel for the doctor patient page — order form plus the
 * doctor's orders for this patient with status badges and transitions.
 */
export function LabOrdersSection({ patientId }: { patientId: string }) {
  const t = useTranslations("labOrders");
  const queryClient = useQueryClient();
  const [testName, setTestName] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["lab-orders", patientId],
    queryFn: () => getDoctorLabOrders({ patient_id: patientId }),
    enabled: !!patientId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["lab-orders", patientId] });

  const createMutation = useMutation({
    mutationFn: () =>
      createLabOrder({
        patient_id: patientId,
        test_name: testName.trim(),
        notes: notes.trim() || undefined,
      }),
    onSuccess: () => {
      setTestName("");
      setNotes("");
      setFormError("");
      invalidate();
    },
    onError: () => setFormError(t("createFailed")),
  });

  const statusMutation = useMutation({
    mutationFn: (vars: { id: string; status: "completed" | "cancelled" }) =>
      updateLabOrderStatus(vars.id, { status: vars.status }),
    onSuccess: invalidate,
  });

  const orders = data?.data ?? [];

  return (
    <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
      <div className="mb-4 flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-dreams-textSecondary" />
        <h2 className="text-base font-semibold text-dreams-textPrimary">
          {t("title")}
        </h2>
      </div>

      {/* Order form */}
      <form
        className="mb-5 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!testName.trim()) return;
          createMutation.mutate();
        }}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label
              htmlFor="lab-order-test-name"
              className="mb-1 block text-xs font-medium text-dreams-textSecondary"
            >
              {t("testNameLabel")}
            </label>
            <input
              id="lab-order-test-name"
              type="text"
              value={testName}
              onChange={(e) => setTestName(e.target.value)}
              placeholder={t("testNamePlaceholder")}
              required
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          <div>
            <label
              htmlFor="lab-order-notes"
              className="mb-1 block text-xs font-medium text-dreams-textSecondary"
            >
              {t("notesLabel")}
            </label>
            <input
              id="lab-order-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("notesPlaceholder")}
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
        </div>
        {formError && <p className="text-sm text-red-600">{formError}</p>}
        <button
          type="submit"
          disabled={createMutation.isPending || !testName.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {createMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {t("orderButton")}
        </button>
      </form>

      {/* Orders list */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-100" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-red-600">{t("loadFailed")}</p>
      ) : orders.length === 0 ? (
        <div className="rounded-lg border border-dashed border-dreams-border p-4 text-center">
          <p className="text-sm text-dreams-textSecondary">{t("empty")}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <div
              key={order.id}
              className="rounded-lg border border-dreams-border p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium text-dreams-textPrimary">
                      {order.test_name}
                    </p>
                    <Badge variant={STATUS_BADGE[order.status]}>
                      {t(`status.${order.status}`)}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-dreams-textSecondary">
                    {formatDate(order.created_at)}
                    {order.notes ? ` · ${order.notes}` : ""}
                  </p>
                </div>
                {order.status === "ordered" && (
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          id: order.id,
                          status: "completed",
                        })
                      }
                      className="rounded-lg border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 transition-colors hover:bg-green-100 disabled:opacity-50"
                    >
                      {t("markCompleted")}
                    </button>
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          id: order.id,
                          status: "cancelled",
                        })
                      }
                      className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50"
                    >
                      {t("cancelOrder")}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  getRefillRequests,
  respondToRefillRequest,
  type RefillRequest,
  type RefillStatus,
} from "@/lib/api/refills";
import { useClinicStore } from "@/stores/clinic-store";
import { cn } from "@/lib/utils";

type StatusFilter = RefillStatus | "all";

const STATUS_BADGE: Record<RefillStatus, "pending" | "completed" | "cancelled"> = {
  pending: "pending",
  approved: "completed",
  declined: "cancelled",
};

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function DoctorRefillRequestsPage() {
  const t = useTranslations("refills");
  const queryClient = useQueryClient();
  const { activeClinicId } = useClinicStore();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending");
  const [respondTarget, setRespondTarget] = useState<{
    request: RefillRequest;
    action: "approve" | "decline";
  } | null>(null);
  const [responseNote, setResponseNote] = useState("");

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    // Keyed by clinic so switching clinic context refetches the scoped list.
    queryKey: ["refill-requests", activeClinicId, statusFilter],
    queryFn: () =>
      getRefillRequests(statusFilter === "all" ? undefined : statusFilter),
  });

  const respondMutation = useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: string;
      action: "approve" | "decline";
      note: string;
    }) => respondToRefillRequest(id, action, note),
    onSuccess: () => {
      setRespondTarget(null);
      setResponseNote("");
      queryClient.invalidateQueries({ queryKey: ["refill-requests"] });
    },
  });

  const filters: { key: StatusFilter; label: string }[] = [
    { key: "pending", label: t("statusPending") },
    { key: "approved", label: t("statusApproved") },
    { key: "declined", label: t("statusDeclined") },
    { key: "all", label: t("filterAll") },
  ];

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("title") }]} />

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            {t("title")}
          </h1>
          <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
        </div>
        <div className="flex gap-1 rounded-lg bg-white border border-dreams-border p-1">
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setStatusFilter(f.key)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                statusFilter === f.key
                  ? "bg-dreams-blue text-white"
                  : "text-dreams-textSecondary hover:text-dreams-textPrimary"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading refill requests">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="bg-white rounded-lg shadow-card border border-dreams-border p-4 space-y-2"
            >
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-72" />
              <Skeleton className="h-3 w-40" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card">
          <EmptyState
            icon={RefreshCcw}
            title={t("loadFailed")}
            description={t("loadFailedHint")}
            action={
              <Button onClick={() => refetch()} disabled={isFetching}>
                {isFetching ? t("retrying") : t("tryAgain")}
              </Button>
            }
          />
        </div>
      ) : (data ?? []).length === 0 ? (
        <div className="bg-white rounded-lg shadow-card">
          <EmptyState
            icon={RefreshCcw}
            title={t("emptyTitle")}
            description={t("emptyHint")}
          />
        </div>
      ) : (
        <div className="space-y-3">
          {(data ?? []).map((req) => (
            <div
              key={req.id}
              className="bg-white rounded-lg shadow-card border border-dreams-border p-4"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-dreams-textPrimary">
                      {req.patient_name ?? t("unknownPatient")}
                    </p>
                    <Badge variant={STATUS_BADGE[req.status]}>
                      {t(
                        req.status === "pending"
                          ? "statusPending"
                          : req.status === "approved"
                            ? "statusApproved"
                            : "statusDeclined"
                      )}
                    </Badge>
                  </div>
                  <p className="text-xs text-dreams-textSecondary mt-1">
                    {t("requestedOn", { date: formatDate(req.created_at) })}
                    {req.prescribed_at
                      ? ` · ${t("prescribedOn", { date: formatDate(req.prescribed_at) })}`
                      : ""}
                    {req.diagnosis ? ` · ${req.diagnosis}` : ""}
                  </p>
                  {(req.medicines ?? []).length > 0 && (
                    <ul className="mt-2 text-sm text-dreams-textSecondary space-y-0.5">
                      {(req.medicines ?? []).map((m, idx) => (
                        <li key={idx}>
                          <span className="font-medium text-dreams-textPrimary">
                            {m.brand_name ?? m.name ?? "—"}
                          </span>
                          {" — "}
                          {[m.dose ?? m.dosage, m.frequency, m.duration]
                            .filter(Boolean)
                            .join(" · ")}
                        </li>
                      ))}
                    </ul>
                  )}
                  {req.note && (
                    <p className="mt-2 text-sm italic text-dreams-textSecondary">
                      “{req.note}”
                    </p>
                  )}
                  {req.response_note && req.status !== "pending" && (
                    <p className="mt-1 text-xs text-dreams-textSecondary">
                      {t("yourResponse")}: {req.response_note}
                    </p>
                  )}
                </div>

                {req.status === "pending" && (
                  <div className="flex gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      onClick={() => {
                        setResponseNote("");
                        setRespondTarget({ request: req, action: "approve" });
                      }}
                    >
                      {t("approve")}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setResponseNote("");
                        setRespondTarget({ request: req, action: "decline" });
                      }}
                    >
                      {t("decline")}
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Respond dialog — shared for approve and decline */}
      <Dialog
        open={respondTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRespondTarget(null);
            setResponseNote("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {respondTarget?.action === "approve"
                ? t("approveTitle")
                : t("declineTitle")}
            </DialogTitle>
            <DialogDescription>
              {respondTarget?.action === "approve"
                ? t("approveDescription")
                : t("declineDescription")}
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={responseNote}
            onChange={(e) => setResponseNote(e.target.value)}
            placeholder={t("responseNotePlaceholder")}
            maxLength={1000}
            rows={3}
          />
          {respondMutation.isError && (
            <p className="text-sm text-red-600">{t("respondFailed")}</p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRespondTarget(null)}
              disabled={respondMutation.isPending}
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={() =>
                respondTarget &&
                respondMutation.mutate({
                  id: respondTarget.request.id,
                  action: respondTarget.action,
                  note: responseNote,
                })
              }
              disabled={respondMutation.isPending}
            >
              {respondMutation.isPending
                ? t("submitting")
                : respondTarget?.action === "approve"
                  ? t("approve")
                  : t("decline")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

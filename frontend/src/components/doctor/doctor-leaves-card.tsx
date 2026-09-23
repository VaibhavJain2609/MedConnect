"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { CalendarOff, Trash2 } from "lucide-react";
import { createLeave, deleteLeave, getMyLeaves } from "@/lib/api/availability";

const inputCls =
  "h-9 rounded-lg border border-dreams-border px-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20";

function formatLeaveDate(iso: string): string {
  // `date` is a clinic-local YYYY-MM-DD; parse the parts so the label never
  // shifts across browser timezones.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function errorMessage(e: unknown): string | null {
  const err = e as { response?: { data?: { error?: { message?: string } } } };
  return err?.response?.data?.error?.message ?? null;
}

/**
 * Leave Days card — the authenticated doctor's full-day blocks. A leave day
 * empties every bookable slot for that doctor (see routers/availability.py).
 */
export function DoctorLeavesCard() {
  const t = useTranslations("doctorLeaves");
  const queryClient = useQueryClient();
  const [leaveDate, setLeaveDate] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const leavesQuery = useQuery({
    queryKey: ["my-leaves"],
    queryFn: getMyLeaves,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["my-leaves"] });

  const createMutation = useMutation({
    mutationFn: createLeave,
    onSuccess: () => {
      setLeaveDate("");
      setLeaveReason("");
      setFormError(null);
      invalidate();
    },
    onError: (e) => setFormError(errorMessage(e) ?? t("addFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLeave,
    onSuccess: () => {
      setFormError(null);
      invalidate();
    },
    onError: (e) => setFormError(errorMessage(e) ?? t("removeFailed")),
  });

  const leaves = (leavesQuery.data ?? [])
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="rounded-xl border border-dreams-border bg-white">
      <div className="border-b border-dreams-border px-5 py-4">
        <div className="flex items-center gap-2">
          <CalendarOff className="h-5 w-5 text-dreams-blue" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            {t("title")}
          </h2>
        </div>
        <p className="text-sm text-dreams-textSecondary mt-0.5">
          {t("description")}
        </p>
      </div>
      <div className="px-5 py-4 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={leaveDate}
            onChange={(e) => setLeaveDate(e.target.value)}
            className={inputCls}
            aria-label={t("dateLabel")}
          />
          <input
            type="text"
            value={leaveReason}
            onChange={(e) => setLeaveReason(e.target.value)}
            placeholder={t("reasonPlaceholder")}
            maxLength={255}
            className={`${inputCls} w-64`}
            aria-label={t("reasonLabel")}
          />
          <button
            onClick={() =>
              leaveDate &&
              createMutation.mutate({
                date: leaveDate,
                reason: leaveReason || null,
              })
            }
            disabled={!leaveDate || createMutation.isPending}
            className="h-9 rounded-lg bg-dreams-blue px-4 text-sm font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
          >
            {createMutation.isPending ? t("adding") : t("add")}
          </button>
        </div>

        {formError && (
          <p className="text-sm text-red-600" role="alert">
            {formError}
          </p>
        )}

        {leavesQuery.isLoading ? (
          <p className="text-sm text-dreams-textSecondary">{t("loading")}</p>
        ) : leavesQuery.isError ? (
          <p className="text-sm text-red-600">{t("loadFailed")}</p>
        ) : leaves.length === 0 ? (
          <p className="text-sm text-dreams-textSecondary">{t("empty")}</p>
        ) : (
          <ul className="divide-y divide-dreams-border">
            {leaves.map((leave) => (
              <li
                key={leave.id}
                className="flex items-center gap-3 py-2.5 text-sm"
              >
                <span className="font-medium text-dreams-textPrimary">
                  {formatLeaveDate(leave.date)}
                </span>
                {leave.reason && (
                  <span className="text-dreams-textSecondary">
                    — {leave.reason}
                  </span>
                )}
                <button
                  onClick={() => deleteMutation.mutate(leave.id)}
                  disabled={deleteMutation.isPending}
                  className="ml-auto text-gray-400 hover:text-red-500 disabled:opacity-50"
                  aria-label={t("remove")}
                  title={t("remove")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

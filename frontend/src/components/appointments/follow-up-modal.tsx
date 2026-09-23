"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";
import { createEncounterFollowUp } from "@/lib/api/encounters";
import type { Appointment } from "@/lib/api/appointments";

interface FollowUpModalProps {
  encounterId: string;
  open: boolean;
  onClose: () => void;
  onScheduled: (appt: Appointment) => void;
}

/**
 * Date/time picker for booking a follow-up appointment from an encounter.
 * POST /api/v1/encounters/{id}/follow-up is idempotent — if a follow-up
 * already exists the server returns it unchanged.
 */
export function FollowUpModal({
  encounterId,
  open,
  onClose,
  onScheduled,
}: FollowUpModalProps) {
  const t = useTranslations("followUp");
  const tCommon = useTranslations("common");

  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [duration, setDuration] = useState(30);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSubmit = async () => {
    setError("");
    if (!date || !time) {
      setError(t("errorSelectDateTime"));
      return;
    }
    // Interpret the picked date+time in the local timezone, then send UTC.
    const scheduledAt = new Date(`${date}T${time}`);
    if (Number.isNaN(scheduledAt.getTime())) {
      setError(t("errorSelectDateTime"));
      return;
    }
    setSubmitting(true);
    try {
      const appt = await createEncounterFollowUp(encounterId, {
        scheduled_at: scheduledAt.toISOString(),
        duration_minutes: duration,
        type: "follow-up",
        notes: notes.trim() || null,
      });
      onScheduled(appt);
      onClose();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: { error?: { message?: string } } } } })
          ?.response?.data?.detail?.error?.message;
      setError(detail || t("errorFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    "w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("title")}
    >
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-dreams-border px-5 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            {t("title")}
          </h2>
          <button
            onClick={onClose}
            aria-label={tCommon("close")}
            className="rounded-lg p-1 text-dreams-textSecondary hover:bg-dreams-lightBg"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("date")}
              </label>
              <input
                type="date"
                value={date}
                min={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setDate(e.target.value)}
                className={inputCls}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("time")}
              </label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              {t("duration")}
            </label>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className={inputCls}
            >
              {[15, 20, 30, 45, 60].map((m) => (
                <option key={m} value={m}>
                  {t("durationOption", { count: m })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              {t("notes")}
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder={t("notesPlaceholder")}
              className={`${inputCls} resize-y`}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-dreams-border px-5 py-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg"
          >
            {tCommon("cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? t("scheduling") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

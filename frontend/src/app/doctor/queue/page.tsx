"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import api from "@/lib/api";
import { useClinicStore } from "@/stores/clinic-store";

interface QueueEntry {
  id: string;
  queue_number: number;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  status: "waiting" | "in_consultation" | "completed" | "cancelled";
  notes: string | null;
  called_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// Status labels come from the "doctorQueue.status" message namespace
// (see docs/i18n.md).
const STATUS_COLORS: Record<QueueEntry["status"], string> = {
  waiting: "bg-blue-100 text-blue-800",
  in_consultation: "bg-green-100 text-green-800",
  completed: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-700",
};

function formatTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface BillModalState {
  entryId: string;
  patientId: string;
  patientName: string | null;
}

function BillPatientModal({
  state,
  clinicId,
  onClose,
}: {
  state: BillModalState;
  clinicId: string;
  onClose: () => void;
}) {
  const t = useTranslations("doctorQueue.bill");
  const tCommon = useTranslations("common");
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const amt = parseFloat(amount);
    if (!amount || isNaN(amt) || amt <= 0) {
      setError(t("invalidAmount"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      // X-Clinic-Id header is attached automatically by the axios interceptor
      await api.post("/api/v1/billing", {
        patient_id: state.patientId,
        clinic_id: clinicId || undefined,
        amount: amt,
        payment_method: paymentMethod,
        notes: notes || undefined,
      });
      onClose();
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: { error?: { message?: string } } | string } } };
      const msg =
        axiosError?.response?.data?.detail &&
        typeof axiosError.response.data.detail === "object" &&
        axiosError.response.data.detail.error?.message
          ? axiosError.response.data.detail.error.message
          : t("createFailed");
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("ariaLabel")}
        className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-dreams-textPrimary mb-1">{t("title")}</h2>
        <p className="text-sm text-dreams-textSecondary mb-4">
          {t("patientLabel")} <span className="font-medium text-dreams-textPrimary">{state.patientName ?? tCommon("unknownPatient")}</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              {t("amount")} <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={t("amountPlaceholder")}
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">{t("paymentMethod")}</label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30"
            >
              <option value="cash">{t("methods.cash")}</option>
              <option value="card">{t("methods.card")}</option>
              <option value="upi">{t("methods.upi")}</option>
              <option value="insurance">{t("methods.insurance")}</option>
              <option value="other">{t("methods.other")}</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">{t("notes")}</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("notesPlaceholder")}
              rows={2}
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30 resize-none"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm border border-dreams-border rounded-lg text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
            >
              {tCommon("cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 text-sm bg-dreams-blue text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {saving ? t("saving") : t("submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function QueuePage() {
  const t = useTranslations("doctorQueue");
  const tCommon = useTranslations("common");
  // Reactive clinic id from the persisted clinic store — the axios
  // interceptor attaches it as X-Clinic-Id automatically.
  const clinicId = useClinicStore((s) => s.activeClinicId) ?? "";

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [billModal, setBillModal] = useState<BillModalState | null>(null);

  // Polling query replaces the manual fetch + setInterval loop.
  const {
    data: entries = [],
    isLoading: loading,
    isError,
    refetch: fetchQueue,
  } = useQuery<QueueEntry[]>({
    queryKey: ["doctor-queue", clinicId],
    queryFn: async () => {
      const res = await api.get("/api/v1/queue");
      return res.data.data ?? res.data;
    },
    enabled: !!clinicId,
    refetchInterval: 30_000,
  });

  async function updateStatus(id: string, status: QueueEntry["status"]) {
    setActionLoading(id + status);
    try {
      await api.patch(`/api/v1/queue/${id}/status`, { status });
      await fetchQueue();
    } catch {
      alert(t("updateFailed"));
    } finally {
      setActionLoading(null);
    }
  }

  const waiting = entries.filter((e) => e.status === "waiting");
  const inConsultation = entries.filter((e) => e.status === "in_consultation");
  const done = entries.filter((e) => e.status === "completed" || e.status === "cancelled");

  if (clinicId && loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      </div>
    );
  }

  // Derived error surface: a fixed message when no clinic is selected,
  // otherwise the last fetch failure.
  const displayError = clinicId
    ? isError
      ? t("loadFailed")
      : ""
    : t("noClinic");

  if (displayError) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {displayError}
        </div>
      </div>
    );
  }

  return (
    <>
      {billModal && (
        <BillPatientModal
          state={billModal}
          clinicId={clinicId}
          onClose={() => setBillModal(null)}
        />
      )}

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("title")}</h1>
            <p className="text-sm text-dreams-textSecondary mt-1">
              {t("subtitle")}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-dreams-textSecondary">
              {t("summary", { waiting: waiting.length, inConsultation: inConsultation.length })}
            </span>
            <button
              onClick={() => void fetchQueue()}
              className="px-3 py-1.5 text-sm border border-dreams-border rounded-lg hover:bg-gray-50 transition-colors"
            >
              {t("refresh")}
            </button>
          </div>
        </div>

        {/* Next patient action */}
        {waiting.length > 0 && inConsultation.length === 0 && (
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-800">{t("nextUp")}</p>
              <p className="text-lg font-bold text-blue-900 mt-0.5">
                #{waiting[0].queue_number} — {waiting[0].patient_name ?? tCommon("unknownPatient")}
              </p>
            </div>
            <button
              onClick={() => updateStatus(waiting[0].id, "in_consultation")}
              disabled={actionLoading === waiting[0].id + "in_consultation"}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {t("callNext")}
            </button>
          </div>
        )}

        {/* In Consultation */}
        {inConsultation.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-3">
              {t("sections.inConsultation")}
            </h2>
            <div className="space-y-2">
              {inConsultation.map((entry) => (
                <QueueCard
                  key={entry.id}
                  entry={entry}
                  onComplete={() => updateStatus(entry.id, "completed")}
                  onCancel={() => updateStatus(entry.id, "cancelled")}
                  onBill={() => setBillModal({ entryId: entry.id, patientId: entry.patient_id, patientName: entry.patient_name })}
                  loading={actionLoading}
                />
              ))}
            </div>
          </section>
        )}

        {/* Waiting */}
        {waiting.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-3">
              {t("sections.waiting", { count: waiting.length })}
            </h2>
            <div className="space-y-2">
              {waiting.map((entry) => (
                <QueueCard
                  key={entry.id}
                  entry={entry}
                  onCallIn={() => updateStatus(entry.id, "in_consultation")}
                  onCancel={() => updateStatus(entry.id, "cancelled")}
                  loading={actionLoading}
                />
              ))}
            </div>
          </section>
        )}

        {/* Completed today */}
        {done.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-3">
              {t("sections.completedToday", { count: done.length })}
            </h2>
            <div className="space-y-2">
              {done.map((entry) => (
                <QueueCard
                  key={entry.id}
                  entry={entry}
                  onBill={entry.status === "completed" ? () => setBillModal({ entryId: entry.id, patientId: entry.patient_id, patientName: entry.patient_name }) : undefined}
                  loading={actionLoading}
                />
              ))}
            </div>
          </section>
        )}

        {entries.length === 0 && (
          <div className="text-center py-16 text-dreams-textSecondary">
            {t("empty")}
          </div>
        )}
      </div>
    </>
  );
}

function QueueCard({
  entry,
  onCallIn,
  onComplete,
  onCancel,
  onBill,
  loading,
}: {
  entry: QueueEntry;
  onCallIn?: () => void;
  onComplete?: () => void;
  onCancel?: () => void;
  onBill?: () => void;
  loading: string | null;
}) {
  const t = useTranslations("doctorQueue");
  const tCommon = useTranslations("common");
  const isLoading = (suffix: string) => loading === entry.id + suffix;

  return (
    <div className="rounded-xl border border-dreams-border bg-white px-4 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-4 min-w-0">
        <span className="w-8 h-8 flex items-center justify-center rounded-full bg-dreams-lightBg text-sm font-bold text-dreams-textPrimary flex-shrink-0">
          {entry.queue_number}
        </span>
        <div className="min-w-0">
          <p className="font-medium text-dreams-textPrimary truncate">
            {entry.patient_name ?? tCommon("unknownPatient")}
          </p>
          {entry.notes && (
            <p className="text-xs text-dreams-textSecondary truncate">{entry.notes}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        <span className="text-xs text-dreams-textSecondary hidden sm:block">
          {formatTime(entry.created_at)}
        </span>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
            STATUS_COLORS[entry.status]
          }`}
        >
          {t(`status.${entry.status}`)}
        </span>

        {onCallIn && (
          <button
            onClick={onCallIn}
            disabled={isLoading("in_consultation")}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {t("actions.callIn")}
          </button>
        )}
        {onComplete && (
          <button
            onClick={onComplete}
            disabled={isLoading("completed")}
            className="px-3 py-1 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {t("actions.complete")}
          </button>
        )}
        {onBill && (
          <button
            onClick={onBill}
            className="px-3 py-1 text-xs border border-dreams-blue text-dreams-blue rounded-lg hover:bg-dreams-blue/10 transition-colors"
          >
            {t("actions.billPatient")}
          </button>
        )}
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={isLoading("cancelled")}
            className="px-3 py-1 text-xs border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            {tCommon("cancel")}
          </button>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

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

const STATUS_LABELS: Record<QueueEntry["status"], string> = {
  waiting: "Waiting",
  in_consultation: "In Consultation",
  completed: "Completed",
  cancelled: "Cancelled",
};

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
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const amt = parseFloat(amount);
    if (!amount || isNaN(amt) || amt <= 0) {
      setError("Please enter a valid amount.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.post(
        "/api/v1/billing",
        {
          patient_id: state.patientId,
          clinic_id: clinicId || undefined,
          amount: amt,
          payment_method: paymentMethod,
          notes: notes || undefined,
        },
        clinicId ? { headers: { "X-Clinic-Id": clinicId } } : {}
      );
      onClose();
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: { error?: { message?: string } } | string } } };
      const msg =
        axiosError?.response?.data?.detail &&
        typeof axiosError.response.data.detail === "object" &&
        axiosError.response.data.detail.error?.message
          ? axiosError.response.data.detail.error.message
          : "Failed to create invoice.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <h2 className="text-lg font-bold text-dreams-textPrimary mb-1">Create Invoice</h2>
        <p className="text-sm text-dreams-textSecondary mb-4">
          Patient: <span className="font-medium text-dreams-textPrimary">{state.patientName ?? "Unknown"}</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              Amount (₹) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="e.g. 500"
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">Payment Method</label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30"
            >
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="upi">UPI</option>
              <option value="insurance">Insurance</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Consultation fee"
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
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 text-sm bg-dreams-blue text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {saving ? "Saving…" : "Create Invoice"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function QueuePage() {
  const { user } = useAuthStore();
  const clinicId = typeof window !== "undefined"
    ? localStorage.getItem("activeClinicId") ?? ""
    : "";

  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [billModal, setBillModal] = useState<BillModalState | null>(null);

  const fetchQueue = useCallback(async () => {
    if (!clinicId) {
      setError("No active clinic selected. Set clinic from the clinic page.");
      setLoading(false);
      return;
    }
    try {
      const res = await api.get("/api/v1/queue", {
        headers: { "X-Clinic-Id": clinicId },
      });
      setEntries(res.data.data ?? res.data);
      setError("");
    } catch {
      setError("Failed to load queue.");
    } finally {
      setLoading(false);
    }
  }, [clinicId]);

  useEffect(() => {
    fetchQueue();
    const timer = setInterval(fetchQueue, 30_000);
    return () => clearInterval(timer);
  }, [fetchQueue]);

  async function updateStatus(id: string, status: QueueEntry["status"]) {
    setActionLoading(id + status);
    try {
      await api.patch(
        `/api/v1/queue/${id}/status`,
        { status },
        { headers: { "X-Clinic-Id": clinicId } }
      );
      await fetchQueue();
    } catch {
      alert("Failed to update status.");
    } finally {
      setActionLoading(null);
    }
  }

  const waiting = entries.filter((e) => e.status === "waiting");
  const inConsultation = entries.filter((e) => e.status === "in_consultation");
  const done = entries.filter((e) => e.status === "completed" || e.status === "cancelled");

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
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
            <h1 className="text-2xl font-bold text-dreams-textPrimary">Queue</h1>
            <p className="text-sm text-dreams-textSecondary mt-1">
              Today&apos;s waiting room — auto-refreshes every 30s
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-dreams-textSecondary">
              {waiting.length} waiting · {inConsultation.length} in consultation
            </span>
            <button
              onClick={fetchQueue}
              className="px-3 py-1.5 text-sm border border-dreams-border rounded-lg hover:bg-gray-50 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Next patient action */}
        {waiting.length > 0 && inConsultation.length === 0 && (
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-800">Next up</p>
              <p className="text-lg font-bold text-blue-900 mt-0.5">
                #{waiting[0].queue_number} — {waiting[0].patient_name ?? "Unknown Patient"}
              </p>
            </div>
            <button
              onClick={() => updateStatus(waiting[0].id, "in_consultation")}
              disabled={actionLoading === waiting[0].id + "in_consultation"}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              Call Next Patient
            </button>
          </div>
        )}

        {/* In Consultation */}
        {inConsultation.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-3">
              In Consultation
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
              Waiting ({waiting.length})
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
              Completed Today ({done.length})
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
            No patients in queue today.
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
  const isLoading = (suffix: string) => loading === entry.id + suffix;

  return (
    <div className="rounded-xl border border-dreams-border bg-white px-4 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-4 min-w-0">
        <span className="w-8 h-8 flex items-center justify-center rounded-full bg-dreams-lightBg text-sm font-bold text-dreams-textPrimary flex-shrink-0">
          {entry.queue_number}
        </span>
        <div className="min-w-0">
          <p className="font-medium text-dreams-textPrimary truncate">
            {entry.patient_name ?? "Unknown Patient"}
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
          {STATUS_LABELS[entry.status]}
        </span>

        {onCallIn && (
          <button
            onClick={onCallIn}
            disabled={isLoading("in_consultation")}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            Call In
          </button>
        )}
        {onComplete && (
          <button
            onClick={onComplete}
            disabled={isLoading("completed")}
            className="px-3 py-1 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            Complete
          </button>
        )}
        {onBill && (
          <button
            onClick={onBill}
            className="px-3 py-1 text-xs border border-dreams-blue text-dreams-blue rounded-lg hover:bg-dreams-blue/10 transition-colors"
          >
            Bill Patient
          </button>
        )}
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={isLoading("cancelled")}
            className="px-3 py-1 text-xs border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

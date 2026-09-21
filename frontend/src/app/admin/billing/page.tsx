"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Plus, X, Loader2 } from "lucide-react";
import api from "@/lib/api";

interface BillItem {
  id: string;
  description: string;
  quantity: string;
  unit_amount: string;
  amount: string;
}

interface Bill {
  id: string;
  patient_id: string;
  patient_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  appointment_id: string | null;
  amount: string;
  status: string;
  payment_method: string | null;
  notes: string | null;
  items?: BillItem[];
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-600",
  refunded: "bg-purple-100 text-purple-800",
};

function formatCurrency(amount: string | number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(amount));
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Patient search typeahead (mirrors admin/appointments)
// ---------------------------------------------------------------------------

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
}

function PatientSearchInput({
  onSelect,
}: {
  onSelect: (p: PatientSuggestion) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    api
      .get(
        `/api/v1/admin/users?role=patient&search=${encodeURIComponent(q)}&limit=10`
      )
      .then((res) => {
        setResults(res.data.data || []);
        setOpen(true);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search patient by name or phone..."
        className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
        </div>
      )}
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white shadow-lg">
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors border-b border-dreams-border last:border-0"
              onMouseDown={() => {
                onSelect(p);
                setQuery("");
                setResults([]);
                setOpen(false);
              }}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">
                  {p.full_name}
                </p>
                {p.phone && (
                  <p className="text-xs text-dreams-textSecondary">{p.phone}</p>
                )}
              </div>
            </button>
          ))}
          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="px-4 py-3 text-sm text-dreams-textSecondary">
              No patients found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create-bill modal with repeatable line-item editor
// ---------------------------------------------------------------------------

interface ItemDraft {
  description: string;
  quantity: string;
  unit_amount: string;
}

function CreateBillModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [patient, setPatient] = useState<PatientSuggestion | null>(null);
  const [items, setItems] = useState<ItemDraft[]>([
    { description: "", quantity: "1", unit_amount: "" },
  ]);
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const validItems = items.filter(
    (it) =>
      it.description.trim() &&
      Number(it.quantity) > 0 &&
      it.unit_amount !== "" &&
      Number(it.unit_amount) >= 0
  );
  const itemsTotal = validItems.reduce(
    (sum, it) => sum + Number(it.quantity) * Number(it.unit_amount),
    0
  );
  const hasItems = items.some(
    (it) => it.description.trim() || it.unit_amount !== ""
  );

  function updateItem(idx: number, field: keyof ItemDraft, value: string) {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it))
    );
  }

  function addItemRow() {
    setItems((prev) => [...prev, { description: "", quantity: "1", unit_amount: "" }]);
  }

  function removeItemRow(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!patient) {
      setError("Please select a patient.");
      return;
    }
    if (hasItems && validItems.length === 0) {
      setError("Complete each item row (description, qty, unit price) or remove it.");
      return;
    }
    if (!hasItems) {
      const amt = parseFloat(amount);
      if (!amount || isNaN(amt) || amt <= 0) {
        setError("Please enter a valid amount or add line items.");
        return;
      }
    }
    setSaving(true);
    setError("");
    try {
      await api.post("/api/v1/billing", {
        patient_id: patient.id,
        ...(hasItems
          ? {
              items: validItems.map((it) => ({
                description: it.description.trim(),
                quantity: Number(it.quantity),
                unit_amount: Number(it.unit_amount),
              })),
            }
          : { amount: parseFloat(amount) }),
        notes: notes || undefined,
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { data?: { detail?: { error?: { message?: string } } | string } };
      };
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Create bill"
        className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-dreams-textPrimary mb-4">
          New Bill
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              Patient <span className="text-red-500">*</span>
            </label>
            {patient ? (
              <div className="flex items-center justify-between rounded-lg border border-dreams-border px-3 py-2">
                <span className="text-sm font-medium text-dreams-textPrimary">
                  {patient.full_name}
                </span>
                <button
                  type="button"
                  onClick={() => setPatient(null)}
                  className="text-dreams-textSecondary hover:text-dreams-textPrimary"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <PatientSearchInput onSelect={setPatient} />
            )}
          </div>

          {/* Line items editor */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-dreams-textPrimary">
                Line Items
              </label>
              <button
                type="button"
                onClick={addItemRow}
                className="flex items-center gap-1 text-xs font-medium text-dreams-blue hover:opacity-80"
              >
                <Plus className="h-3.5 w-3.5" /> Add item
              </button>
            </div>
            <div className="space-y-2">
              {items.map((it, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <input
                    type="text"
                    value={it.description}
                    onChange={(e) => updateItem(idx, "description", e.target.value)}
                    placeholder="Description"
                    className="flex-1 h-9 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                  />
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={it.quantity}
                    onChange={(e) => updateItem(idx, "quantity", e.target.value)}
                    placeholder="Qty"
                    className="w-16 h-9 rounded-lg border border-dreams-border px-2 text-sm text-right focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                  />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={it.unit_amount}
                    onChange={(e) => updateItem(idx, "unit_amount", e.target.value)}
                    placeholder="Unit ₹"
                    className="w-24 h-9 rounded-lg border border-dreams-border px-2 text-sm text-right focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                  />
                  <button
                    type="button"
                    onClick={() => removeItemRow(idx)}
                    className="h-9 px-1 text-dreams-textSecondary hover:text-red-500"
                    aria-label="Remove item"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
            {hasItems && (
              <div className="mt-2 flex justify-end text-sm">
                <span className="text-dreams-textSecondary mr-2">Total:</span>
                <span className="font-semibold text-dreams-textPrimary">
                  {formatCurrency(itemsTotal)}
                </span>
              </div>
            )}
          </div>

          {/* Flat amount fallback when no items are used */}
          {!hasItems && (
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
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Consultation fee"
              rows={2}
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue/30 resize-none"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
              {error}
            </p>
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
              {saving ? "Saving…" : "Create Bill"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function BillingPage() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const params = statusFilter ? `?status=${statusFilter}` : "";
    api
      .get(`/api/v1/billing${params}`)
      .then((res) => {
        setBills(res.data.data ?? []);
        setTotal(res.data.total ?? 0);
      })
      .catch(() => setError("Failed to load billing data."))
      .finally(() => setLoading(false));
  }, [statusFilter, reloadKey]);

  const totalPaid = bills
    .filter((b) => b.status === "paid")
    .reduce((sum, b) => sum + Number(b.amount), 0);

  const totalPending = bills
    .filter((b) => b.status === "pending")
    .reduce((sum, b) => sum + Number(b.amount), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">Billing</h1>
          <p className="text-sm text-dreams-textSecondary mt-1">
            Manage invoices and track revenue
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          <Plus className="h-4 w-4" /> New Bill
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-dreams-border bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary">
            Total Bills
          </p>
          <p className="text-2xl font-bold text-dreams-textPrimary mt-1">{total}</p>
        </div>
        <div className="rounded-xl border border-green-200 bg-green-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-green-700">
            Revenue Collected
          </p>
          <p className="text-2xl font-bold text-green-800 mt-1">
            {formatCurrency(String(totalPaid))}
          </p>
        </div>
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-yellow-700">
            Outstanding
          </p>
          <p className="text-2xl font-bold text-yellow-800 mt-1">
            {formatCurrency(String(totalPending))}
          </p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-dreams-textSecondary">Filter:</span>
        {["", "pending", "paid", "cancelled", "refunded"].map((s) => (
          <button
            key={s}
            onClick={() => {
              if (s !== statusFilter) {
                setStatusFilter(s);
                setLoading(true);
              }
            }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              statusFilter === s
                ? "bg-dreams-blue text-white"
                : "border border-dreams-border text-dreams-textSecondary hover:bg-gray-50"
            }`}
          >
            {s === "" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-dreams-border bg-white overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center min-h-[200px]">
            <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
          </div>
        ) : error ? (
          <div className="p-6">
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dreams-border bg-dreams-lightBg">
                    <th className="px-4 py-3 text-left font-semibold text-dreams-textSecondary">
                      Date
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-dreams-textSecondary">
                      Patient
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-dreams-textSecondary hidden sm:table-cell">
                      Clinic
                    </th>
                    <th className="px-4 py-3 text-right font-semibold text-dreams-textSecondary">
                      Amount
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-dreams-textSecondary">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-dreams-textSecondary hidden md:table-cell">
                      Payment
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dreams-border">
                  {bills.map((bill) => (
                    <tr key={bill.id} className="hover:bg-dreams-lightBg transition-colors">
                      <td className="px-4 py-3 text-dreams-textSecondary whitespace-nowrap">
                        {formatDate(bill.created_at)}
                      </td>
                      <td className="px-4 py-3 font-medium text-dreams-textPrimary">
                        {bill.patient_name ?? bill.patient_id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3 text-dreams-textSecondary hidden sm:table-cell">
                        {bill.clinic_name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-dreams-textPrimary">
                        {formatCurrency(bill.amount)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            STATUS_COLORS[bill.status] ?? "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {bill.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-dreams-textSecondary hidden md:table-cell capitalize">
                        {bill.payment_method ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {bills.length === 0 && (
              <div className="py-12 text-center text-dreams-textSecondary text-sm">
                No bills found.
              </div>
            )}
          </>
        )}
      </div>

      {showCreate && (
        <CreateBillModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setLoading(true);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}

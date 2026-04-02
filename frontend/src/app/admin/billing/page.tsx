"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

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
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-600",
  refunded: "bg-purple-100 text-purple-800",
};

function formatCurrency(amount: string) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function BillingPage() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    const params = statusFilter ? `?status=${statusFilter}` : "";
    api
      .get(`/api/v1/billing${params}`)
      .then((res) => {
        setBills(res.data.data ?? []);
        setTotal(res.data.total ?? 0);
      })
      .catch(() => setError("Failed to load billing data."))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  const totalPaid = bills
    .filter((b) => b.status === "paid")
    .reduce((sum, b) => sum + Number(b.amount), 0);

  const totalPending = bills
    .filter((b) => b.status === "pending")
    .reduce((sum, b) => sum + Number(b.amount), 0);

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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-dreams-textPrimary">Billing</h1>
        <p className="text-sm text-dreams-textSecondary mt-1">
          Manage invoices and track revenue
        </p>
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
            onClick={() => setStatusFilter(s)}
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
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Receipt,
  ChevronDown,
  ChevronRight,
  Printer,
  Loader2,
} from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { getMyBills, type PatientBill } from "@/lib/api/patient-portal";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  paid: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  overdue: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
  refunded: "bg-purple-100 text-purple-800",
};

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "paid", label: "Paid" },
  { value: "cancelled", label: "Cancelled" },
  { value: "refunded", label: "Refunded" },
];

function formatCurrency(amount: string | number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(Number(amount));
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * Client-side printable receipt.
 * NOTE: the billing API has no PDF/receipt endpoint yet, so we render a
 * printable HTML view in a new window and let the browser handle print/save.
 * TODO: switch to the server receipt endpoint when one exists.
 */
function printReceipt(bill: PatientBill) {
  const win = window.open("", "_blank", "noopener,noreferrer");
  if (!win) return;
  win.document.write(`<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Receipt ${bill.id.slice(0, 8)}</title>
  <style>
    body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 40px; color: #1A1D1F; }
    h1 { font-size: 20px; margin-bottom: 4px; }
    .muted { color: #6B7280; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; margin-top: 24px; }
    td, th { text-align: left; padding: 8px 0; border-bottom: 1px solid #E5E7EB; font-size: 14px; }
    .total td { font-weight: 700; border-bottom: none; font-size: 16px; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; background: #F5F7FA; font-size: 12px; text-transform: capitalize; }
  </style>
</head>
<body>
  <h1>MedConnect — Payment Receipt</h1>
  <p class="muted">Invoice #${bill.id.slice(0, 8)} · ${formatDate(bill.created_at)}</p>
  <table>
    <tr><td>Status</td><td><span class="badge">${bill.status}</span></td></tr>
    <tr><td>Clinic</td><td>${bill.clinic_name ?? "—"}</td></tr>
    <tr><td>Payment method</td><td>${bill.payment_method ?? "—"}</td></tr>
    <tr><td>Description</td><td>${bill.notes ?? "Medical services"}</td></tr>
    <tr class="total"><td>Total</td><td>${formatCurrency(bill.amount)}</td></tr>
  </table>
  <p class="muted" style="margin-top:32px">Generated ${new Date().toLocaleString("en-IN")}</p>
  <script>window.onload = () => window.print();</script>
</body>
</html>`);
  win.document.close();
}

function BillRow({ bill }: { bill: PatientBill }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow-card border border-dreams-border">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 p-4 text-left"
        aria-expanded={expanded}
      >
        <div className="p-2 rounded-lg bg-dreams-lightBg flex-shrink-0">
          <Receipt className="h-4 w-4 text-dreams-blue" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-dreams-textPrimary">
              Invoice #{bill.id.slice(0, 8)}
            </p>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                STATUS_STYLES[bill.status] ?? "bg-gray-100 text-gray-600"
              )}
            >
              {bill.status}
            </span>
          </div>
          <p className="text-xs text-dreams-textSecondary mt-0.5">
            {formatDate(bill.created_at)}
            {bill.clinic_name ? ` · ${bill.clinic_name}` : ""}
          </p>
        </div>
        <p className="font-semibold text-dreams-textPrimary flex-shrink-0">
          {formatCurrency(bill.amount)}
        </p>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-dreams-border px-4 py-4 space-y-4">
          {/* Bill detail — the billing model stores a single amount rather
              than itemized lines, so the notes field acts as the description. */}
          <div className="rounded-lg border border-dreams-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-dreams-lightBg text-dreams-textSecondary text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-2 font-medium">Description</th>
                  <th className="text-right px-4 py-2 font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-dreams-border">
                  <td className="px-4 py-3 text-dreams-textPrimary">
                    {bill.notes ?? "Medical services"}
                  </td>
                  <td className="px-4 py-3 text-right text-dreams-textPrimary">
                    {formatCurrency(bill.amount)}
                  </td>
                </tr>
                <tr className="border-t border-dreams-border bg-dreams-lightBg/50">
                  <td className="px-4 py-3 font-semibold text-dreams-textPrimary">
                    Total
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-dreams-textPrimary">
                    {formatCurrency(bill.amount)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Clinic
              </p>
              <p className="mt-1 text-dreams-textPrimary">
                {bill.clinic_name ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Payment Method
              </p>
              <p className="mt-1 text-dreams-textPrimary capitalize">
                {bill.payment_method ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Last Updated
              </p>
              <p className="mt-1 text-dreams-textPrimary">
                {formatDate(bill.updated_at)}
              </p>
            </div>
          </div>

          <div className="pt-1">
            <button
              type="button"
              onClick={() => printReceipt(bill)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm border border-dreams-border rounded-lg text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              <Printer className="h-4 w-4" />
              Print Receipt
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PatientBillingPage() {
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["patient-billing", statusFilter],
    queryFn: () =>
      getMyBills({ status: statusFilter || undefined, limit: 100 }),
  });

  const bills = data?.data ?? [];

  const totalOutstanding = bills
    .filter((b) => b.status === "pending" || b.status === "overdue")
    .reduce((sum, b) => sum + Number(b.amount), 0);

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Billing" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Billing</h1>
          <p className="text-dreams-textSecondary mt-1">
            Your invoices and payment history
          </p>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-white rounded-xl shadow-card border border-dreams-border p-4 flex flex-wrap items-center gap-x-8 gap-y-2">
        <div>
          <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
            Total Invoices
          </p>
          <p className="text-lg font-semibold text-dreams-textPrimary">
            {data?.total ?? 0}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
            Outstanding
          </p>
          <p className="text-lg font-semibold text-dreams-textPrimary">
            {formatCurrency(totalOutstanding)}
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={cn(
                "px-3 py-1.5 text-sm rounded-lg font-medium transition-colors",
                statusFilter === f.value
                  ? "bg-dreams-blue text-white"
                  : "bg-dreams-lightBg text-dreams-textSecondary hover:text-dreams-textPrimary"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">Failed to load invoices.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            Please refresh the page or try again later.
          </p>
        </div>
      ) : bills.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <Receipt className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">
            No invoices found.
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {statusFilter
              ? "Try a different status filter."
              : "Your invoices will appear here once created."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {bills.map((bill) => (
            <BillRow key={bill.id} bill={bill} />
          ))}
        </div>
      )}
    </div>
  );
}

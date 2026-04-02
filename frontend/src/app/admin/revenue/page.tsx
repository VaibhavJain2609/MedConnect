"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";

interface DailyRevenue {
  date: string;
  total_paid: string;
  bill_count: number;
}

interface MonthlyRevenue {
  year: number;
  month: number;
  total_paid: string;
  bill_count: number;
  daily_breakdown: DailyRevenue[];
}

interface UnpaidBill {
  id: string;
  patient_id: string;
  patient_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  amount: string;
  status: string;
  payment_method: string | null;
  notes: string | null;
  created_at: string;
}

interface UnpaidSummary {
  data: UnpaidBill[];
  total: number;
  total_unpaid_amount: string;
}

function formatINR(amount: string | number): string {
  return `₹${parseFloat(String(amount)).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;
}

export default function RevenuePage() {
  const queryClient = useQueryClient();
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  const [markingPaid, setMarkingPaid] = useState<string | null>(null);

  const { data: daily, isLoading: loadingDaily } = useQuery<DailyRevenue>({
    queryKey: ["revenue-daily", todayStr],
    queryFn: async () => {
      const res = await api.get(`/api/v1/revenue/daily?date=${todayStr}`);
      return res.data;
    },
  });

  const { data: monthly, isLoading: loadingMonthly } = useQuery<MonthlyRevenue>({
    queryKey: ["revenue-monthly", today.getFullYear(), today.getMonth() + 1],
    queryFn: async () => {
      const res = await api.get(
        `/api/v1/revenue/monthly?year=${today.getFullYear()}&month=${today.getMonth() + 1}`
      );
      return res.data;
    },
  });

  const { data: unpaid, isLoading: loadingUnpaid } = useQuery<UnpaidSummary>({
    queryKey: ["revenue-unpaid"],
    queryFn: async () => {
      const res = await api.get("/api/v1/revenue/unpaid");
      return res.data;
    },
  });

  async function markPaid(billId: string) {
    setMarkingPaid(billId);
    try {
      await api.patch(`/api/v1/billing/${billId}`, {
        status: "paid",
        payment_method: "cash",
      });
      await queryClient.invalidateQueries({ queryKey: ["revenue-unpaid"] });
      await queryClient.invalidateQueries({ queryKey: ["revenue-daily"] });
      await queryClient.invalidateQueries({ queryKey: ["revenue-monthly"] });
    } catch {
      alert("Failed to mark as paid.");
    } finally {
      setMarkingPaid(null);
    }
  }

  const monthName = today.toLocaleString("en-IN", { month: "long", year: "numeric" });

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Dashboard", href: "/admin/dashboard" }, { label: "Revenue" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Revenue</h1>
        <p className="text-dreams-textSecondary mt-1">Billing and revenue overview</p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="bg-white rounded-lg shadow-card p-6">
          <p className="text-sm text-dreams-textSecondary">Today&apos;s Revenue</p>
          {loadingDaily ? (
            <div className="h-8 w-24 bg-gray-100 animate-pulse rounded mt-2" />
          ) : (
            <>
              <p className="text-3xl font-bold text-dreams-textPrimary mt-1">
                {formatINR(daily?.total_paid ?? "0")}
              </p>
              <p className="text-sm text-dreams-textSecondary mt-1">
                {daily?.bill_count ?? 0} bill{(daily?.bill_count ?? 0) !== 1 ? "s" : ""}
              </p>
            </>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-card p-6">
          <p className="text-sm text-dreams-textSecondary">{monthName}</p>
          {loadingMonthly ? (
            <div className="h-8 w-24 bg-gray-100 animate-pulse rounded mt-2" />
          ) : (
            <>
              <p className="text-3xl font-bold text-dreams-textPrimary mt-1">
                {formatINR(monthly?.total_paid ?? "0")}
              </p>
              <p className="text-sm text-dreams-textSecondary mt-1">
                {monthly?.bill_count ?? 0} bill{(monthly?.bill_count ?? 0) !== 1 ? "s" : ""}
              </p>
            </>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-card p-6">
          <p className="text-sm text-dreams-textSecondary">Outstanding</p>
          {loadingUnpaid ? (
            <div className="h-8 w-24 bg-gray-100 animate-pulse rounded mt-2" />
          ) : (
            <>
              <p className="text-3xl font-bold text-orange-500 mt-1">
                {formatINR(unpaid?.total_unpaid_amount ?? "0")}
              </p>
              <p className="text-sm text-dreams-textSecondary mt-1">
                {unpaid?.total ?? 0} pending invoice{(unpaid?.total ?? 0) !== 1 ? "s" : ""}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Monthly breakdown */}
      <div className="bg-white rounded-lg shadow-card">
        <div className="px-6 py-4 border-b border-dreams-border">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Daily Breakdown — {monthName}</h2>
        </div>
        <div className="p-6">
          {loadingMonthly ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-gray-100 animate-pulse rounded" />
              ))}
            </div>
          ) : monthly?.daily_breakdown?.length === 0 ? (
            <p className="text-dreams-textSecondary text-center py-8">No paid bills this month yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dreams-border">
                  <th className="text-left py-2 pr-4 text-dreams-textSecondary font-medium">Date</th>
                  <th className="text-right py-2 pr-4 text-dreams-textSecondary font-medium">Bills</th>
                  <th className="text-right py-2 text-dreams-textSecondary font-medium">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {monthly?.daily_breakdown?.map((row) => (
                  <tr key={row.date} className="border-b border-dreams-border last:border-0 hover:bg-dreams-lightBg">
                    <td className="py-2.5 pr-4 text-dreams-textPrimary">
                      {new Date(row.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-dreams-textSecondary">{row.bill_count}</td>
                    <td className="py-2.5 text-right font-medium text-dreams-textPrimary">{formatINR(row.total_paid)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Unpaid invoices */}
      <div className="bg-white rounded-lg shadow-card">
        <div className="px-6 py-4 border-b border-dreams-border">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Unpaid Invoices</h2>
        </div>
        <div className="p-6">
          {loadingUnpaid ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 bg-gray-100 animate-pulse rounded" />
              ))}
            </div>
          ) : unpaid?.data?.length === 0 ? (
            <p className="text-dreams-textSecondary text-center py-8">No unpaid invoices. 🎉</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dreams-border">
                  <th className="text-left py-2 pr-4 text-dreams-textSecondary font-medium">Patient</th>
                  <th className="text-left py-2 pr-4 text-dreams-textSecondary font-medium">Clinic</th>
                  <th className="text-right py-2 pr-4 text-dreams-textSecondary font-medium">Amount</th>
                  <th className="text-right py-2 pr-4 text-dreams-textSecondary font-medium">Date</th>
                  <th className="text-right py-2 text-dreams-textSecondary font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {unpaid?.data?.map((bill) => (
                  <tr key={bill.id} className="border-b border-dreams-border last:border-0 hover:bg-dreams-lightBg">
                    <td className="py-3 pr-4 font-medium text-dreams-textPrimary">{bill.patient_name ?? "—"}</td>
                    <td className="py-3 pr-4 text-dreams-textSecondary">{bill.clinic_name ?? "—"}</td>
                    <td className="py-3 pr-4 text-right font-medium text-dreams-textPrimary">{formatINR(bill.amount)}</td>
                    <td className="py-3 pr-4 text-right text-dreams-textSecondary">
                      {new Date(bill.created_at).toLocaleDateString("en-IN")}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => markPaid(bill.id)}
                        disabled={markingPaid === bill.id}
                        className="px-3 py-1 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {markingPaid === bill.id ? "Saving…" : "Mark Paid"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

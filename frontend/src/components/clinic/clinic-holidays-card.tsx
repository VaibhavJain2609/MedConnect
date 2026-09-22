"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { CalendarOff, Plus, Trash2 } from "lucide-react";
import {
  createClinicHoliday,
  deleteClinicHoliday,
  getClinicHolidays,
} from "@/lib/api/clinics";

function formatHolidayDate(iso: string): string {
  // `date` is a clinic-local YYYY-MM-DD; parse the parts so the label never
  // shifts across browser timezones.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    weekday: "short",
  });
}

export function ClinicHolidaysCard({ clinicId }: { clinicId: string }) {
  const t = useTranslations("clinicHolidays");
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: holidays, isLoading, isError } = useQuery({
    queryKey: ["clinic-holidays", clinicId],
    queryFn: () => getClinicHolidays(clinicId),
    enabled: !!clinicId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["clinic-holidays", clinicId] });

  const createMutation = useMutation({
    mutationFn: () =>
      createClinicHoliday(clinicId, { date, name: name.trim() || undefined }),
    onSuccess: () => {
      invalidate();
      setDate("");
      setName("");
      setFormError(null);
      setShowForm(false);
    },
    onError: () => setFormError(t("addFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: (holidayId: string) => deleteClinicHoliday(clinicId, holidayId),
    onSuccess: invalidate,
  });

  return (
    <div className="rounded-xl border border-dreams-border bg-white p-5 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarOff className="h-4 w-4 text-dreams-textSecondary" />
          <h2 className="text-sm font-semibold text-dreams-textPrimary">
            {t("title")}
          </h2>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg p-1 hover:bg-gray-100"
          aria-label={t("add")}
        >
          <Plus className="h-4 w-4 text-dreams-textSecondary" />
        </button>
      </div>

      <p className="mb-3 text-xs text-dreams-textSecondary">{t("description")}</p>

      {showForm && (
        <div className="mb-3 space-y-2">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label={t("dateLabel")}
            className="w-full rounded-lg border border-dreams-border px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-dreams-blue"
          />
          <div className="flex gap-2">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("namePlaceholder")}
              maxLength={255}
              className="flex-1 rounded-lg border border-dreams-border px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-dreams-blue"
            />
            <button
              onClick={() => createMutation.mutate()}
              disabled={!date || createMutation.isPending}
              className="rounded-lg bg-dreams-blue px-3 py-1.5 text-xs text-white disabled:opacity-50"
            >
              {createMutation.isPending ? t("adding") : t("add")}
            </button>
          </div>
          {formError && (
            <p className="text-xs text-red-600" role="alert">
              {formError}
            </p>
          )}
        </div>
      )}

      {isLoading ? (
        <p className="text-xs text-dreams-textSecondary">{t("loading")}</p>
      ) : isError ? (
        <p className="text-xs text-red-600">{t("loadFailed")}</p>
      ) : !holidays || holidays.length === 0 ? (
        <p className="text-xs text-dreams-textSecondary">{t("empty")}</p>
      ) : (
        <ul className="space-y-2">
          {holidays.map((h) => (
            <li
              key={h.id}
              className="flex items-center justify-between rounded-lg border border-dreams-border px-3 py-2"
            >
              <div>
                <p className="text-xs font-medium text-dreams-textPrimary">
                  {formatHolidayDate(h.date)}
                </p>
                {h.name && (
                  <p className="text-xs text-dreams-textSecondary">{h.name}</p>
                )}
              </div>
              <button
                onClick={() => deleteMutation.mutate(h.id)}
                disabled={deleteMutation.isPending}
                className="rounded-lg p-1 text-dreams-textSecondary hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                aria-label={t("remove")}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

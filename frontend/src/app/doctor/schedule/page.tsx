"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Clock3, Plus, Trash2, X } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DoctorLeavesCard } from "@/components/doctor/doctor-leaves-card";
import {
  getMyAvailability,
  createAvailabilityWindow,
  updateAvailabilityWindow,
  deleteAvailabilityWindow,
  getDoctorSlots,
  type AvailabilityWindow,
} from "@/lib/api/availability";
import {
  getMyClinics,
  getClinicBranches,
  type Clinic,
  type ClinicBranch,
} from "@/lib/api/clinics";
import { getMyDoctorProfile } from "@/lib/api/doctors";

// Backend weekday convention: 0 = Monday .. 6 = Sunday (date.weekday()).
// NOTE: times are naive clinic-local wall-clock values — see the timezone
// assumption documented in backend/app/models/doctor_availability.py.
const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

const SLOT_DURATIONS = [10, 15, 20, 30, 45, 60];

const DEFAULT_TIMEZONE = "Asia/Kolkata";

// ── Location scope ─────────────────────────────────────────────────────────
// A window can apply everywhere (clinic_id NULL), to one clinic, or to one
// branch of a clinic. Scope keys encode the pair so a single <select> value
// carries both ids.
type Scope = { clinicId: string | null; branchId: string | null };

function scopeKey(s: Scope): string {
  if (s.branchId && s.clinicId) return `b:${s.clinicId}:${s.branchId}`;
  if (s.clinicId) return `c:${s.clinicId}`;
  return "";
}

function parseScope(key: string): Scope {
  if (key.startsWith("b:")) {
    const [, clinicId, branchId] = key.split(":");
    return { clinicId, branchId };
  }
  if (key.startsWith("c:")) return { clinicId: key.slice(2), branchId: null };
  return { clinicId: null, branchId: null };
}

// ── Date helpers (local clock — window/leave values are clinic-local) ──────
function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function formatLocalDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const inputCls =
  "h-9 rounded-lg border border-dreams-border px-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20";

interface ScopeOption {
  key: string;
  label: string;
}

function errorMessage(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { error?: { message?: string } } } };
  return err?.response?.data?.error?.message || fallback;
}

// ---------------------------------------------------------------------------
// Existing window row — local draft state, Save enabled when dirty
// ---------------------------------------------------------------------------

function WindowRow({
  window,
  scopeLabel,
  onSave,
  onToggle,
  onDelete,
  saving,
}: {
  window: AvailabilityWindow;
  scopeLabel: string;
  onSave: (id: string, patch: { start_time: string; end_time: string; slot_duration_minutes: number }) => void;
  onToggle: (id: string, isActive: boolean) => void;
  onDelete: (id: string) => void;
  saving: boolean;
}) {
  const t = useTranslations("doctorSchedule");
  const [start, setStart] = useState(window.start_time.slice(0, 5));
  const [end, setEnd] = useState(window.end_time.slice(0, 5));
  const [duration, setDuration] = useState(window.slot_duration_minutes);

  const dirty =
    start !== window.start_time.slice(0, 5) ||
    end !== window.end_time.slice(0, 5) ||
    duration !== window.slot_duration_minutes;

  return (
    <div className="flex flex-wrap items-center gap-2 py-1.5">
      <input
        type="time"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        className={inputCls}
        aria-label={t("startTime")}
      />
      <span className="text-dreams-textSecondary text-sm">–</span>
      <input
        type="time"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        className={inputCls}
        aria-label={t("endTime")}
      />
      <select
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        className={inputCls}
        aria-label={t("slotDuration")}
      >
        {SLOT_DURATIONS.map((d) => (
          <option key={d} value={d}>
            {t("minutesSlots", { min: d })}
          </option>
        ))}
      </select>
      <span
        className="rounded-full bg-dreams-lightBg px-2 py-0.5 text-xs text-dreams-textSecondary"
        title={t("locationLabel")}
      >
        {scopeLabel}
      </span>
      <label className="flex items-center gap-1.5 text-sm text-dreams-textSecondary cursor-pointer">
        <input
          type="checkbox"
          checked={window.is_active}
          onChange={(e) => onToggle(window.id, e.target.checked)}
          className="h-4 w-4 rounded border-dreams-border text-dreams-blue focus:ring-dreams-blue/30"
        />
        {t("active")}
      </label>
      {dirty && (
        <button
          onClick={() =>
            onSave(window.id, {
              start_time: start,
              end_time: end,
              slot_duration_minutes: duration,
            })
          }
          disabled={saving}
          className="h-8 rounded-lg bg-dreams-blue px-3 text-xs font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
        >
          {t("save")}
        </button>
      )}
      <button
        onClick={() => onDelete(window.id)}
        className="ml-auto text-gray-400 hover:text-red-500"
        aria-label={t("deleteWindow")}
        title={t("deleteWindow")}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline "add window" form for a weekday
// ---------------------------------------------------------------------------

function NewWindowForm({
  weekday,
  scopeOptions,
  defaultScopeKey,
  onSubmit,
  onCancel,
  saving,
}: {
  weekday: number;
  scopeOptions: ScopeOption[];
  defaultScopeKey: string;
  onSubmit: (data: {
    weekday: number;
    start_time: string;
    end_time: string;
    slot_duration_minutes: number;
    clinic_id: string | null;
    branch_id: string | null;
  }) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const t = useTranslations("doctorSchedule");
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("17:00");
  const [duration, setDuration] = useState(15);
  const [scope, setScope] = useState(defaultScopeKey);

  const submit = () => {
    const s = parseScope(scope);
    onSubmit({
      weekday,
      start_time: start,
      end_time: end,
      slot_duration_minutes: duration,
      clinic_id: s.clinicId,
      branch_id: s.branchId,
    });
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg bg-dreams-lightBg p-2 mt-1.5">
      <input
        type="time"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        className={inputCls}
        aria-label={t("startTime")}
      />
      <span className="text-dreams-textSecondary text-sm">–</span>
      <input
        type="time"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        className={inputCls}
        aria-label={t("endTime")}
      />
      <select
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        className={inputCls}
        aria-label={t("slotDuration")}
      >
        {SLOT_DURATIONS.map((d) => (
          <option key={d} value={d}>
            {t("minutesSlots", { min: d })}
          </option>
        ))}
      </select>
      {scopeOptions.length > 1 && (
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          className={inputCls}
          aria-label={t("locationLabel")}
        >
          {scopeOptions.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
      )}
      <button
        onClick={submit}
        disabled={saving}
        className="h-8 rounded-lg bg-dreams-blue px-3 text-xs font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
      >
        {t("add")}
      </button>
      <button
        onClick={onCancel}
        className="text-gray-400 hover:text-gray-600"
        aria-label={t("cancel")}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DoctorSchedulePage() {
  const t = useTranslations("doctorSchedule");
  const format = useFormatter();
  const queryClient = useQueryClient();
  const [addingFor, setAddingFor] = useState<number | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  // Selected location scope — drives the default scope for new windows, the
  // clinic filter on the slot preview, and the timezone label.
  const [scopeSel, setScopeSel] = useState("");

  const windowsQuery = useQuery({
    queryKey: ["my-availability"],
    queryFn: getMyAvailability,
  });
  const clinicsQuery = useQuery({
    queryKey: ["my-clinics"],
    queryFn: async () => (await getMyClinics()).data,
  });
  const profileQuery = useQuery({
    queryKey: ["my-doctor-profile"],
    queryFn: getMyDoctorProfile,
  });

  const clinics: Clinic[] = clinicsQuery.data ?? [];
  const clinicIds = clinics.map((c) => c.id).join(",");

  // Branch names are needed for the scope selector and per-window badges.
  const branchesQuery = useQuery({
    queryKey: ["clinic-branches", clinicIds],
    enabled: clinics.length > 0,
    queryFn: async () => {
      const perClinic = await Promise.all(
        clinics.map((c) => getClinicBranches(c.id))
      );
      return perClinic.flat() as ClinicBranch[];
    },
  });
  const branches = branchesQuery.data ?? [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["my-availability"] });
    queryClient.invalidateQueries({ queryKey: ["my-leaves"] });
    queryClient.invalidateQueries({ queryKey: ["my-slot-preview"] });
  };

  const createWindowMutation = useMutation({
    mutationFn: createAvailabilityWindow,
    onSuccess: () => {
      setAddingFor(null);
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e, t("errorGeneric"))),
  });

  const updateWindowMutation = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: string;
      patch: Parameters<typeof updateAvailabilityWindow>[1];
    }) => updateAvailabilityWindow(id, patch),
    onSuccess: () => {
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e, t("errorGeneric"))),
  });

  const deleteWindowMutation = useMutation({
    mutationFn: deleteAvailabilityWindow,
    onSuccess: () => {
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e, t("errorGeneric"))),
  });

  const windows = windowsQuery.data ?? [];

  // ── Scope options: everywhere → each clinic → each clinic–branch ─────────
  const clinicName = (id: string | null) =>
    clinics.find((c) => c.id === id)?.name ?? t("unknownClinic");
  const branchName = (id: string | null) =>
    branches.find((b) => b.id === id)?.name ?? t("unknownBranch");

  const scopeOptions: ScopeOption[] = [
    { key: "", label: t("scopeEverywhere") },
    ...clinics.map((c) => ({
      key: scopeKey({ clinicId: c.id, branchId: null }),
      label: c.name,
    })),
    ...branches.map((b) => ({
      key: scopeKey({ clinicId: b.clinic_id, branchId: b.id }),
      label: `${clinicName(b.clinic_id)} — ${b.name}`,
    })),
  ];

  const windowScopeLabel = (w: AvailabilityWindow): string => {
    if (w.branch_id) return `${clinicName(w.clinic_id)} — ${branchName(w.branch_id)}`;
    if (w.clinic_id) return clinicName(w.clinic_id);
    return t("scopeEverywhere");
  };

  const selectedScope = parseScope(scopeSel);
  const selectedClinic = clinics.find((c) => c.id === selectedScope.clinicId);
  const displayTz = selectedClinic?.timezone ?? DEFAULT_TIMEZONE;

  // ── Effective-slot preview: bookable slots per day for the next 7 days ───
  // The slots endpoint filters by clinic only — a branch scope previews at
  // its clinic level.
  const doctorId = profileQuery.data?.id;
  const previewClinicId = selectedScope.clinicId ?? undefined;
  const previewDays = Array.from({ length: 7 }, (_, i) => addDays(new Date(), i));

  const slotsQuery = useQuery({
    queryKey: ["my-slot-preview", doctorId, previewClinicId ?? "all"],
    enabled: !!doctorId,
    queryFn: () =>
      Promise.all(
        previewDays.map((d) =>
          getDoctorSlots(doctorId!, formatLocalDate(d), previewClinicId)
        )
      ),
  });
  const previewCounts = slotsQuery.data?.map((r) => r.slots.length);

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
      </div>

      {pageError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {pageError}
        </div>
      )}

      {/* Surface query failures — otherwise a failed fetch looks like "not
          available" on every day, which silently misleads the doctor. */}
      {windowsQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {t("loadFailed")}{" "}
          <button
            className="underline font-medium"
            onClick={() => windowsQuery.refetch()}
          >
            {t("retry")}
          </button>
        </div>
      )}

      {/* Weekly availability editor */}
      <div className="rounded-xl border border-dreams-border bg-white">
        <div className="flex flex-wrap items-center gap-3 border-b border-dreams-border px-5 py-4">
          <CalendarDays className="h-5 w-5 text-dreams-blue" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            {t("weeklyAvailability")}
          </h2>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            {scopeOptions.length > 1 && (
              <label className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                {t("locationLabel")}
                <select
                  value={scopeSel}
                  onChange={(e) => setScopeSel(e.target.value)}
                  className={inputCls}
                >
                  {scopeOptions.map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span className="flex items-center gap-1 text-xs text-dreams-textSecondary">
              <Clock3 className="h-3.5 w-3.5" />
              {selectedClinic
                ? t("timezoneNote", { timezone: displayTz })
                : t("timezoneNoteDefault", { timezone: displayTz })}
            </span>
          </div>
        </div>
        <div className="divide-y divide-dreams-border">
          {WEEKDAY_KEYS.map((dayKey, weekday) => {
            const dayWindows = windows.filter((w) => w.weekday === weekday);
            return (
              <div key={weekday} className="px-5 py-3">
                <div className="flex items-start gap-4">
                  <div className="w-24 shrink-0 pt-2 text-sm font-medium text-dreams-textPrimary">
                    {t(`weekdays.${dayKey}`)}
                  </div>
                  <div className="flex-1">
                    {dayWindows.length === 0 && addingFor !== weekday && (
                      <p className="py-1.5 text-sm text-dreams-textSecondary">
                        {t("notAvailable")}
                      </p>
                    )}
                    {dayWindows.map((w) => (
                      <WindowRow
                        key={w.id}
                        window={w}
                        scopeLabel={windowScopeLabel(w)}
                        saving={updateWindowMutation.isPending}
                        onSave={(id, patch) =>
                          updateWindowMutation.mutate({ id, patch })
                        }
                        onToggle={(id, isActive) =>
                          updateWindowMutation.mutate({
                            id,
                            patch: { is_active: isActive },
                          })
                        }
                        onDelete={(id) => deleteWindowMutation.mutate(id)}
                      />
                    ))}
                    {addingFor === weekday ? (
                      <NewWindowForm
                        weekday={weekday}
                        scopeOptions={scopeOptions}
                        defaultScopeKey={scopeSel}
                        saving={createWindowMutation.isPending}
                        onSubmit={(data) => createWindowMutation.mutate(data)}
                        onCancel={() => setAddingFor(null)}
                      />
                    ) : (
                      <button
                        onClick={() => setAddingFor(weekday)}
                        className="mt-1 flex items-center gap-1 text-xs font-medium text-dreams-blue hover:underline"
                      >
                        <Plus className="h-3.5 w-3.5" /> {t("addWindow")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Effective-slot preview — what patients can actually book */}
      <div className="rounded-xl border border-dreams-border bg-white">
        <div className="border-b border-dreams-border px-5 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            {t("previewTitle")}
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-0.5">
            {t("previewSubtitle")}
          </p>
        </div>
        <div className="px-5 py-4">
          {slotsQuery.isLoading ? (
            <p className="text-sm text-dreams-textSecondary">{t("previewLoading")}</p>
          ) : slotsQuery.isError ? (
            <p className="text-sm text-red-600">
              {t("previewFailed")}{" "}
              <button className="underline font-medium" onClick={() => slotsQuery.refetch()}>
                {t("retry")}
              </button>
            </p>
          ) : (
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
              {previewDays.map((d, i) => {
                const count = previewCounts?.[i];
                const weekdayKey =
                  WEEKDAY_KEYS[(d.getDay() + 6) % 7];
                return (
                  <li
                    key={formatLocalDate(d)}
                    className="rounded-lg border border-dreams-border px-3 py-2.5 text-center"
                  >
                    <p className="text-xs font-medium text-dreams-textSecondary">
                      {t(`weekdaysShort.${weekdayKey}`)}{" "}
                      {format.dateTime(d, { day: "numeric", month: "short" })}
                    </p>
                    <p
                      className={`mt-1 text-sm font-semibold ${
                        count ? "text-dreams-textPrimary" : "text-dreams-textSecondary"
                      }`}
                    >
                      {count === undefined ? "—" : t("slotsCount", { count })}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* Leave days */}
      <DoctorLeavesCard />
    </div>
  );
}

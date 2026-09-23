"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Plus, Trash2, X } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DoctorLeavesCard } from "@/components/doctor/doctor-leaves-card";
import {
  getMyAvailability,
  createAvailabilityWindow,
  updateAvailabilityWindow,
  deleteAvailabilityWindow,
  type AvailabilityWindow,
} from "@/lib/api/availability";

// Backend weekday convention: 0 = Monday .. 6 = Sunday (date.weekday()).
// NOTE: times are naive clinic-local wall-clock values — see the timezone
// assumption documented in backend/app/models/doctor_availability.py.
const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const SLOT_DURATIONS = [10, 15, 20, 30, 45, 60];

function errorMessage(e: unknown): string {
  const err = e as { response?: { data?: { error?: { message?: string } } } };
  return err?.response?.data?.error?.message || "Something went wrong";
}

const inputCls =
  "h-9 rounded-lg border border-dreams-border px-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20";

// ---------------------------------------------------------------------------
// Existing window row — local draft state, Save enabled when dirty
// ---------------------------------------------------------------------------

function WindowRow({
  window,
  onSave,
  onToggle,
  onDelete,
  saving,
}: {
  window: AvailabilityWindow;
  onSave: (id: string, patch: { start_time: string; end_time: string; slot_duration_minutes: number }) => void;
  onToggle: (id: string, isActive: boolean) => void;
  onDelete: (id: string) => void;
  saving: boolean;
}) {
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
        aria-label="Start time"
      />
      <span className="text-dreams-textSecondary text-sm">–</span>
      <input
        type="time"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        className={inputCls}
        aria-label="End time"
      />
      <select
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        className={inputCls}
        aria-label="Slot duration"
      >
        {SLOT_DURATIONS.map((d) => (
          <option key={d} value={d}>
            {d} min slots
          </option>
        ))}
      </select>
      <label className="flex items-center gap-1.5 text-sm text-dreams-textSecondary cursor-pointer">
        <input
          type="checkbox"
          checked={window.is_active}
          onChange={(e) => onToggle(window.id, e.target.checked)}
          className="h-4 w-4 rounded border-dreams-border text-dreams-blue focus:ring-dreams-blue/30"
        />
        Active
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
          Save
        </button>
      )}
      <button
        onClick={() => onDelete(window.id)}
        className="ml-auto text-gray-400 hover:text-red-500"
        aria-label="Delete window"
        title="Delete window"
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
  onSubmit,
  onCancel,
  saving,
}: {
  weekday: number;
  onSubmit: (data: {
    weekday: number;
    start_time: string;
    end_time: string;
    slot_duration_minutes: number;
  }) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("17:00");
  const [duration, setDuration] = useState(15);

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg bg-dreams-lightBg p-2 mt-1.5">
      <input
        type="time"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        className={inputCls}
        aria-label="Start time"
      />
      <span className="text-dreams-textSecondary text-sm">–</span>
      <input
        type="time"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        className={inputCls}
        aria-label="End time"
      />
      <select
        value={duration}
        onChange={(e) => setDuration(Number(e.target.value))}
        className={inputCls}
        aria-label="Slot duration"
      >
        {SLOT_DURATIONS.map((d) => (
          <option key={d} value={d}>
            {d} min slots
          </option>
        ))}
      </select>
      <button
        onClick={() =>
          onSubmit({
            weekday,
            start_time: start,
            end_time: end,
            slot_duration_minutes: duration,
          })
        }
        disabled={saving}
        className="h-8 rounded-lg bg-dreams-blue px-3 text-xs font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
      >
        Add
      </button>
      <button
        onClick={onCancel}
        className="text-gray-400 hover:text-gray-600"
        aria-label="Cancel"
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
  const queryClient = useQueryClient();
  const [addingFor, setAddingFor] = useState<number | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const windowsQuery = useQuery({
    queryKey: ["my-availability"],
    queryFn: getMyAvailability,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["my-availability"] });
  };

  const createWindowMutation = useMutation({
    mutationFn: createAvailabilityWindow,
    onSuccess: () => {
      setAddingFor(null);
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e)),
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
    onError: (e) => setPageError(errorMessage(e)),
  });

  const deleteWindowMutation = useMutation({
    mutationFn: deleteAvailabilityWindow,
    onSuccess: () => {
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e)),
  });

  const windows = windowsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Schedule" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Schedule</h1>
        <p className="text-dreams-textSecondary mt-1">
          Set your weekly availability and leave days. These windows define the
          bookable appointment slots patients see.
        </p>
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
          Failed to load your schedule — the grid below may be stale.{" "}
          <button
            className="underline font-medium"
            onClick={() => windowsQuery.refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Weekly availability editor */}
      <div className="rounded-xl border border-dreams-border bg-white">
        <div className="flex items-center gap-2 border-b border-dreams-border px-5 py-4">
          <CalendarDays className="h-5 w-5 text-dreams-blue" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Weekly Availability
          </h2>
        </div>
        <div className="divide-y divide-dreams-border">
          {WEEKDAYS.map((label, weekday) => {
            const dayWindows = windows.filter((w) => w.weekday === weekday);
            return (
              <div key={weekday} className="px-5 py-3">
                <div className="flex items-start gap-4">
                  <div className="w-24 shrink-0 pt-2 text-sm font-medium text-dreams-textPrimary">
                    {label}
                  </div>
                  <div className="flex-1">
                    {dayWindows.length === 0 && addingFor !== weekday && (
                      <p className="py-1.5 text-sm text-dreams-textSecondary">
                        Not available
                      </p>
                    )}
                    {dayWindows.map((w) => (
                      <WindowRow
                        key={w.id}
                        window={w}
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
                        saving={createWindowMutation.isPending}
                        onSubmit={(data) => createWindowMutation.mutate(data)}
                        onCancel={() => setAddingFor(null)}
                      />
                    ) : (
                      <button
                        onClick={() => setAddingFor(weekday)}
                        className="mt-1 flex items-center gap-1 text-xs font-medium text-dreams-blue hover:underline"
                      >
                        <Plus className="h-3.5 w-3.5" /> Add window
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Leave days */}
      <DoctorLeavesCard />
    </div>
  );
}

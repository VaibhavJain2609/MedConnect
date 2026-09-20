"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Plus, Trash2, X } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  getMyAvailability,
  createAvailabilityWindow,
  updateAvailabilityWindow,
  deleteAvailabilityWindow,
  getMyLeaves,
  createLeave,
  deleteLeave,
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
  const [leaveDate, setLeaveDate] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);

  const windowsQuery = useQuery({
    queryKey: ["my-availability"],
    queryFn: getMyAvailability,
  });
  const leavesQuery = useQuery({
    queryKey: ["my-leaves"],
    queryFn: getMyLeaves,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["my-availability"] });
    queryClient.invalidateQueries({ queryKey: ["my-leaves"] });
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

  const createLeaveMutation = useMutation({
    mutationFn: createLeave,
    onSuccess: () => {
      setLeaveDate("");
      setLeaveReason("");
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e)),
  });

  const deleteLeaveMutation = useMutation({
    mutationFn: deleteLeave,
    onSuccess: () => {
      setPageError(null);
      invalidate();
    },
    onError: (e) => setPageError(errorMessage(e)),
  });

  const windows = windowsQuery.data ?? [];
  const leaves = (leavesQuery.data ?? []).slice().sort((a, b) => a.date.localeCompare(b.date));

  const formatLeaveDate = (iso: string) =>
    new Date(iso + "T00:00:00").toLocaleDateString("en-IN", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });

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
      {(windowsQuery.isError || leavesQuery.isError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load your schedule — the grid below may be stale.{" "}
          <button
            className="underline font-medium"
            onClick={() => { windowsQuery.refetch(); leavesQuery.refetch(); }}
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
      <div className="rounded-xl border border-dreams-border bg-white">
        <div className="border-b border-dreams-border px-5 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Leave Days
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-0.5">
            Full days off — no slots are bookable on these dates.
          </p>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              value={leaveDate}
              onChange={(e) => setLeaveDate(e.target.value)}
              className={inputCls}
              aria-label="Leave date"
            />
            <input
              type="text"
              value={leaveReason}
              onChange={(e) => setLeaveReason(e.target.value)}
              placeholder="Reason (optional)"
              maxLength={255}
              className={`${inputCls} w-64`}
              aria-label="Leave reason"
            />
            <button
              onClick={() =>
                leaveDate &&
                createLeaveMutation.mutate({
                  date: leaveDate,
                  reason: leaveReason || null,
                })
              }
              disabled={!leaveDate || createLeaveMutation.isPending}
              className="h-9 rounded-lg bg-dreams-blue px-4 text-sm font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
            >
              Add leave
            </button>
          </div>

          {leavesQuery.isLoading ? (
            <p className="text-sm text-dreams-textSecondary">Loading…</p>
          ) : leaves.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">
              No upcoming leave days.
            </p>
          ) : (
            <ul className="divide-y divide-dreams-border">
              {leaves.map((leave) => (
                <li
                  key={leave.id}
                  className="flex items-center gap-3 py-2.5 text-sm"
                >
                  <span className="font-medium text-dreams-textPrimary">
                    {formatLeaveDate(leave.date)}
                  </span>
                  {leave.reason && (
                    <span className="text-dreams-textSecondary">
                      — {leave.reason}
                    </span>
                  )}
                  <button
                    onClick={() => deleteLeaveMutation.mutate(leave.id)}
                    className="ml-auto text-gray-400 hover:text-red-500"
                    aria-label="Remove leave"
                    title="Remove leave"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

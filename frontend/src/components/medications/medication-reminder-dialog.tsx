"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { BellRing } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  deleteMedicationReminder,
  updateMedicationReminder,
  upsertMedicationReminder,
  type MedicationReminder,
} from "@/lib/api/medication-reminders";
import { cn } from "@/lib/utils";

/** Fixed preset chips — values are the "HH:MM" strings the backend stores. */
const PRESETS = [
  { key: "morning", time: "08:00" },
  { key: "afternoon", time: "13:00" },
  { key: "evening", time: "18:00" },
  { key: "night", time: "21:00" },
] as const;

interface MedicationReminderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prescriptionId: string;
  /** Medicine name shown in the description line. */
  medName: string;
  /** Existing reminder for this prescription, if any. */
  existing: MedicationReminder | null;
  /** Called after a successful save/remove so the page can refetch. */
  onSaved: () => void;
}

/**
 * "Remind me" panel: pick preset times-of-day and enable/disable reminders
 * for one prescription. Upserts via POST (or PATCH when a reminder already
 * exists); "turn off" soft-deletes the row.
 */
export function MedicationReminderDialog({
  open,
  onOpenChange,
  prescriptionId,
  medName,
  existing,
  onSaved,
}: MedicationReminderDialogProps) {
  const t = useTranslations("medReminders");
  const [times, setTimes] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [validationError, setValidationError] = useState(false);

  // Reset local state whenever the dialog opens for a (possibly different)
  // prescription.
  useEffect(() => {
    if (open) {
      setTimes(existing?.times_of_day ?? []);
      setEnabled(existing?.enabled ?? true);
      setValidationError(false);
    }
  }, [open, existing]);

  const toggleTime = (time: string) =>
    setTimes((prev) =>
      prev.includes(time) ? prev.filter((x) => x !== time) : [...prev, time]
    );

  const saveMutation = useMutation({
    mutationFn: () =>
      existing
        ? updateMedicationReminder(existing.id, {
            times_of_day: times,
            enabled,
          })
        : upsertMedicationReminder({
            prescription_id: prescriptionId,
            times_of_day: times,
            enabled,
          }),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
  });

  const removeMutation = useMutation({
    mutationFn: () => deleteMedicationReminder(existing!.id),
    onSuccess: () => {
      onSaved();
      onOpenChange(false);
    },
  });

  const busy = saveMutation.isPending || removeMutation.isPending;

  const handleSave = () => {
    if (times.length === 0) {
      setValidationError(true);
      return;
    }
    saveMutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BellRing className="h-4 w-4 text-dreams-blue" aria-hidden />
            {t("dialogTitle")}
          </DialogTitle>
          <DialogDescription>
            {t("dialogDescription", { name: medName })}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium text-dreams-textPrimary mb-2">
              {t("pickTimes")}
            </p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => {
                const selected = times.includes(p.time);
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => toggleTime(p.time)}
                    aria-pressed={selected}
                    className={cn(
                      "px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
                      selected
                        ? "bg-dreams-blue text-white border-dreams-blue"
                        : "bg-dreams-lightBg text-dreams-textSecondary border-dreams-border hover:text-dreams-textPrimary"
                    )}
                  >
                    {t(p.key)} · {p.time}
                  </button>
                );
              })}
            </div>
            {validationError && times.length === 0 && (
              <p className="text-xs text-red-600 mt-2">{t("needOneTime")}</p>
            )}
          </div>

          <label className="flex items-center gap-2 text-sm text-dreams-textPrimary cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-dreams-border text-dreams-blue focus:ring-dreams-blue"
            />
            {t("enableLabel")}
          </label>

          {(saveMutation.isError || removeMutation.isError) && (
            <p className="text-sm text-red-600">{t("saveFailed")}</p>
          )}
        </div>

        <DialogFooter className="gap-2">
          {existing && (
            <Button
              variant="outline"
              onClick={() => removeMutation.mutate()}
              disabled={busy}
              className="mr-auto text-red-600 border-red-200 hover:bg-red-50"
            >
              {t("turnOff")}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            {t("cancel")}
          </Button>
          <Button onClick={handleSave} disabled={busy}>
            {saveMutation.isPending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

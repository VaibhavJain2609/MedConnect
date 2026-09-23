"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Save, Settings } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
  getPlatformSettings,
  PlatformSetting,
  updatePlatformSetting,
} from "@/lib/api/platform-settings";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const REMINDER_CHANNEL_KEYS = [
  "in_app",
  "email",
  "sms",
  "whatsapp",
  "push",
] as const;

const BOOLEAN_KEYS = new Set(["maintenance_mode", "registration_enabled"]);
const NUMBER_KEYS = new Set(["max_upload_mb"]);

// Display order for known keys; anything else sorts alphabetically after.
const KNOWN_ORDER = [
  "maintenance_mode",
  "registration_enabled",
  "reminder_channels_enabled",
  "max_upload_mb",
];

function formatKey(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
        checked ? "bg-dreams-blue" : "bg-gray-300"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

function SettingCard({
  setting,
  onSaved,
}: {
  setting: PlatformSetting;
  onSaved: () => void;
}) {
  const t = useTranslations("adminSettings");
  const tCommon = useTranslations("common");
  const [draft, setDraft] = useState<unknown>(setting.value);
  const [jsonText, setJsonText] = useState(
    JSON.stringify(setting.value, null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmMaintenanceOpen, setConfirmMaintenanceOpen] = useState(false);

  // Re-sync local state when the server value changes (e.g. after refetch) —
  // adjusted during render via the prev-value pattern.
  const [prevValue, setPrevValue] = useState(setting.value);
  if (prevValue !== setting.value) {
    setPrevValue(setting.value);
    setDraft(setting.value);
    setJsonText(JSON.stringify(setting.value, null, 2));
    setJsonError(null);
  }

  const isKnownBool = BOOLEAN_KEYS.has(setting.key);
  const isKnownNumber = NUMBER_KEYS.has(setting.key);
  const isReminderChannels = setting.key === "reminder_channels_enabled";
  const isMaintenance = setting.key === "maintenance_mode";
  const isTyped = isKnownBool || isKnownNumber || isReminderChannels;

  const channels =
    isReminderChannels && typeof draft === "object" && draft !== null
      ? (draft as Record<string, boolean>)
      : {};

  const performSave = async (value: unknown) => {
    setSaving(true);
    try {
      await updatePlatformSetting(setting.key, value);
      toast({
        title: t("toasts.savedTitle"),
        description: t("toasts.savedDesc", { key: setting.key }),
      });
      onSaved();
    } catch (err) {
      toast({
        title: t("toasts.saveFailedTitle"),
        description:
          (err as { userMessage?: string })?.userMessage || (err instanceof Error ? err.message : t("toasts.saveFailedFallback")),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    let value = draft;
    if (!isTyped) {
      try {
        value = JSON.parse(jsonText);
      } catch {
        setJsonError(t("toasts.invalidJson"));
        return;
      }
      setJsonError(null);
    }
    if (isKnownNumber) {
      if (typeof value !== "number" || !Number.isFinite(value)) {
        toast({
          title: t("toasts.invalidValueTitle"),
          description: t("toasts.mustBeNumber", { key: setting.key }),
          variant: "destructive",
        });
        return;
      }
      if (setting.key === "max_upload_mb" && (value < 1 || value > 50)) {
        toast({
          title: t("toasts.invalidValueTitle"),
          description: t("toasts.uploadRange"),
          variant: "destructive",
        });
        return;
      }
    }
    // Turning maintenance mode ON is destructive — require confirmation.
    if (isMaintenance && value === true && setting.value !== true) {
      setConfirmMaintenanceOpen(true);
      return;
    }
    void performSave(value);
  };

  return (
    <div className="bg-white rounded-xl border border-dreams-border shadow-card p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-dreams-textPrimary">
            {formatKey(setting.key)}
          </h2>
          <p className="text-xs font-mono text-dreams-textSecondary">
            {setting.key}
          </p>
          {setting.description && (
            <p className="text-sm text-dreams-textSecondary mt-1">
              {setting.description}
            </p>
          )}
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dreams-blue text-white text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? t("saving") : t("save")}
        </button>
      </div>

      {isKnownBool && (
        <div className="flex items-center gap-3">
          <Toggle
            checked={draft === true}
            onChange={setDraft}
            disabled={saving}
            label={formatKey(setting.key)}
          />
          <span className="text-sm text-dreams-textPrimary">
            {draft === true ? t("enabled") : t("disabled")}
          </span>
        </div>
      )}

      {isMaintenance && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-800">
            {t("maintenanceWarning")}
          </p>
        </div>
      )}

      {isKnownNumber && (
        <input
          type="number"
          min={1}
          max={50}
          aria-label={formatKey(setting.key)}
          value={typeof draft === "number" ? draft : ""}
          onChange={(e) =>
            setDraft(e.target.value === "" ? null : Number(e.target.value))
          }
          className="h-10 w-40 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      )}

      {isReminderChannels && (
        <div className="flex flex-wrap gap-4">
          {REMINDER_CHANNEL_KEYS.map((key) => (
            <label
              key={key}
              className="flex items-center gap-2 text-sm text-dreams-textPrimary cursor-pointer"
            >
              <input
                type="checkbox"
                checked={channels[key] === true}
                onChange={(e) =>
                  setDraft({ ...channels, [key]: e.target.checked })
                }
                className="h-4 w-4 rounded border-dreams-border accent-dreams-blue"
              />
              {t(`channels.${key}`)}
            </label>
          ))}
        </div>
      )}

      {!isTyped && (
        <div>
          <textarea
            aria-label={t("jsonValueAria", { label: formatKey(setting.key) })}
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setJsonError(null);
            }}
            rows={Math.min(8, jsonText.split("\n").length + 1)}
            spellCheck={false}
            className="w-full px-3 py-2 rounded-lg border border-dreams-border bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-dreams-blue resize-y"
          />
          {jsonError && (
            <p className="text-xs text-red-600 mt-1">{jsonError}</p>
          )}
        </div>
      )}

      <p className="text-xs text-dreams-textSecondary">
        {t("lastUpdated", { datetime: formatDateTime(setting.updated_at) })}
      </p>

      <AlertDialog
        open={confirmMaintenanceOpen}
        onOpenChange={setConfirmMaintenanceOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("maintenanceDialog.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("maintenanceDialog.desc")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void performSave(true)}
              className="bg-dreams-blue text-white hover:opacity-90"
            >
              {t("maintenanceDialog.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function AdminSettingsPage() {
  const t = useTranslations("adminSettings");
  const tCommon = useTranslations("common");
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<PlatformSetting[]>({
    queryKey: ["admin-platform-settings"],
    queryFn: getPlatformSettings,
  });

  const settings = [...(data ?? [])].sort((a, b) => {
    const ia = KNOWN_ORDER.indexOf(a.key);
    const ib = KNOWN_ORDER.indexOf(b.key);
    if (ia !== -1 || ib !== -1) {
      return (ia === -1 ? KNOWN_ORDER.length : ia) -
        (ib === -1 ? KNOWN_ORDER.length : ib);
    }
    return a.key.localeCompare(b.key);
  });

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-platform-settings"] });
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: t("breadcrumbDashboard"), href: "/admin/dashboard" },
          { label: t("breadcrumb") },
        ]}
      />

      <div className="flex items-center gap-3">
        <Settings className="h-7 w-7 text-dreams-blue" />
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-dreams-textSecondary mt-0.5">
            {t("subtitle")}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : error ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 text-center">
          <p className="text-red-600 font-medium">{t("loadError")}</p>
          <p className="text-dreams-textSecondary text-sm mt-1">
            {error instanceof Error ? error.message : tCommon("errorGeneric")}
          </p>
        </div>
      ) : settings.length === 0 ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 text-center">
          <p className="text-dreams-textSecondary">{t("empty")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {settings.map((s) => (
            <SettingCard key={s.key} setting={s} onSaved={handleSaved} />
          ))}
        </div>
      )}
    </div>
  );
}

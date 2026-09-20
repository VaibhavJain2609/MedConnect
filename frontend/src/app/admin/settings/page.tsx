"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Settings } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
  getPlatformSettings,
  PlatformSetting,
  updatePlatformSetting,
} from "@/lib/api/admin-broadcast";
import { Breadcrumb } from "@/components/ui/breadcrumb";

const REMINDER_CHANNELS = [
  { key: "in_app", label: "In-app" },
  { key: "email", label: "Email" },
  { key: "sms", label: "SMS" },
  { key: "whatsapp", label: "WhatsApp" },
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
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
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
  const [draft, setDraft] = useState<unknown>(setting.value);
  const [jsonText, setJsonText] = useState(
    JSON.stringify(setting.value, null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Re-sync local state when the server value changes (e.g. after refetch).
  useEffect(() => {
    setDraft(setting.value);
    setJsonText(JSON.stringify(setting.value, null, 2));
    setJsonError(null);
  }, [setting.value]);

  const isKnownBool = BOOLEAN_KEYS.has(setting.key);
  const isKnownNumber = NUMBER_KEYS.has(setting.key);
  const isReminderChannels = setting.key === "reminder_channels_enabled";
  const isTyped = isKnownBool || isKnownNumber || isReminderChannels;

  const channels =
    isReminderChannels && typeof draft === "object" && draft !== null
      ? (draft as Record<string, boolean>)
      : {};

  const handleSave = async () => {
    let value = draft;
    if (!isTyped) {
      try {
        value = JSON.parse(jsonText);
      } catch {
        setJsonError("Invalid JSON — fix the value before saving.");
        return;
      }
      setJsonError(null);
    }
    setSaving(true);
    try {
      await updatePlatformSetting(setting.key, value);
      toast({ title: "Setting saved", description: `${setting.key} updated.` });
      onSaved();
    } catch (err) {
      toast({
        title: "Save failed",
        description:
          err instanceof Error ? err.message : "Could not update the setting.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-dreams-border shadow-card p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-dreams-textPrimary">
            {formatKey(setting.key)}
          </h3>
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
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {isKnownBool && (
        <div className="flex items-center gap-3">
          <Toggle
            checked={draft === true}
            onChange={setDraft}
            disabled={saving}
          />
          <span className="text-sm text-dreams-textPrimary">
            {draft === true ? "Enabled" : "Disabled"}
          </span>
        </div>
      )}

      {isKnownNumber && (
        <input
          type="number"
          min={1}
          value={typeof draft === "number" ? draft : ""}
          onChange={(e) =>
            setDraft(e.target.value === "" ? null : Number(e.target.value))
          }
          className="h-10 w-40 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      )}

      {isReminderChannels && (
        <div className="flex flex-wrap gap-4">
          {REMINDER_CHANNELS.map((ch) => (
            <label
              key={ch.key}
              className="flex items-center gap-2 text-sm text-dreams-textPrimary cursor-pointer"
            >
              <input
                type="checkbox"
                checked={channels[ch.key] === true}
                onChange={(e) =>
                  setDraft({ ...channels, [ch.key]: e.target.checked })
                }
                className="h-4 w-4 rounded border-dreams-border accent-dreams-blue"
              />
              {ch.label}
            </label>
          ))}
        </div>
      )}

      {!isTyped && (
        <div>
          <textarea
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
        Last updated: {formatDateTime(setting.updated_at)}
      </p>
    </div>
  );
}

export default function AdminSettingsPage() {
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
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Settings" },
        ]}
      />

      <div className="flex items-center gap-3">
        <Settings className="h-7 w-7 text-dreams-blue" />
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Settings</h1>
          <p className="text-dreams-textSecondary mt-0.5">
            Platform configuration and feature flags
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : error ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 text-center">
          <p className="text-red-600 font-medium">Failed to load settings</p>
          <p className="text-dreams-textSecondary text-sm mt-1">
            {error instanceof Error ? error.message : "An error occurred"}
          </p>
        </div>
      ) : settings.length === 0 ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 text-center">
          <p className="text-dreams-textSecondary">No settings configured</p>
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

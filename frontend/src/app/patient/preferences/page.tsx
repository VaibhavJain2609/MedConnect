"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { BellOff } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
  type NotificationPreferencesUpdate,
} from "@/lib/api/notifications";
import {
  disablePushNotifications,
  enablePushNotifications,
  getPushPermission,
  getPushSubscription,
  pushSupported,
} from "@/lib/push";

const PREFERENCES_QUERY_KEY = ["notification-preferences"];

// Mirrors DEFAULT_NOTIFICATION_PREFERENCES in backend/app/routers/notifications.py.
// Merged over API data defensively since older rows may lack newer keys.
const DEFAULT_PREFERENCES: NotificationPreferences = {
  email_notifications: true,
  push_notifications: true,
  sms_notifications: false,
  whatsapp_notifications: false,
  appointment_reminders: true,
  queue_updates: true,
  lab_results: true,
  prescription_alerts: true,
  system_alerts: true,
};

// labelKey/descriptionKey values double as message keys under the
// `preferences` namespace — keep them in sync with messages/en.json +
// hi.json (the parity test guards en↔hi; the type below guards en↔code).
type EnMessages = typeof import("../../../../messages/en.json");
type PreferencesMessages = EnMessages["preferences"];
type PreferencesKey = {
  [K in keyof PreferencesMessages & string]: PreferencesMessages[K] extends string
    ? K
    : `${K}.${keyof PreferencesMessages[K] & string}`;
}[keyof PreferencesMessages & string];

interface PreferenceItem {
  key: keyof NotificationPreferences;
  labelKey: PreferencesKey;
  descriptionKey: PreferencesKey;
}

// Channel toggles — keys map to CHANNEL_PREF_KEYS in
// backend/app/services/notification_channels.py. in_app has no pref key by
// design (baseline channel) and is rendered separately as always-on.
const CHANNEL_ITEMS: PreferenceItem[] = [
  {
    key: "email_notifications",
    labelKey: "channels.email",
    descriptionKey: "channels.emailDesc",
  },
  {
    key: "push_notifications",
    labelKey: "channels.push",
    descriptionKey: "channels.pushDesc",
  },
  {
    key: "sms_notifications",
    labelKey: "channels.sms",
    descriptionKey: "channels.smsDesc",
  },
  {
    key: "whatsapp_notifications",
    labelKey: "channels.whatsapp",
    descriptionKey: "channels.whatsappDesc",
  },
];

const TYPE_ITEMS: PreferenceItem[] = [
  {
    key: "appointment_reminders",
    labelKey: "types.appointmentReminders",
    descriptionKey: "types.appointmentRemindersDesc",
  },
  {
    key: "queue_updates",
    labelKey: "types.queueUpdates",
    descriptionKey: "types.queueUpdatesDesc",
  },
  {
    key: "lab_results",
    labelKey: "types.labResults",
    descriptionKey: "types.labResultsDesc",
  },
  {
    key: "prescription_alerts",
    labelKey: "types.prescriptionAlerts",
    descriptionKey: "types.prescriptionAlertsDesc",
  },
  {
    key: "system_alerts",
    labelKey: "types.systemAlerts",
    descriptionKey: "types.systemAlertsDesc",
  },
];

type PreferencesT = ReturnType<typeof useTranslations<"preferences">>;

function PreferenceToggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
        checked ? "bg-dreams-blue" : "bg-gray-300"
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-[22px]" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

function PreferenceRow({
  item,
  checked,
  disabled,
  onChange,
  t,
}: {
  item: PreferenceItem;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  t: PreferencesT;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-dreams-textPrimary">
          {t(item.labelKey)}
        </p>
        <p className="text-xs text-dreams-textSecondary mt-0.5">
          {t(item.descriptionKey)}
        </p>
      </div>
      <PreferenceToggle checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  );
}

/**
 * "This device" push subscription control — registers the browser's
 * PushManager subscription with the backend (distinct from the "Push"
 * channel toggle, which only gates dispatch preference). Shows the live
 * subscription status plus a hint when the browser has denied the
 * notification permission (sticky until the user re-allows it in site
 * settings).
 */
function PushDeviceControl({ t }: { t: PreferencesT }) {
  // null = still probing, "unsupported" hides the control entirely.
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [permission, setPermission] = useState<
    NotificationPermission | "unsupported"
  >("unsupported");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // `subscribed` stays null (control hidden) when push is unsupported.
    if (!pushSupported()) return;
    setPermission(getPushPermission());
    let cancelled = false;
    getPushSubscription()
      .then((sub) => {
        if (!cancelled) setSubscribed(sub !== null);
      })
      .catch(() => {
        if (!cancelled) setSubscribed(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (subscribed === null) return null;

  const denied = permission === "denied";

  const handleClick = async () => {
    setBusy(true);
    try {
      if (subscribed) {
        await disablePushNotifications();
        setSubscribed(false);
        toast({
          title: t("pushDevice.disabledToast"),
          description: t("pushDevice.disabledToastDesc"),
        });
      } else {
        const ok = await enablePushNotifications();
        setSubscribed(ok);
        setPermission(getPushPermission());
        toast(
          ok
            ? {
                title: t("pushDevice.enabledToast"),
                description: t("pushDevice.enabledToastDesc"),
              }
            : {
                title: t("pushDevice.notEnabledToast"),
                description: t("pushDevice.notEnabledToastDesc"),
                variant: "destructive",
              }
        );
      }
    } catch {
      toast({
        title: t("pushDevice.failedToast"),
        description: t("pushDevice.failedToastDesc"),
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="py-3">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-dreams-textPrimary">
              {t("pushDevice.title")}
            </p>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                subscribed
                  ? "bg-status-completed/10 text-status-completed"
                  : "bg-gray-100 text-dreams-textSecondary"
              )}
            >
              {subscribed
                ? t("pushDevice.statusSubscribed")
                : t("pushDevice.statusNotSubscribed")}
            </span>
          </div>
          <p className="text-xs text-dreams-textSecondary mt-0.5">
            {subscribed
              ? t("pushDevice.subscribed")
              : t("pushDevice.notSubscribed")}
          </p>
        </div>
        <button
          type="button"
          onClick={handleClick}
          disabled={busy || (!subscribed && denied)}
          className={cn(
            "h-9 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 shrink-0",
            subscribed
              ? "border border-dreams-border text-dreams-textPrimary hover:bg-gray-50"
              : "bg-dreams-blue text-white hover:bg-dreams-blue/90"
          )}
        >
          {busy
            ? t("pushDevice.working")
            : subscribed
              ? t("pushDevice.disable")
              : t("pushDevice.enable")}
        </button>
      </div>
      {denied && (
        <p className="text-xs text-status-overdue mt-2">
          {t("pushDevice.deniedHint")}
        </p>
      )}
    </div>
  );
}

export default function PatientPreferencesPage() {
  const t = useTranslations("preferences");
  const queryClient = useQueryClient();

  // Mark the "Set notification preferences" onboarding-checklist item done.
  useEffect(() => {
    try {
      window.localStorage.setItem("pt-onboarding-prefs-visited", "1");
    } catch {
      // localStorage unavailable — non-fatal
    }
  }, []);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: getNotificationPreferences,
  });

  const preferences: NotificationPreferences = { ...DEFAULT_PREFERENCES, ...data };

  const mutation = useMutation({
    mutationFn: (update: NotificationPreferencesUpdate) =>
      updateNotificationPreferences(update),
    onMutate: async (update) => {
      await queryClient.cancelQueries({ queryKey: PREFERENCES_QUERY_KEY });
      const previous =
        queryClient.getQueryData<NotificationPreferences>(PREFERENCES_QUERY_KEY);
      queryClient.setQueryData<NotificationPreferences>(
        PREFERENCES_QUERY_KEY,
        (old) => ({ ...DEFAULT_PREFERENCES, ...old, ...update })
      );
      return { previous };
    },
    onError: (_error, _update, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(PREFERENCES_QUERY_KEY, context.previous);
      }
      toast({
        title: t("saveFailed"),
        description: t("saveFailedDesc"),
        variant: "destructive",
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY });
    },
  });

  const handleToggle = (key: keyof NotificationPreferences, next: boolean) => {
    mutation.mutate({ [key]: next });
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" label={t("loading")} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: t("title") }]} />
        <EmptyState
          icon={BellOff}
          title={t("loadError")}
          description={t("loadErrorDesc")}
          action={
            <button
              onClick={() => refetch()}
              className="h-10 px-6 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 transition-colors"
            >
              {t("tryAgain")}
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("title") }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          {t("title")}
        </h1>
        <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* Channels */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            {t("channels.title")}
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-3">
            {t("channels.description")}
          </p>
          <div className="divide-y divide-dreams-border">
            {/* In-app is the baseline channel — no pref key exists, so it
                renders as an informational always-on row. */}
            <div className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-dreams-textPrimary">
                  {t("channels.inApp")}
                </p>
                <p className="text-xs text-dreams-textSecondary mt-0.5">
                  {t("channels.inAppDesc")}
                </p>
              </div>
              <PreferenceToggle checked disabled onChange={() => {}} />
            </div>
            {CHANNEL_ITEMS.map((item) => (
              <PreferenceRow
                key={item.key}
                item={item}
                checked={preferences[item.key]}
                onChange={(next) => handleToggle(item.key, next)}
                t={t}
              />
            ))}
            <PushDeviceControl t={t} />
          </div>
        </div>

        {/* Types */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            {t("types.title")}
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-3">
            {t("types.description")}
          </p>
          <div className="divide-y divide-dreams-border">
            {TYPE_ITEMS.map((item) => (
              <PreferenceRow
                key={item.key}
                item={item}
                checked={preferences[item.key]}
                onChange={(next) => handleToggle(item.key, next)}
                t={t}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

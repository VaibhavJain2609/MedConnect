"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  lab_results: true,
  prescription_alerts: true,
  system_alerts: true,
};

interface PreferenceItem {
  key: keyof NotificationPreferences;
  label: string;
  description: string;
}

const CHANNEL_ITEMS: PreferenceItem[] = [
  {
    key: "email_notifications",
    label: "Email",
    description: "Receive notifications at your account email address.",
  },
  {
    key: "push_notifications",
    label: "Push",
    description: "Browser and device push notifications.",
  },
  {
    key: "sms_notifications",
    label: "SMS",
    description: "Text messages to your phone. Off by default.",
  },
  {
    key: "whatsapp_notifications",
    label: "WhatsApp",
    description: "WhatsApp messages to your phone. Off by default.",
  },
];

const TYPE_ITEMS: PreferenceItem[] = [
  {
    key: "appointment_reminders",
    label: "Appointment reminders",
    description: "Reminders before upcoming appointments.",
  },
  {
    key: "lab_results",
    label: "Lab results",
    description: "Alerts when new lab results are available.",
  },
  {
    key: "prescription_alerts",
    label: "Prescription alerts",
    description: "Notifications about new or updated prescriptions.",
  },
  {
    key: "system_alerts",
    label: "System alerts",
    description: "Important account and platform announcements.",
  },
];

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
}: {
  item: PreferenceItem;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-dreams-textPrimary">{item.label}</p>
        <p className="text-xs text-dreams-textSecondary mt-0.5">{item.description}</p>
      </div>
      <PreferenceToggle checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  );
}

/**
 * "This device" push subscription control — registers the browser's
 * PushManager subscription with the backend (distinct from the "Push"
 * channel toggle, which only gates dispatch preference).
 */
function PushDeviceControl() {
  // null = still probing, "unsupported" hides the control entirely.
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!pushSupported()) {
      setSubscribed(null);
      return;
    }
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

  const handleClick = async () => {
    setBusy(true);
    try {
      if (subscribed) {
        await disablePushNotifications();
        setSubscribed(false);
        toast({ title: "Push disabled", description: "This device will no longer receive push notifications." });
      } else {
        const ok = await enablePushNotifications();
        setSubscribed(ok);
        toast(
          ok
            ? { title: "Push enabled", description: "This device will now receive notifications." }
            : {
                title: "Push not enabled",
                description: "Push is unavailable or permission was denied.",
                variant: "destructive",
              }
        );
      }
    } catch {
      toast({
        title: "Push setup failed",
        description: "Could not update push notifications. Please try again.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-dreams-textPrimary">This device</p>
        <p className="text-xs text-dreams-textSecondary mt-0.5">
          {subscribed
            ? "Push notifications are enabled on this browser."
            : "Enable browser push notifications on this device."}
        </p>
      </div>
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className={cn(
          "h-9 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 shrink-0",
          subscribed
            ? "border border-dreams-border text-dreams-textPrimary hover:bg-gray-50"
            : "bg-dreams-blue text-white hover:bg-dreams-blue/90"
        )}
      >
        {busy ? "Working…" : subscribed ? "Disable push" : "Enable push"}
      </button>
    </div>
  );
}

export default function PatientPreferencesPage() {
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
        title: "Failed to save preferences",
        description: "Your change was not saved. Please try again.",
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
        <Spinner size="lg" label="Loading preferences" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: "Preferences" }]} />
        <EmptyState
          icon={BellOff}
          title="Couldn't load notification preferences"
          description="Something went wrong while loading your preferences."
          action={
            <button
              onClick={() => refetch()}
              className="h-10 px-6 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 transition-colors"
            >
              Try again
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Preferences" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          Notification Preferences
        </h1>
        <p className="text-dreams-textSecondary mt-1">
          Choose how you want to be notified. Changes save automatically.
        </p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* Channels */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Channels
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-3">
            Where your notifications are delivered.
          </p>
          <div className="divide-y divide-dreams-border">
            {CHANNEL_ITEMS.map((item) => (
              <PreferenceRow
                key={item.key}
                item={item}
                checked={preferences[item.key]}
                onChange={(next) => handleToggle(item.key, next)}
              />
            ))}
            <PushDeviceControl />
          </div>
        </div>

        {/* Types */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Notification Types
          </h2>
          <p className="text-sm text-dreams-textSecondary mt-3">
            What you want to be notified about.
          </p>
          <div className="divide-y divide-dreams-border">
            {TYPE_ITEMS.map((item) => (
              <PreferenceRow
                key={item.key}
                item={item}
                checked={preferences[item.key]}
                onChange={(next) => handleToggle(item.key, next)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

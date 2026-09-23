"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, RotateCcw, Trash2, Webhook } from "lucide-react";
import {
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  listWebhookDeliveries,
  listWebhookEndpoints,
  redeliverFailedDeliveries,
  redeliverWebhookDelivery,
  updateWebhookEndpoint,
  WEBHOOK_EVENT_TYPES,
  type WebhookDeliveryStatus,
  type WebhookEndpoint,
} from "@/lib/api/webhooks";
import { getClinicMembers } from "@/lib/api/clinics";
import { useClinicStore } from "@/stores/clinic-store";
import { useAuthStore } from "@/stores/auth-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

const STATUS_BADGE: Record<WebhookDeliveryStatus, string> = {
  sent: "completed",
  failed: "overdue",
  pending: "pending",
};

function truncate(text: string, n: number): string {
  return text.length > n ? `${text.slice(0, n)}…` : text;
}

export default function ClinicWebhooksPage() {
  const t = useTranslations("clinicWebhooks");
  const { activeClinicId } = useClinicStore();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [url, setUrl] = useState("");
  const [checkedEvents, setCheckedEvents] = useState<Set<string>>(new Set());
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(null);

  const { data: membersData } = useQuery({
    queryKey: ["clinic-members", activeClinicId],
    queryFn: () => getClinicMembers(activeClinicId!),
    enabled: !!activeClinicId && !!user,
  });
  const myRole = membersData?.data.find((m) => m.user_id === user?.id)?.role;
  const canManage = myRole === "owner" || myRole === "admin";

  const {
    data: endpoints,
    isLoading: endpointsLoading,
    isError: endpointsError,
  } = useQuery({
    queryKey: ["webhook-endpoints", activeClinicId],
    queryFn: () => listWebhookEndpoints(activeClinicId!),
    enabled: !!activeClinicId && canManage,
  });

  const selectedEndpoint: WebhookEndpoint | undefined =
    endpoints?.find((e) => e.id === selectedEndpointId) ?? endpoints?.[0];

  const {
    data: deliveries,
    isLoading: deliveriesLoading,
    isError: deliveriesError,
  } = useQuery({
    queryKey: ["webhook-deliveries", activeClinicId, selectedEndpoint?.id],
    queryFn: () =>
      listWebhookDeliveries(activeClinicId!, {
        endpoint_id: selectedEndpoint!.id,
        limit: 50,
      }),
    enabled: !!activeClinicId && canManage && !!selectedEndpoint,
  });

  const invalidateEndpoints = () =>
    queryClient.invalidateQueries({ queryKey: ["webhook-endpoints", activeClinicId] });
  const invalidateDeliveries = () =>
    queryClient.invalidateQueries({ queryKey: ["webhook-deliveries", activeClinicId] });

  const createMutation = useMutation({
    mutationFn: () =>
      createWebhookEndpoint(activeClinicId!, {
        url: url.trim(),
        event_types: Array.from(checkedEvents),
      }),
    onSuccess: (created) => {
      invalidateEndpoints();
      setNewSecret(created.secret);
      setUrl("");
      setCheckedEvents(new Set());
      setFormError(null);
      setShowForm(false);
      setSelectedEndpointId(created.id);
    },
    onError: () => setFormError(t("createFailed")),
  });

  const toggleMutation = useMutation({
    mutationFn: (ep: WebhookEndpoint) =>
      updateWebhookEndpoint(activeClinicId!, ep.id, { is_active: !ep.is_active }),
    onSuccess: invalidateEndpoints,
  });

  const deleteMutation = useMutation({
    mutationFn: (endpointId: string) => deleteWebhookEndpoint(activeClinicId!, endpointId),
    onSuccess: () => {
      invalidateEndpoints();
      invalidateDeliveries();
      if (selectedEndpointId && endpoints?.find((e) => e.id === selectedEndpointId) == null) {
        setSelectedEndpointId(null);
      }
    },
  });

  const redeliverMutation = useMutation({
    mutationFn: (deliveryId: string) => redeliverWebhookDelivery(activeClinicId!, deliveryId),
    onSuccess: invalidateDeliveries,
  });

  const redeliverAllMutation = useMutation({
    mutationFn: () => redeliverFailedDeliveries(activeClinicId!, selectedEndpoint!.id),
    onSuccess: invalidateDeliveries,
  });

  const toggleEvent = (eventType: string) => {
    setCheckedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventType)) {
        next.delete(eventType);
      } else {
        next.add(eventType);
      }
      return next;
    });
  };

  if (!activeClinicId) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Dashboard", href: "/doctor/dashboard" },
            { label: t("breadcrumbClinic"), href: "/doctor/clinic" },
            { label: t("title") },
          ]}
        />
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Webhook className="mx-auto h-12 w-12 text-dreams-textSecondary" />
          <h2 className="mt-4 text-lg font-semibold text-dreams-textPrimary">
            {t("noClinicTitle")}
          </h2>
          <p className="mt-2 text-sm text-dreams-textSecondary">{t("noClinicHint")}</p>
        </div>
      </div>
    );
  }

  if (membersData && !canManage) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Dashboard", href: "/doctor/dashboard" },
            { label: t("breadcrumbClinic"), href: "/doctor/clinic" },
            { label: t("title") },
          ]}
        />
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Webhook className="mx-auto h-12 w-12 text-dreams-textSecondary" />
          <h2 className="mt-4 text-lg font-semibold text-dreams-textPrimary">
            {t("restrictedTitle")}
          </h2>
          <p className="mt-2 text-sm text-dreams-textSecondary">{t("restrictedHint")}</p>
        </div>
      </div>
    );
  }

  const failedCount = deliveries?.data.filter((d) => d.status === "failed").length ?? 0;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: t("breadcrumbClinic"), href: "/doctor/clinic" },
          { label: t("title") },
        ]}
      />

      <div>
        <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <p className="mt-1 text-sm text-dreams-textSecondary">{t("description")}</p>
      </div>

      {/* One-time secret reveal */}
      {newSecret && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-card">
          <p className="text-sm font-semibold text-amber-900">{t("secretTitle")}</p>
          <p className="mt-1 text-xs text-amber-800">{t("secretHint")}</p>
          <code className="mt-2 block break-all rounded-lg bg-white px-3 py-2 text-xs text-dreams-textPrimary">
            {newSecret}
          </code>
          <button
            onClick={() => setNewSecret(null)}
            className="mt-2 text-xs font-medium text-amber-900 underline"
          >
            {t("secretDismiss")}
          </button>
        </div>
      )}

      {/* Endpoints */}
      <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-dreams-textPrimary">
            {t("endpointsTitle")}
          </h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-lg p-1 hover:bg-gray-100"
            aria-label={t("addEndpoint")}
          >
            <Plus className="h-4 w-4 text-dreams-textSecondary" />
          </button>
        </div>

        {showForm && (
          <div className="mb-4 space-y-3 rounded-lg border border-dreams-border p-4">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={t("urlPlaceholder")}
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-dreams-blue"
            />
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-dreams-textSecondary">
                {t("eventsLabel")}
              </p>
              {WEBHOOK_EVENT_TYPES.map((eventType) => (
                <label
                  key={eventType}
                  className="flex items-center gap-2 text-sm text-dreams-textPrimary"
                >
                  <input
                    type="checkbox"
                    checked={checkedEvents.has(eventType)}
                    onChange={() => toggleEvent(eventType)}
                    className="h-4 w-4 rounded border-dreams-border text-dreams-blue focus:ring-dreams-blue"
                  />
                  <code className="text-xs">{eventType}</code>
                </label>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => createMutation.mutate()}
                disabled={
                  !url.trim() || checkedEvents.size === 0 || createMutation.isPending
                }
                className="rounded-lg bg-dreams-blue px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {createMutation.isPending ? t("creating") : t("addEndpoint")}
              </button>
              {formError && (
                <p className="text-xs text-red-600" role="alert">
                  {formError}
                </p>
              )}
            </div>
          </div>
        )}

        {endpointsLoading || !membersData ? (
          <p className="text-sm text-dreams-textSecondary">{t("loading")}</p>
        ) : endpointsError ? (
          <p className="text-sm text-red-600">{t("loadFailed")}</p>
        ) : !endpoints || endpoints.length === 0 ? (
          <p className="text-sm text-dreams-textSecondary">{t("endpointsEmpty")}</p>
        ) : (
          <ul className="space-y-3">
            {endpoints.map((ep) => (
              <li
                key={ep.id}
                className={`rounded-lg border p-3 transition-colors ${
                  selectedEndpoint?.id === ep.id
                    ? "border-dreams-blue bg-blue-50/50"
                    : "border-dreams-border"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    onClick={() => setSelectedEndpointId(ep.id)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <p className="truncate text-sm font-medium text-dreams-textPrimary">
                      {ep.url}
                    </p>
                    <p className="mt-0.5 text-xs text-dreams-textSecondary">
                      {ep.secret_masked}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {ep.event_types.map((eventType) => (
                        <span
                          key={eventType}
                          className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-dreams-textSecondary"
                        >
                          {eventType}
                        </span>
                      ))}
                    </div>
                  </button>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => toggleMutation.mutate(ep)}
                      disabled={toggleMutation.isPending}
                      role="switch"
                      aria-checked={ep.is_active}
                      aria-label={ep.is_active ? t("deactivate") : t("activate")}
                      className={`relative h-5 w-9 rounded-full transition-colors disabled:opacity-50 ${
                        ep.is_active ? "bg-dreams-blue" : "bg-gray-300"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                          ep.is_active ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(ep.id)}
                      disabled={deleteMutation.isPending}
                      className="rounded-lg p-1 text-dreams-textSecondary hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                      aria-label={t("deleteEndpoint")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Deliveries */}
      {selectedEndpoint && (
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-dreams-textPrimary">
                {t("deliveriesTitle")}
              </h2>
              <p className="truncate text-xs text-dreams-textSecondary">
                {selectedEndpoint.url}
              </p>
            </div>
            <button
              onClick={() => redeliverAllMutation.mutate()}
              disabled={failedCount === 0 || redeliverAllMutation.isPending}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-dreams-border px-3 py-1.5 text-xs font-medium text-dreams-textPrimary hover:bg-gray-50 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {redeliverAllMutation.isPending
                ? t("redelivering")
                : t("redeliverAllFailed")}
            </button>
          </div>

          {deliveriesLoading ? (
            <p className="text-sm text-dreams-textSecondary">{t("loading")}</p>
          ) : deliveriesError ? (
            <p className="text-sm text-red-600">{t("deliveriesLoadFailed")}</p>
          ) : !deliveries || deliveries.data.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">{t("deliveriesEmpty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-dreams-border text-xs text-dreams-textSecondary">
                    <th className="pb-2 pr-3 font-medium">{t("colCreated")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("colEvent")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("colStatus")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("colAttempts")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("colError")}</th>
                    <th className="pb-2 font-medium">{t("colActions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.data.map((d) => (
                    <tr key={d.id} className="border-b border-dreams-border last:border-0">
                      <td className="py-2.5 pr-3 text-xs text-dreams-textSecondary whitespace-nowrap">
                        {new Date(d.created_at).toLocaleString()}
                      </td>
                      <td className="py-2.5 pr-3">
                        <code className="text-xs text-dreams-textPrimary">
                          {d.event_type}
                        </code>
                      </td>
                      <td className="py-2.5 pr-3">
                        <Badge variant={STATUS_BADGE[d.status] as any}>{d.status}</Badge>
                      </td>
                      <td className="py-2.5 pr-3 text-xs text-dreams-textSecondary">
                        {d.attempts}
                      </td>
                      <td
                        className="max-w-[220px] truncate py-2.5 pr-3 text-xs text-dreams-textSecondary"
                        title={d.last_error ?? undefined}
                      >
                        {d.last_error ? truncate(d.last_error, 80) : "—"}
                      </td>
                      <td className="py-2.5">
                        {d.status === "failed" && (
                          <button
                            onClick={() => redeliverMutation.mutate(d.id)}
                            disabled={redeliverMutation.isPending}
                            className="flex items-center gap-1 rounded-lg border border-dreams-border px-2 py-1 text-xs font-medium text-dreams-textPrimary hover:bg-gray-50 disabled:opacity-50"
                          >
                            <RotateCcw className="h-3 w-3" />
                            {t("redeliver")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

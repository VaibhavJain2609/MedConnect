"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { MessageSquare, Send, Lock, Loader2, Building2 } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  closeThread, getThreadMessages, listThreads, postMessage,
  type MessageThread,
} from "@/lib/api/messages";
import { useAuthStore } from "@/stores/auth-store";
import { useClinicStore } from "@/stores/clinic-store";

const POLL_MS = 15_000;

function MessagesInner() {
  const t = useTranslations("messages");
  const format = useFormatter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const me = useAuthStore((s) => s.user);
  // Reactive clinic id — the axios interceptor attaches it as X-Clinic-Id.
  const clinicId = useClinicStore((s) => s.activeClinicId) ?? "";

  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("thread"));
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const paramThread = searchParams.get("thread");
  useEffect(() => {
    if (paramThread) setSelectedId(paramThread);
  }, [paramThread]);

  const threadsQuery = useQuery({
    queryKey: ["msg-threads", clinicId],
    queryFn: () => listThreads(),
    enabled: !!clinicId,
    refetchInterval: POLL_MS,
  });
  const threads = threadsQuery.data?.data ?? [];

  const messagesQuery = useQuery({
    queryKey: ["msg-thread", clinicId, selectedId],
    queryFn: () => getThreadMessages(selectedId!),
    enabled: !!clinicId && !!selectedId,
    refetchInterval: POLL_MS,
  });
  const selected: MessageThread | undefined =
    messagesQuery.data?.thread ?? threads.find((x) => x.id === selectedId);
  const messages = messagesQuery.data?.data ?? [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["msg-threads", clinicId] });
    queryClient.invalidateQueries({ queryKey: ["msg-thread", clinicId, selectedId] });
  };

  const sendMutation = useMutation({
    mutationFn: (body: string) => postMessage(selectedId!, body),
    onSuccess: () => {
      setDraft("");
      invalidate();
    },
  });

  const closeMutation = useMutation({
    mutationFn: () => closeThread(selectedId!),
    onSuccess: invalidate,
  });

  const msgCount = messages.length;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgCount, selectedId]);

  const isClosed = selected?.status === "closed";

  if (!clinicId) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: t("title") }]} />
        <div className="flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
          <Building2 className="mb-3 h-10 w-10 text-dreams-textSecondary opacity-40" />
          <p className="text-sm text-dreams-textSecondary">{t("noClinic")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("title") }]} />
      <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("inboxTitle")}</h1>

      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        {/* Thread list */}
        <div className="overflow-hidden rounded-xl border border-dreams-border bg-white shadow-card">
          {threadsQuery.isLoading ? (
            <div className="p-8 text-center text-dreams-textSecondary">{t("loading")}</div>
          ) : threads.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center">
              <MessageSquare className="mb-3 h-10 w-10 text-dreams-textSecondary opacity-40" />
              <p className="text-sm text-dreams-textSecondary">{t("emptyThreads")}</p>
            </div>
          ) : (
            <ul className="divide-y divide-dreams-border">
              {threads.map((thread) => (
                <li key={thread.id}>
                  <button
                    onClick={() => setSelectedId(thread.id)}
                    className={cn(
                      "w-full p-3 text-left transition-colors hover:bg-dreams-lightBg/60",
                      selectedId === thread.id && "bg-dreams-blue/5"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-dreams-textPrimary">
                        {thread.subject}
                      </p>
                      {thread.unread_count > 0 && (
                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-dreams-blue px-1.5 text-xs font-semibold text-white">
                          {thread.unread_count}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-dreams-textSecondary">
                      {thread.patient_name ?? t("unknownPatient")}
                      {thread.status === "closed" && ` · ${t("closed")}`}
                    </p>
                    {thread.last_message_preview && (
                      <p className="mt-1 truncate text-xs text-dreams-textSecondary">
                        {thread.last_message_preview}
                      </p>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Chat view */}
        <div className="flex min-h-[480px] flex-col overflow-hidden rounded-xl border border-dreams-border bg-white shadow-card">
          {!selectedId ? (
            <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
              <MessageSquare className="mb-3 h-10 w-10 text-dreams-textSecondary opacity-40" />
              <p className="text-sm text-dreams-textSecondary">{t("selectThread")}</p>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="flex items-center justify-between border-b border-dreams-border px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-dreams-textPrimary">
                    {selected?.subject}
                  </p>
                  <p className="text-xs text-dreams-textSecondary">
                    {selected?.patient_name ?? ""}
                    {isClosed && ` · ${t("closed")}`}
                  </p>
                </div>
                {!isClosed && (
                  <button
                    onClick={() => closeMutation.mutate()}
                    disabled={closeMutation.isPending}
                    className="flex items-center gap-1 rounded-lg border border-dreams-border px-2.5 py-1.5 text-xs font-medium text-dreams-textPrimary hover:bg-dreams-lightBg disabled:opacity-50"
                  >
                    <Lock className="h-3.5 w-3.5" />
                    {t("close")}
                  </button>
                )}
              </div>

              {/* Messages */}
              <div className="flex-1 space-y-3 overflow-y-auto bg-dreams-lightBg/40 p-4">
                {messagesQuery.isLoading ? (
                  <div className="flex justify-center p-8">
                    <Loader2 className="h-6 w-6 animate-spin text-dreams-textSecondary" />
                  </div>
                ) : (
                  messages.map((m) => {
                    const mine = m.sender_id === me?.id;
                    return (
                      <div key={m.id} className={cn("flex", mine && "justify-end")}>
                        <div
                          className={cn(
                            "max-w-[75%] rounded-2xl px-3.5 py-2",
                            mine
                              ? "bg-dreams-blue text-white"
                              : "border border-dreams-border bg-white text-dreams-textPrimary"
                          )}
                        >
                          {!mine && (
                            <p className="mb-0.5 text-xs font-medium text-dreams-textSecondary">
                              {m.sender_name}
                            </p>
                          )}
                          <p className="whitespace-pre-wrap text-sm">{m.body}</p>
                          {m.created_at && (
                            <p
                              className={cn(
                                "mt-1 text-right text-[10px]",
                                mine ? "text-white/70" : "text-dreams-textSecondary"
                              )}
                            >
                              {format.dateTime(new Date(m.created_at), {
                                day: "numeric",
                                month: "short",
                                hour: "numeric",
                                minute: "2-digit",
                              })}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={bottomRef} />
              </div>

              {/* Composer */}
              {isClosed ? (
                <div className="border-t border-dreams-border px-4 py-3 text-center text-sm text-dreams-textSecondary">
                  {t("closedHintStaff")}
                </div>
              ) : (
                <form
                  className="flex items-end gap-2 border-t border-dreams-border p-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const body = draft.trim();
                    if (body) sendMutation.mutate(body);
                  }}
                >
                  <Textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={t("replyPlaceholder")}
                    rows={2}
                    className="flex-1 resize-none"
                  />
                  <button
                    type="submit"
                    disabled={!draft.trim() || sendMutation.isPending}
                    className="flex h-9 items-center gap-1.5 rounded-lg bg-dreams-blue px-3 text-sm font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
                  >
                    <Send className="h-4 w-4" />
                    {t("send")}
                  </button>
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DoctorMessagesPage() {
  // useSearchParams() requires a Suspense boundary during prerendering.
  return (
    <Suspense fallback={null}>
      <MessagesInner />
    </Suspense>
  );
}

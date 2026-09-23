"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import {
  MessageSquare, Plus, Send, Lock, LockOpen, Loader2,
} from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  closeThread, createThread, getThreadMessages, listThreads,
  postMessage, reopenThread,
  type MessageThread,
} from "@/lib/api/messages";
import { getMyClinicLinks } from "@/lib/api/patients";
import { useAuthStore } from "@/stores/auth-store";

const POLL_MS = 15_000;

function MessagesInner() {
  const t = useTranslations("messages");
  const format = useFormatter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const me = useAuthStore((s) => s.user);

  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("thread"));
  const [draft, setDraft] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [newClinicId, setNewClinicId] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newBody, setNewBody] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Deep-link: notification clicks land here with ?thread=<id>.
  const paramThread = searchParams.get("thread");
  useEffect(() => {
    if (paramThread) setSelectedId(paramThread);
  }, [paramThread]);

  const threadsQuery = useQuery({
    queryKey: ["msg-threads"],
    queryFn: () => listThreads(),
    refetchInterval: POLL_MS,
  });
  const threads = threadsQuery.data?.data ?? [];

  const messagesQuery = useQuery({
    queryKey: ["msg-thread", selectedId],
    queryFn: () => getThreadMessages(selectedId!),
    enabled: !!selectedId,
    refetchInterval: POLL_MS,
  });
  const selected: MessageThread | undefined =
    messagesQuery.data?.thread ?? threads.find((x) => x.id === selectedId);
  const messages = messagesQuery.data?.data ?? [];

  const approvedClinicsQuery = useQuery({
    queryKey: ["my-clinic-links"],
    queryFn: getMyClinicLinks,
    enabled: newOpen,
  });
  const approvedClinics = (approvedClinicsQuery.data?.data ?? []).filter(
    (l) => l.consent_status === "approved"
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["msg-threads"] });
    queryClient.invalidateQueries({ queryKey: ["msg-thread", selectedId] });
  };

  const sendMutation = useMutation({
    mutationFn: (body: string) => postMessage(selectedId!, body),
    onSuccess: () => {
      setDraft("");
      invalidate();
    },
  });

  const createMutation = useMutation({
    mutationFn: createThread,
    onSuccess: (thread) => {
      setNewOpen(false);
      setNewClinicId("");
      setNewSubject("");
      setNewBody("");
      setSelectedId(thread.id);
      invalidate();
    },
  });

  const closeMutation = useMutation({
    mutationFn: () => closeThread(selectedId!),
    onSuccess: invalidate,
  });
  const reopenMutation = useMutation({
    mutationFn: () => reopenThread(selectedId!),
    onSuccess: invalidate,
  });

  const msgCount = messages.length;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgCount, selectedId]);

  const isClosed = selected?.status === "closed";

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("title") }]} />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <button
          onClick={() => setNewOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-dreams-blue px-3 py-2 text-sm font-medium text-white hover:bg-dreams-blue/90"
        >
          <Plus className="h-4 w-4" />
          {t("newMessage")}
        </button>
      </div>

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
                      {thread.clinic_name ?? t("unknownClinic")}
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
                    {selected?.clinic_name ?? ""}
                    {isClosed && ` · ${t("closed")}`}
                  </p>
                </div>
                {isClosed ? (
                  <button
                    onClick={() => reopenMutation.mutate()}
                    disabled={reopenMutation.isPending}
                    className="flex items-center gap-1 rounded-lg border border-dreams-border px-2.5 py-1.5 text-xs font-medium text-dreams-textPrimary hover:bg-dreams-lightBg disabled:opacity-50"
                  >
                    <LockOpen className="h-3.5 w-3.5" />
                    {t("reopen")}
                  </button>
                ) : (
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
                  {t("closedHint")}
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

      {/* New thread dialog */}
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("newThreadTitle")}</DialogTitle>
            <DialogDescription>{t("newThreadDescription")}</DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (newClinicId && newSubject.trim() && newBody.trim()) {
                createMutation.mutate({
                  clinic_id: newClinicId,
                  subject: newSubject.trim(),
                  body: newBody.trim(),
                });
              }
            }}
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("clinicLabel")}
              </label>
              <select
                value={newClinicId}
                onChange={(e) => setNewClinicId(e.target.value)}
                required
                className="w-full rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm"
              >
                <option value="">{t("clinicPlaceholder")}</option>
                {approvedClinics.map((l) => (
                  <option key={l.clinic_id} value={l.clinic_id}>
                    {l.clinic_name}
                  </option>
                ))}
              </select>
              {approvedClinicsQuery.isSuccess && approvedClinics.length === 0 && (
                <p className="mt-1 text-xs text-dreams-textSecondary">{t("noLinkedClinics")}</p>
              )}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("subjectLabel")}
              </label>
              <Input
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                placeholder={t("subjectPlaceholder")}
                maxLength={255}
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("bodyLabel")}
              </label>
              <Textarea
                value={newBody}
                onChange={(e) => setNewBody(e.target.value)}
                placeholder={t("bodyPlaceholder")}
                rows={4}
                required
              />
            </div>
            <DialogFooter>
              <button
                type="button"
                onClick={() => setNewOpen(false)}
                className="rounded-lg border border-dreams-border px-3 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg"
              >
                {t("cancel")}
              </button>
              <button
                type="submit"
                disabled={
                  createMutation.isPending || !newClinicId || !newSubject.trim() || !newBody.trim()
                }
                className="rounded-lg bg-dreams-blue px-3 py-2 text-sm font-medium text-white hover:bg-dreams-blue/90 disabled:opacity-50"
              >
                {createMutation.isPending ? t("sending") : t("send")}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function PatientMessagesPage() {
  // useSearchParams() requires a Suspense boundary during prerendering.
  return (
    <Suspense fallback={null}>
      <MessagesInner />
    </Suspense>
  );
}

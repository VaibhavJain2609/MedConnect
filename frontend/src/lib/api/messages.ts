import api from "@/lib/api";

/**
 * Secure patient↔clinic messaging (/api/v1/messages).
 *
 * Patient calls carry no X-Clinic-Id → own threads. Clinic staff calls rely
 * on the axios interceptor attaching the active clinic id → clinic inbox.
 */

export interface MessageThread {
  id: string;
  patient_id: string;
  patient_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  subject: string;
  status: "open" | "closed";
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ThreadMessage {
  id: string;
  thread_id: string;
  sender_id: string;
  sender_name: string | null;
  body: string;
  created_at: string | null;
}

export interface UnreadCount {
  unread_threads: number;
  unread_messages: number;
}

export interface ThreadMessagesResponse {
  thread: MessageThread;
  data: ThreadMessage[];
}

export async function createThread(input: {
  clinic_id: string;
  subject: string;
  body: string;
}): Promise<MessageThread> {
  const res = await api.post("/api/v1/messages/threads", input);
  return res.data;
}

export async function listThreads(statusFilter?: "open" | "closed"): Promise<{
  data: MessageThread[];
}> {
  const res = await api.get("/api/v1/messages/threads", {
    params: statusFilter ? { status_filter: statusFilter } : undefined,
  });
  return res.data;
}

export async function getUnreadCount(): Promise<UnreadCount> {
  const res = await api.get("/api/v1/messages/threads/unread-count");
  return res.data;
}

export async function getThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
  const res = await api.get(`/api/v1/messages/threads/${threadId}/messages`);
  return res.data;
}

export async function postMessage(threadId: string, body: string): Promise<ThreadMessage> {
  const res = await api.post(`/api/v1/messages/threads/${threadId}/messages`, { body });
  return res.data;
}

export async function closeThread(threadId: string): Promise<MessageThread> {
  const res = await api.patch(`/api/v1/messages/threads/${threadId}/close`);
  return res.data;
}

export async function reopenThread(threadId: string): Promise<MessageThread> {
  const res = await api.patch(`/api/v1/messages/threads/${threadId}/reopen`);
  return res.data;
}

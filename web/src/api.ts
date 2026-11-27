const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export const DEFAULT_USER_ID = "u1";

export type HitlAction = {
  type?: string;
  label?: string;
  oauth_url?: string;
  start_api?: string;
  popup?: boolean;
  error?: string;
  [key: string]: unknown;
};

export type ChatMessage = {
  id?: number;
  role: "user" | "assistant" | string;
  content: string;
  flow?: string | null;
  created_at?: string;
  hitl?: boolean;
  missing_fields?: string[];
  actions?: HitlAction[];
  ui?: { show_connect_email?: boolean; provider?: string };
};

export type ChatSession = {
  session_id: string;
  user_id: string;
  title: string;
  first_user_message?: string | null;
  last_message?: string | null;
  message_count?: number;
  created_at?: string;
  last_seen_at?: string;
};

export type AskResult = {
  ok?: boolean;
  message?: string;
  error?: string;
  session_id: string;
  user_id?: string;
  flow?: string;
  hitl?: boolean;
  missing_fields?: string[];
  actions?: HitlAction[];
  ui?: { show_connect_email?: boolean; provider?: string };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function listSessions(userId = DEFAULT_USER_ID) {
  return request<{ items: ChatSession[] }>(
    `/auth/sessions?user_id=${encodeURIComponent(userId)}`,
  );
}

export function createSession(userId = DEFAULT_USER_ID) {
  return request<{ ok: boolean; session_id: string; session: ChatSession }>(
    "/auth/sessions",
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    },
  );
}

export function deleteSession(sessionId: string, userId = DEFAULT_USER_ID) {
  const q = new URLSearchParams({ user_id: userId });
  return request<{ ok: boolean }>(
    `/auth/sessions/${encodeURIComponent(sessionId)}?${q}`,
    { method: "DELETE" },
  );
}

export function getChatHistory(sessionId: string, userId = DEFAULT_USER_ID) {
  const q = new URLSearchParams({
    session_id: sessionId,
    user_id: userId,
    limit: "200",
  });
  return request<{ items: ChatMessage[] }>(`/auth/chat/history?${q}`);
}

export function ask(
  text: string,
  opts: { userId?: string; sessionId?: string | null } = {},
) {
  return request<AskResult>("/ask", {
    method: "POST",
    body: JSON.stringify({
      text,
      user_id: opts.userId || DEFAULT_USER_ID,
      session_id: opts.sessionId || undefined,
    }),
  });
}

export type AskStreamHandlers = {
  onStatus?: (data: { phase?: string; message?: string }) => void;
  onMeta?: (data: Partial<AskResult>) => void;
  onDelta?: (text: string) => void;
  onDone?: (result: AskResult) => void;
  onError?: (message: string) => void;
};

/** POST /ask/stream — SSE: status → meta → delta* → done | error */
export async function askStream(
  text: string,
  opts: { userId?: string; sessionId?: string | null } = {},
  handlers: AskStreamHandlers = {},
): Promise<AskResult> {
  const res = await fetch(`${API_BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      text,
      user_id: opts.userId || DEFAULT_USER_ID,
      session_id: opts.sessionId || undefined,
    }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (!res.body) {
    throw new Error("Trình duyệt không hỗ trợ stream body.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: AskResult | null = null;

  const dispatch = (event: string, raw: string) => {
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      data = { message: raw };
    }
    if (event === "status") {
      handlers.onStatus?.(data as { phase?: string; message?: string });
      return;
    }
    if (event === "meta") {
      handlers.onMeta?.(data as Partial<AskResult>);
      return;
    }
    if (event === "delta") {
      const t = typeof data.text === "string" ? data.text : "";
      if (t) handlers.onDelta?.(t);
      return;
    }
    if (event === "error") {
      const msg =
        typeof data.message === "string" ? data.message : "Lỗi stream từ server.";
      handlers.onError?.(msg);
      throw new Error(msg);
    }
    if (event === "done") {
      finalResult = data as AskResult;
      handlers.onDone?.(finalResult);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const block of parts) {
      if (!block.trim()) continue;
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length) dispatch(event, dataLines.join("\n"));
    }
  }

  if (!finalResult) {
    throw new Error("Stream kết thúc mà chưa nhận event done.");
  }
  return finalResult;
}

export type AppNotification = {
  id: number;
  kind: string;
  title: string;
  body: string;
  created_at?: string;
  read_at?: string | null;
  meta?: {
    session_id?: string;
    checkpoint_id?: number;
    url?: string;
    [key: string]: unknown;
  } | null;
};

export function listNotifications(
  opts: { userId?: string; sinceId?: number; unreadOnly?: boolean } = {},
) {
  const q = new URLSearchParams({
    user_id: opts.userId || DEFAULT_USER_ID,
    limit: "50",
  });
  if (opts.sinceId != null) q.set("since_id", String(opts.sinceId));
  if (opts.unreadOnly) q.set("unread_only", "true");
  return request<{ items: AppNotification[] }>(`/email/notifications?${q}`);
}

export type ScheduledJob = {
  id: string;
  job_type: string;
  payload?: Record<string, unknown>;
  run_at_unix: number;
  run_at_local: string;
  description: string;
};

export function listScheduledJobs(userId = DEFAULT_USER_ID) {
  return request<{ items: ScheduledJob[]; user_id: string }>(
    `/jobs/scheduled?user_id=${encodeURIComponent(userId)}`,
  );
}

export function deleteScheduledJob(jobId: string, userId = DEFAULT_USER_ID) {
  const q = new URLSearchParams({ user_id: userId });
  return request<{ ok: boolean; id: string }>(
    `/jobs/scheduled/${encodeURIComponent(jobId)}?${q}`,
    { method: "DELETE" },
  );
}

export function runScheduledJobNow(jobId: string, userId = DEFAULT_USER_ID) {
  const q = new URLSearchParams({ user_id: userId });
  return request<{
    ok: boolean;
    id: string;
    job_type?: string;
    message?: string;
    error?: string;
    result?: unknown;
    awaiting_content?: boolean;
    session_id?: string;
  }>(`/jobs/scheduled/${encodeURIComponent(jobId)}/run?${q}`, {
    method: "POST",
  });
}

export type EmailStatus = {
  connected: boolean;
  user_id: string;
  provider: string;
  email_address?: string | null;
  expires_at?: string | null;
};

export function getEmailStatus(userId = DEFAULT_USER_ID) {
  return request<EmailStatus>(
    `/email/status?user_id=${encodeURIComponent(userId)}`,
  );
}

export function startGmailOAuth(opts: {
  userId?: string;
  sessionId?: string | null;
} = {}) {
  const q = new URLSearchParams({
    format: "json",
    user_id: opts.userId || DEFAULT_USER_ID,
  });
  if (opts.sessionId) q.set("session_id", opts.sessionId);
  return request<{
    ok: boolean;
    oauth_url: string;
    popup?: boolean;
    user_id?: string;
    session_id?: string;
  }>(`/email/oauth/google/start?${q}`);
}

export function disconnectGmail(userId = DEFAULT_USER_ID) {
  return request<{ ok: boolean; message?: string }>(
    `/email/oauth/google?user_id=${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}

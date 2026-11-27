import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import {
  Search,
  Plus,
  Minus,
  Square,
  X,
  Loader2,
  MessageSquare,
  MessageSquarePlus,
  SendHorizontal,
  Ban,
  Trash2,
  Mail,
  Lock,
  CalendarClock,
  ChevronRight,
  RefreshCw,
  Bot,
  CircleUserRound,
  Clock3,
  ClipboardList,
  Inbox,
  Sparkles,
  Unplug,
  Link2,
  ChevronUp,
  Play,
} from "lucide-react";
import { MarkdownBody } from "./MarkdownBody";
import {
  askStream,
  createSession,
  DEFAULT_USER_ID,
  deleteScheduledJob,
  deleteSession,
  disconnectGmail,
  getChatHistory,
  getEmailStatus,
  listNotifications,
  listScheduledJobs,
  runScheduledJobNow,
  listSessions,
  startGmailOAuth,
  type ChatMessage,
  type ChatSession,
  type EmailStatus,
  type HitlAction,
  type ScheduledJob,
} from "./api";

const dragRegion = { WebkitAppRegion: "drag" } as CSSProperties;
const noDrag = { WebkitAppRegion: "no-drag" } as CSSProperties;
const ICON = 1.5;

type UiMessage = ChatMessage & {
  localId?: string;
};

function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-[0.85rem] bg-[linear-gradient(145deg,#134e4a_0%,#0f766e_55%,#14b8a6_100%)] text-white shadow-[0_8px_24px_-12px_rgba(15,118,110,0.55)]"
      style={{ width: size, height: size }}
    >
      <Bot style={{ width: size * 0.48, height: size * 0.48 }} strokeWidth={ICON} />
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
  danger,
  disabled,
}: {
  label: string;
  onClick?: () => void;
  children: ReactNode;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-xl p-2 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] disabled:opacity-40 ${
        danger
          ? "text-[var(--muted)] hover:bg-rose-50 hover:text-[var(--danger)]"
          : "text-[var(--muted)] hover:bg-black/[0.04] hover:text-[var(--ink)]"
      }`}
    >
      {children}
    </button>
  );
}

function formatDayLabel(iso?: string) {
  if (!iso) return "Today";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Today";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return `Today · ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function sessionLabel(s: ChatSession) {
  return s.title || "New conversation";
}

function hasEmailConnectAction(actions?: HitlAction[] | null) {
  return Boolean(actions?.some((a) => a.type === "oauth_google"));
}

const HINTS = [
  { icon: ClipboardList, text: "Điền standup giúp tôi hôm nay" },
  { icon: Inbox, text: "Đọc email quan trọng giúp tôi" },
  { icon: CalendarClock, text: "Mỗi 8h tối điền standup giúp tôi" },
  { icon: Mail, text: "Kết nối Gmail để theo dõi mail" },
] as const;

export default function App() {
  const api = window.electronAPI;
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [connectingEmail, setConnectingEmail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showJobs, setShowJobs] = useState(false);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [showAccount, setShowAccount] = useState(false);
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null);
  const [emailBusy, setEmailBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastNotifId = useRef(0);
  const activeSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const hitlLocked =
    Boolean(lastAssistant?.hitl) && hasEmailConnectAction(lastAssistant?.actions);
  const inputLocked = sending || connectingEmail || hitlLocked;

  const refreshSessions = useCallback(async (preferId?: string | null) => {
    setLoadingSessions(true);
    setError(null);
    try {
      const { items } = await listSessions();
      setSessions(items);
      setActiveSessionId((prev) => {
        if (preferId === null) return items[0]?.session_id ?? null;
        if (preferId) return preferId;
        if (prev && items.some((s) => s.session_id === prev)) return prev;
        return items[0]?.session_id ?? null;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const loadHistory = useCallback(async (sessionId: string) => {
    setLoadingMessages(true);
    setError(null);
    try {
      const { items } = await getChatHistory(sessionId);
      setMessages(
        items.map((m) => {
          const meta = (m as ChatMessage & { meta?: Record<string, unknown> }).meta;
          if (!meta || typeof meta !== "object") return m;
          return {
            ...m,
            hitl: m.hitl ?? Boolean(meta.hitl),
            missing_fields:
              m.missing_fields ??
              (Array.isArray(meta.missing_fields)
                ? (meta.missing_fields as string[])
                : undefined),
            actions:
              m.actions ??
              (Array.isArray(meta.actions) ? (meta.actions as HitlAction[]) : undefined),
            ui:
              m.ui ??
              (meta.ui && typeof meta.ui === "object"
                ? (meta.ui as ChatMessage["ui"])
                : undefined),
          };
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    void loadHistory(activeSessionId);
  }, [activeSessionId, loadHistory]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const { items } = await listNotifications({
          sinceId: lastNotifId.current || undefined,
        });
        if (cancelled || !items?.length) return;
        for (const n of items) {
          if (n.id <= lastNotifId.current) continue;
          lastNotifId.current = Math.max(lastNotifId.current, n.id);
          setBanner(`${n.title}: ${n.body}`);
          void api?.notify?.(n.title, n.body);
          const sid =
            typeof n.meta?.session_id === "string" ? n.meta.session_id : null;
          // Cron standup hỏi nội dung → nhảy sang chat mới để user trả lời
          if (
            sid &&
            (n.kind === "standup_need_content" ||
              n.kind === "standup_login" ||
              n.kind === "standup_missed")
          ) {
            void (async () => {
              await refreshSessions(sid);
              setActiveSessionId(sid);
              await loadHistory(sid);
              inputRef.current?.focus();
            })();
          }
        }
      } catch {
        /* ignore */
      }
    };
    void tick();
    const id = window.setInterval(tick, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [api, refreshSessions, loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, connectingEmail]);

  const refreshEmailStatus = useCallback(async () => {
    try {
      const st = await getEmailStatus();
      setEmailStatus(st);
    } catch {
      setEmailStatus(null);
    }
  }, []);

  useEffect(() => {
    void refreshEmailStatus();
  }, [refreshEmailStatus]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data;
      if (!data || data.type !== "gmail_oauth_done") return;
      setConnectingEmail(false);
      setEmailBusy(false);
      void refreshEmailStatus();
      const sid = activeSessionIdRef.current;
      if (sid) {
        void loadHistory(sid);
        void refreshSessions(sid);
      }
      const msg = data.message || "Gmail connected.";
      setBanner(typeof msg === "string" ? msg : "Gmail đã kết nối.");
      void api?.notify?.("Gmail connected", String(msg));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [api, loadHistory, refreshSessions, refreshEmailStatus]);

  const openAccountMenu = () => {
    setShowAccount((v) => !v);
    void refreshEmailStatus();
  };

  const handleConnectGmail = async () => {
    setEmailBusy(true);
    setError(null);
    try {
      const start = await startGmailOAuth({
        sessionId: activeSessionIdRef.current,
      });
      if (!start.oauth_url) throw new Error("Không nhận được OAuth URL");
      setConnectingEmail(true);
      const popup = window.open(
        start.oauth_url,
        "haven_gmail_oauth",
        "width=520,height=720,menubar=no,toolbar=no,status=no",
      );
      if (!popup) {
        setConnectingEmail(false);
        throw new Error("Popup bị chặn. Cho phép popup rồi thử lại.");
      }
      const timer = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(timer);
          setConnectingEmail(false);
          setEmailBusy(false);
          void refreshEmailStatus();
        }
      }, 800);
    } catch (e) {
      setEmailBusy(false);
      setConnectingEmail(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleRevokeGmail = async () => {
    if (emailBusy) return;
    setEmailBusy(true);
    setError(null);
    try {
      await disconnectGmail();
      await refreshEmailStatus();
      setBanner("Đã ngắt kết nối Gmail.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEmailBusy(false);
    }
  };

  const refreshJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const { items } = await listScheduledJobs();
      setJobs(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingJobs(false);
    }
  }, []);

  const openJobsPanel = () => {
    setShowJobs(true);
    void refreshJobs();
  };

  const handleDeleteJob = async (jobId: string) => {
    if (deletingJobId || runningJobId) return;
    setDeletingJobId(jobId);
    try {
      await deleteScheduledJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeletingJobId(null);
    }
  };

  const handleRunJobNow = async (jobId: string) => {
    if (runningJobId || deletingJobId) return;
    setRunningJobId(jobId);
    setError(null);
    try {
      const out = await runScheduledJobNow(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
      const result = out.result as
        | { session_id?: string; awaiting_content?: boolean; message?: string }
        | undefined;
      const sid =
        (typeof result?.session_id === "string" && result.session_id) ||
        (typeof out.session_id === "string" ? out.session_id : null);
      if (sid && (result?.awaiting_content || out.awaiting_content)) {
        setShowJobs(false);
        setBanner(
          result?.message ||
            out.message ||
            "Đã mở chat mới — hãy trả lời hôm qua / hôm nay tại đây.",
        );
        // Luôn refresh + loadHistory (kể cả sid trùng) để hiện câu hỏi HITL
        await refreshSessions(sid);
        setActiveSessionId(sid);
        await loadHistory(sid);
        inputRef.current?.focus();
      } else {
        setBanner(out.message || (out.ok ? "Đã chạy job." : "Job chạy xong."));
      }
      void refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunningJobId(null);
    }
  };

  const handleNewChat = async () => {
    setError(null);
    try {
      const created = await createSession();
      setMessages([]);
      await refreshSessions(created.session_id);
      inputRef.current?.focus();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDeleteSession = async (sessionId: string, e?: MouseEvent) => {
    e?.stopPropagation();
    if (deletingId) return;
    setDeletingId(sessionId);
    setError(null);
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        setMessages([]);
        await refreshSessions(null);
      } else {
        await refreshSessions(activeSessionId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  };

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || inputLocked) return;

    setSending(true);
    setError(null);
    setDraft("");
    const assistantLocalId = `a-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, localId: `u-${Date.now()}` },
      {
        role: "assistant",
        content: "",
        localId: assistantLocalId,
      },
    ]);

    try {
      const result = await askStream(
        text,
        { sessionId: activeSessionId },
        {
          onMeta: (meta) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.localId === assistantLocalId
                  ? {
                      ...m,
                      flow: meta.flow ?? m.flow,
                      hitl: Boolean(meta.hitl),
                      missing_fields: meta.missing_fields,
                      actions: meta.actions,
                      ui: meta.ui,
                    }
                  : m,
              ),
            );
          },
          onDelta: (chunk) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.localId === assistantLocalId
                  ? { ...m, content: (m.content || "") + chunk }
                  : m,
              ),
            );
          },
          onDone: (done) => {
            const reply =
              done.message ||
              done.error ||
              "Không nhận được phản hồi từ server.";
            setMessages((prev) =>
              prev.map((m) =>
                m.localId === assistantLocalId
                  ? {
                      ...m,
                      content: reply,
                      flow: done.flow,
                      hitl: Boolean(done.hitl),
                      missing_fields: done.missing_fields,
                      actions: done.actions,
                      ui: done.ui,
                    }
                  : m,
              ),
            );
          },
        },
      );
      if (result.session_id && result.session_id !== activeSessionId) {
        setActiveSessionId(result.session_id);
      }
      await refreshSessions(result.session_id);
    } catch (e) {
      const errText = `Lỗi: ${e instanceof Error ? e.message : String(e)}`;
      setMessages((prev) =>
        prev.map((m) =>
          m.localId === assistantLocalId
            ? { ...m, content: m.content?.trim() ? m.content : errText }
            : m,
        ),
      );
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
      if (!hitlLocked) inputRef.current?.focus();
    }
  };

  const openGmailConnect = (action: HitlAction) => {
    const url = action.oauth_url;
    if (!url) {
      setError(action.error || "Không có OAuth URL để kết nối Gmail.");
      return;
    }
    setConnectingEmail(true);
    setError(null);
    const popup = window.open(
      url,
      "haven_gmail_oauth",
      "width=520,height=720,menubar=no,toolbar=no,status=no",
    );
    if (!popup) {
      setConnectingEmail(false);
      setError("Popup bị chặn. Cho phép popup rồi thử lại.");
      return;
    }
    const timer = window.setInterval(() => {
      if (popup.closed) {
        window.clearInterval(timer);
        setConnectingEmail(false);
        const sid = activeSessionIdRef.current;
        if (sid) void loadHistory(sid);
      }
    }, 800);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void handleSend();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const filteredSessions = query.trim()
    ? sessions.filter((s) =>
        sessionLabel(s).toLowerCase().includes(query.trim().toLowerCase()),
      )
    : sessions;

  const activeSession = sessions.find((s) => s.session_id === activeSessionId);
  const headerTitle = activeSession ? sessionLabel(activeSession) : "digitalboo";
  const showEmptyWorkspace =
    Boolean(activeSessionId) &&
    !loadingMessages &&
    messages.length === 0 &&
    !sending;

  const jobTypeLabel = (t: string) => {
    if (t === "standup_fill") return "Standup";
    if (t === "email_watch") return "Email";
    return t;
  };

  const statusLabel = hitlLocked
    ? "Waiting for action"
    : sending
      ? "Responding…"
      : "Ready";

  return (
    <div className="relative flex h-full min-h-[100dvh] overflow-hidden bg-[var(--surface)] text-[var(--ink)]">
      {/* soft ambient wash */}
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        style={{
          background:
            "radial-gradient(900px 420px at 12% -10%, rgba(20,184,166,0.10), transparent 55%), radial-gradient(700px 380px at 90% 0%, rgba(15,23,42,0.04), transparent 50%)",
        }}
      />

      {/* ── Jobs modal ── */}
      {showJobs && (
        <div className="absolute inset-0 z-40 flex animate-fade-up" style={noDrag}>
          <button
            type="button"
            className="absolute inset-0 bg-[#12141a]/30 backdrop-blur-md"
            aria-label="Close jobs panel"
            onClick={() => setShowJobs(false)}
          />
          <div className="relative z-10 m-auto w-[min(460px,92vw)] rounded-[1.75rem] bg-black/[0.04] p-1.5 ring-1 ring-black/[0.06]">
            <div className="flex max-h-[78vh] flex-col overflow-hidden rounded-[calc(1.75rem-0.375rem)] bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
              <div className="flex items-start justify-between gap-3 border-b border-black/[0.06] px-5 py-4">
                <div>
                  <p className="inline-flex items-center gap-1.5 rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
                    <CalendarClock className="h-3 w-3" strokeWidth={ICON} />
                    Scheduler
                  </p>
                  <h2 className="font-display mt-2 text-[26px] leading-none text-[var(--ink)]">
                    Scheduled jobs
                  </h2>
                  <p className="mt-1.5 text-[13px] text-[var(--muted)]">
                    Thời điểm chạy và việc digitalboo sẽ làm
                  </p>
                </div>
                <div className="flex items-center gap-0.5">
                  <IconButton label="Refresh" onClick={() => void refreshJobs()}>
                    <RefreshCw
                      className={`h-4 w-4 ${loadingJobs ? "animate-spin" : ""}`}
                      strokeWidth={ICON}
                    />
                  </IconButton>
                  <IconButton label="Close" onClick={() => setShowJobs(false)}>
                    <X className="h-4 w-4" strokeWidth={ICON} />
                  </IconButton>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4">
                {loadingJobs && (
                  <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-[var(--muted)]">
                    <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                    Loading jobs…
                  </div>
                )}
                {!loadingJobs && jobs.length === 0 && (
                  <div className="rounded-[1.25rem] bg-[var(--surface)] px-5 py-10 text-center ring-1 ring-black/[0.04]">
                    <CalendarClock
                      className="mx-auto mb-3 h-9 w-9 text-black/20"
                      strokeWidth={ICON}
                    />
                    <p className="text-[15px] font-semibold">Chưa có job nào</p>
                    <p className="mt-1 text-[13px] text-[var(--muted)]">
                      Hẹn lịch standup / email rồi quay lại đây.
                    </p>
                  </div>
                )}
                <ul className="space-y-2.5">
                  {jobs.map((job) => (
                    <li
                      key={job.id}
                      className="rounded-[1.25rem] bg-[var(--surface)] p-1 ring-1 ring-black/[0.05] transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:-translate-y-0.5"
                    >
                      <div className="flex items-start gap-2 rounded-[calc(1.25rem-0.25rem)] bg-white px-3.5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                          {job.job_type === "email_watch" ? (
                            <Inbox className="h-4 w-4" strokeWidth={ICON} />
                          ) : (
                            <ClipboardList className="h-4 w-4" strokeWidth={ICON} />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-[var(--ink)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-white">
                              {jobTypeLabel(job.job_type)}
                            </span>
                            <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--accent)]">
                              <Clock3 className="h-3 w-3" strokeWidth={ICON} />
                              {job.run_at_local}
                            </span>
                          </div>
                          <p className="mt-1.5 text-[13px] leading-snug text-[var(--ink)]">
                            {job.description}
                          </p>
                        </div>
                        <IconButton
                          label="Chạy ngay"
                          disabled={
                            runningJobId === job.id ||
                            deletingJobId === job.id ||
                            Boolean(runningJobId)
                          }
                          onClick={() => void handleRunJobNow(job.id)}
                        >
                          {runningJobId === job.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                          ) : (
                            <Play className="h-4 w-4" strokeWidth={ICON} />
                          )}
                        </IconButton>
                        <IconButton
                          label="Xóa cronjob"
                          danger
                          disabled={
                            deletingJobId === job.id ||
                            runningJobId === job.id ||
                            Boolean(runningJobId)
                          }
                          onClick={() => void handleDeleteJob(job.id)}
                        >
                          {deletingJobId === job.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                          ) : (
                            <Trash2 className="h-4 w-4" strokeWidth={ICON} />
                          )}
                        </IconButton>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Sidebar ── */}
      <aside className="relative z-[1] flex w-[292px] shrink-0 flex-col border-r border-black/[0.06] bg-white/55 backdrop-blur-xl">
        <div
          className="flex items-center justify-between gap-1 px-3 pt-4 pb-2"
          style={dragRegion}
        >
          <button
            type="button"
            onClick={openJobsPanel}
            className="group flex min-w-0 flex-1 items-center gap-2.5 rounded-2xl px-2 py-2 text-left transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-black/[0.03] active:scale-[0.99]"
            style={noDrag}
            title="Xem lịch chạy (cronjobs)"
          >
            <BrandMark size={34} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold tracking-tight">
                digitalboo
              </p>
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-[var(--muted)]">
                <CalendarClock className="h-3 w-3" strokeWidth={ICON} />
                Scheduled jobs
                <ChevronRight className="h-3 w-3 -translate-x-1 opacity-0 transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0 group-hover:opacity-100" strokeWidth={ICON} />
              </p>
            </div>
          </button>
          <div className="flex items-center" style={noDrag}>
            <IconButton label="Search" onClick={() => setShowSearch((v) => !v)}>
              <Search className="h-[18px] w-[18px]" strokeWidth={ICON} />
            </IconButton>
            <IconButton label="New chat" onClick={() => void handleNewChat()}>
              <Plus className="h-[18px] w-[18px]" strokeWidth={ICON} />
            </IconButton>
          </div>
        </div>

        {showSearch && (
          <div className="px-3 pb-2 animate-fade-up" style={noDrag}>
            <div className="rounded-2xl bg-black/[0.03] p-1 ring-1 ring-black/[0.05]">
              <div className="flex items-center gap-2 rounded-[calc(1rem-0.15rem)] bg-white px-3 py-2">
                <Search className="h-4 w-4 text-[var(--muted)]" strokeWidth={ICON} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search conversations"
                  className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-black/30"
                />
              </div>
            </div>
          </div>
        )}

        <div className="px-4 pb-1 pt-3">
          <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-black/35">
            Conversations
          </p>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
          {loadingSessions && (
            <div className="flex items-center gap-2 px-3 py-4 text-[13px] text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
              Loading…
            </div>
          )}
          {!loadingSessions && filteredSessions.length === 0 && (
            <p className="px-3 py-4 text-[13px] text-[var(--muted)]">
              No conversations yet.
            </p>
          )}
          {filteredSessions.map((s) => {
            const active = s.session_id === activeSessionId;
            return (
              <div
                key={s.session_id}
                className={`group flex w-full items-center gap-0.5 rounded-2xl transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${
                  active
                    ? "bg-white shadow-[0_10px_30px_-18px_rgba(18,20,26,0.35)] ring-1 ring-black/[0.06]"
                    : "hover:bg-black/[0.03]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setActiveSessionId(s.session_id)}
                  className="flex min-w-0 flex-1 items-center gap-2.5 px-2.5 py-2.5 text-left"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                    <MessageSquare className="h-4 w-4" strokeWidth={ICON} />
                  </div>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium">
                      {sessionLabel(s)}
                    </span>
                    {s.last_message && (
                      <span className="mt-0.5 block truncate text-[11px] text-[var(--muted)]">
                        {s.last_message}
                      </span>
                    )}
                  </span>
                </button>
                <button
                  type="button"
                  title="Delete conversation"
                  aria-label="Delete conversation"
                  disabled={deletingId === s.session_id}
                  onClick={(e) => void handleDeleteSession(s.session_id, e)}
                  className="mr-1.5 rounded-xl p-1.5 text-black/25 opacity-0 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-rose-50 hover:text-[var(--danger)] group-hover:opacity-100 disabled:opacity-50"
                >
                  {deletingId === s.session_id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={ICON} />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={ICON} />
                  )}
                </button>
              </div>
            );
          })}
        </nav>

        <div className="relative border-t border-black/[0.06] px-3 py-3">
          {showAccount && (
            <div className="absolute bottom-[calc(100%-0.25rem)] left-3 right-3 z-20 animate-fade-up rounded-[1.25rem] bg-black/[0.04] p-1 ring-1 ring-black/[0.06]">
              <div className="rounded-[calc(1.25rem-0.25rem)] bg-white p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                <div className="mb-2.5 flex items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/35">
                    Email connector
                  </p>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      emailStatus?.connected
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "bg-black/[0.04] text-[var(--muted)]"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        emailStatus?.connected ? "bg-[var(--accent)]" : "bg-black/25"
                      }`}
                    />
                    {emailStatus?.connected ? "Connected" : "Not connected"}
                  </span>
                </div>

                <div className="mb-3 rounded-xl bg-[var(--surface)] px-3 py-2.5">
                  <p className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--ink)]">
                    <Mail className="h-3.5 w-3.5 text-[var(--accent)]" strokeWidth={ICON} />
                    Gmail
                  </p>
                  <p className="mt-1 truncate text-[12px] text-[var(--muted)]">
                    {emailStatus?.connected
                      ? emailStatus.email_address || "Đã kết nối"
                      : "Chưa liên kết tài khoản"}
                  </p>
                </div>

                {emailStatus?.connected ? (
                  <button
                    type="button"
                    disabled={emailBusy}
                    onClick={() => void handleRevokeGmail()}
                    className="group flex w-full items-center justify-between rounded-full bg-rose-50 px-3.5 py-2.5 text-[13px] font-semibold text-rose-700 transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-rose-100 active:scale-[0.98] disabled:opacity-50"
                  >
                    <span className="inline-flex items-center gap-2">
                      {emailBusy ? (
                        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                      ) : (
                        <Unplug className="h-4 w-4" strokeWidth={ICON} />
                      )}
                      Revoke Gmail
                    </span>
                    <ChevronRight className="h-4 w-4 opacity-50 transition group-hover:translate-x-0.5" strokeWidth={ICON} />
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={emailBusy || connectingEmail}
                    onClick={() => void handleConnectGmail()}
                    className="group flex w-full items-center justify-between rounded-full bg-[var(--ink)] px-3.5 py-2.5 text-[13px] font-semibold text-white transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-black active:scale-[0.98] disabled:opacity-50"
                  >
                    <span className="inline-flex items-center gap-2">
                      {emailBusy || connectingEmail ? (
                        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                      ) : (
                        <Link2 className="h-4 w-4" strokeWidth={ICON} />
                      )}
                      Connect Gmail
                    </span>
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15 transition group-hover:translate-x-0.5">
                      <ChevronRight className="h-3.5 w-3.5" strokeWidth={ICON} />
                    </span>
                  </button>
                )}
              </div>
            </div>
          )}

          <div className="rounded-2xl bg-black/[0.03] p-1 ring-1 ring-black/[0.05]">
            <button
              type="button"
              onClick={openAccountMenu}
              className="flex w-full items-center gap-2.5 rounded-[calc(1rem-0.15rem)] bg-white px-2.5 py-2 text-left transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-[var(--surface)] active:scale-[0.99]"
            >
              <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-[var(--panel)] text-[var(--muted)]">
                <CircleUserRound className="h-5 w-5" strokeWidth={ICON} />
                <span
                  className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-white ${
                    emailStatus?.connected ? "bg-[var(--accent)]" : "bg-black/20"
                  }`}
                />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">Demo User</p>
                <p className="truncate text-[11px] text-[var(--muted)]">
                  {DEFAULT_USER_ID}
                  {emailStatus?.connected
                    ? ` · ${emailStatus.email_address || "Gmail on"}`
                    : " · Gmail off"}
                </p>
              </div>
              <ChevronUp
                className={`h-4 w-4 shrink-0 text-[var(--muted)] transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${
                  showAccount ? "" : "rotate-180"
                }`}
                strokeWidth={ICON}
              />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="relative z-[1] flex min-w-0 flex-1 flex-col">
        <header
          className="relative flex h-14 shrink-0 items-center px-5"
          style={dragRegion}
        >
          <div className="flex min-w-0 items-center gap-3" style={noDrag}>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/70 ring-1 ring-black/[0.06]">
              <Bot className="h-4 w-4 text-[var(--accent)]" strokeWidth={ICON} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-[14px] font-semibold tracking-tight">
                {headerTitle}
              </p>
              <p className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    hitlLocked
                      ? "bg-amber-500"
                      : sending
                        ? "animate-pulse bg-[var(--accent)]"
                        : "bg-emerald-500"
                  }`}
                />
                {statusLabel}
              </p>
            </div>
          </div>

          <div
            className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center"
            style={noDrag}
          >
            <IconButton label="Minimize" onClick={() => void api?.minimize()}>
              <Minus className="h-3.5 w-3.5" strokeWidth={ICON} />
            </IconButton>
            <IconButton label="Maximize" onClick={() => void api?.maximize()}>
              <Square className="h-3 w-3" strokeWidth={ICON} />
            </IconButton>
            <IconButton label="Close" danger onClick={() => void api?.close()}>
              <X className="h-3.5 w-3.5" strokeWidth={ICON} />
            </IconButton>
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-y-auto px-6 pt-2 pb-4">
          {banner && (
            <div
              className="mx-auto mb-4 flex w-full max-w-2xl items-start gap-2 rounded-2xl bg-white/80 px-3.5 py-2.5 text-[13px] text-[var(--ink)] ring-1 ring-black/[0.06] animate-fade-up"
              title={banner}
            >
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[var(--accent)]" strokeWidth={ICON} />
              <span className="min-w-0 flex-1 truncate">
                {banner.length > 50 ? `${banner.slice(0, 50)}…` : banner}
              </span>
              <IconButton label="Dismiss" onClick={() => setBanner(null)}>
                <X className="h-3.5 w-3.5" strokeWidth={ICON} />
              </IconButton>
            </div>
          )}
          {error && (
            <div className="mx-auto mb-4 w-full max-w-2xl rounded-2xl bg-rose-50 px-3.5 py-2.5 text-[13px] text-rose-700 ring-1 ring-rose-100">
              {error}
            </div>
          )}

          {!activeSessionId && !loadingSessions && (
            <div className="m-auto flex max-w-md flex-col items-center px-4 text-center animate-fade-up">
              <div className="mb-5 rounded-[1.5rem] bg-black/[0.03] p-1.5 ring-1 ring-black/[0.05]">
                <div className="flex h-16 w-16 items-center justify-center rounded-[calc(1.5rem-0.375rem)] bg-white text-[var(--accent)]">
                  <MessageSquarePlus className="h-7 w-7" strokeWidth={ICON} />
                </div>
              </div>
              <h2 className="font-display text-[34px] leading-none tracking-tight">
                Start a conversation
              </h2>
              <p className="mt-3 text-[14px] leading-relaxed text-[var(--muted)]">
                digitalboo giúp điền standup, đọc mail quan trọng, hoặc hẹn lịch chạy
                tự động.
              </p>
              <button
                type="button"
                onClick={() => void handleNewChat()}
                className="group mt-6 inline-flex items-center gap-2 rounded-full bg-[var(--ink)] px-5 py-3 text-[13px] font-semibold text-white transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-black active:scale-[0.98]"
              >
                New conversation
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/15 transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0.5">
                  <Plus className="h-4 w-4" strokeWidth={ICON} />
                </span>
              </button>
            </div>
          )}

          {activeSessionId && loadingMessages && messages.length === 0 && (
            <div className="m-auto flex items-center gap-2 text-[13px] text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
              Loading messages…
            </div>
          )}

          {showEmptyWorkspace && (
            <div className="m-auto flex w-full max-w-xl flex-col items-center px-4 text-center animate-fade-up">
              <BrandMark size={52} />
              <p className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)] ring-1 ring-black/[0.05]">
                <Sparkles className="h-3 w-3 text-[var(--accent)]" strokeWidth={ICON} />
                digitalboo assistant
              </p>
              <h2 className="font-display mt-3 text-[40px] leading-[0.95] tracking-tight">
                How can I help?
              </h2>
              <p className="mt-3 max-w-md text-[14px] leading-relaxed text-[var(--muted)]">
                Gửi standup, kết nối Gmail, hoặc đặt lịch định kỳ. Mọi thứ giữ trong
                conversation này.
              </p>
              <div className="mt-7 grid w-full gap-2.5 sm:grid-cols-2">
                {HINTS.map(({ icon: Icon, text }) => (
                  <button
                    key={text}
                    type="button"
                    disabled={inputLocked}
                    onClick={() => {
                      setDraft(text);
                      inputRef.current?.focus();
                    }}
                    className="group rounded-[1.25rem] bg-black/[0.03] p-1 text-left ring-1 ring-black/[0.05] transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:-translate-y-0.5 hover:bg-black/[0.045] disabled:opacity-50"
                  >
                    <div className="flex items-start gap-2.5 rounded-[calc(1.25rem-0.25rem)] bg-white/90 px-3.5 py-3.5">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)] transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:scale-105">
                        <Icon className="h-4 w-4" strokeWidth={ICON} />
                      </span>
                      <span className="text-[13px] font-medium leading-snug text-[var(--ink)]">
                        {text}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.length > 0 && (
            <p className="mb-5 text-center text-[12px] text-[var(--muted)]">
              {formatDayLabel(messages[0]?.created_at)}
            </p>
          )}

          <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
            {messages.map((m, i) => {
              const isUser = m.role === "user";
              const showEmailHitl =
                !isUser &&
                Boolean(m.hitl) &&
                hasEmailConnectAction(m.actions) &&
                i === messages.length - 1;
              return (
                <div
                  key={m.localId ?? m.id ?? `${m.role}-${i}`}
                  className="flex flex-col gap-2 animate-fade-up"
                >
                  <div
                    className={`flex ${isUser ? "justify-end" : "items-start gap-3"}`}
                  >
                    {!isUser && <BrandMark size={30} />}
                    <div
                      className={`max-w-[85%] break-words px-4 py-3 text-[14px] leading-relaxed ${
                        isUser
                          ? "whitespace-pre-wrap rounded-[1.35rem] rounded-br-md bg-[var(--ink)] text-white shadow-[0_12px_28px_-16px_rgba(18,20,26,0.55)]"
                          : "rounded-[1.35rem] rounded-tl-md bg-white text-[var(--ink)] ring-1 ring-black/[0.06] shadow-[0_12px_30px_-22px_rgba(18,20,26,0.35)]"
                      }`}
                    >
                      {!isUser && sending && i === messages.length - 1 && !m.content ? (
                        <span className="inline-flex items-center gap-2 text-[var(--muted)]">
                          <Loader2
                            className="h-3.5 w-3.5 animate-spin text-[var(--accent)]"
                            strokeWidth={ICON}
                          />
                          Thinking…
                        </span>
                      ) : isUser ? (
                        m.content
                      ) : (
                        <MarkdownBody content={m.content || ""} />
                      )}
                    </div>
                  </div>

                  {showEmailHitl && (
                    <div className="ml-[42px] max-w-[85%] rounded-[1.25rem] bg-amber-50/90 p-1 ring-1 ring-amber-200/70">
                      <div className="rounded-[calc(1.25rem-0.25rem)] bg-white/70 px-3.5 py-3">
                        <div className="mb-2.5 flex items-center gap-1.5 text-[12px] font-semibold text-amber-800">
                          <Lock className="h-3.5 w-3.5" strokeWidth={ICON} />
                          Action required — chat paused
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {(m.actions || [])
                            .filter((a) => a.type === "oauth_google")
                            .map((action, idx) => (
                              <button
                                key={`${action.type}-${idx}`}
                                type="button"
                                disabled={connectingEmail}
                                onClick={() => openGmailConnect(action)}
                                className="group inline-flex items-center gap-2 rounded-full bg-[var(--ink)] px-4 py-2.5 text-[13px] font-semibold text-white transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-black active:scale-[0.98] disabled:opacity-60"
                              >
                                {connectingEmail ? (
                                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                                ) : (
                                  <Mail className="h-4 w-4" strokeWidth={ICON} />
                                )}
                                {connectingEmail
                                  ? "Connecting…"
                                  : action.label || "Connect Gmail"}
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15 transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0.5">
                                  <ChevronRight className="h-3.5 w-3.5" strokeWidth={ICON} />
                                </span>
                              </button>
                            ))}
                        </div>
                        <p className="mt-2.5 text-[12px] text-amber-800/80">
                          Hoàn tất kết nối Gmail trong popup. Không gõ chat cho đến khi
                          bước này xong.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {sending &&
              !(
                messages.length > 0 &&
                messages[messages.length - 1]?.role === "assistant"
              ) && (
              <div className="flex items-center gap-3 animate-fade-up">
                <BrandMark size={30} />
                <span className="inline-flex items-center gap-2 rounded-[1.25rem] bg-white px-4 py-2.5 text-[14px] text-[var(--muted)] ring-1 ring-black/[0.06]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent)]" strokeWidth={ICON} />
                  Thinking…
                </span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form
          className="shrink-0 px-5 pb-5 pt-2"
          onSubmit={onSubmit}
          style={noDrag}
        >
          {hitlLocked && (
            <p className="mx-auto mb-2 flex max-w-2xl items-center gap-1.5 text-[12px] text-amber-700">
              <Ban className="h-3.5 w-3.5" strokeWidth={ICON} />
              Waiting for Gmail connect — dùng nút phía trên thay vì chat.
            </p>
          )}
          <div className="mx-auto max-w-2xl rounded-[1.75rem] bg-black/[0.035] p-1.5 ring-1 ring-black/[0.06]">
            <div
              className={`flex items-center gap-1.5 rounded-[calc(1.75rem-0.375rem)] px-2.5 py-2 transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${
                inputLocked ? "bg-[var(--panel)]" : "bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
              }`}
            >
              <IconButton
                label="New chat"
                disabled={sending || connectingEmail}
                onClick={() => void handleNewChat()}
              >
                <Plus className="h-5 w-5" strokeWidth={ICON} />
              </IconButton>

              <input
                ref={inputRef}
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  hitlLocked
                    ? "Chat paused — complete the action above"
                    : sending
                      ? "Waiting for response…"
                      : "Message digitalboo"
                }
                disabled={inputLocked}
                className="min-w-0 flex-1 bg-transparent text-[14px] text-[var(--ink)] outline-none placeholder:text-black/30 disabled:cursor-not-allowed disabled:opacity-70"
              />

              <button
                type="submit"
                disabled={inputLocked || !draft.trim()}
                className={`flex h-10 w-10 items-center justify-center rounded-full transition duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] disabled:opacity-40 ${
                  inputLocked
                    ? "bg-black/10 text-[var(--muted)]"
                    : "bg-[var(--accent)] text-white shadow-[0_10px_24px_-12px_rgba(15,118,110,0.7)] hover:bg-[var(--accent-hover)]"
                }`}
                aria-label={inputLocked ? "Chat locked" : "Send"}
                title={
                  hitlLocked
                    ? "Complete HITL action first"
                    : sending
                      ? "Waiting for reply"
                      : "Send"
                }
              >
                {sending || connectingEmail ? (
                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={ICON} />
                ) : hitlLocked ? (
                  <Ban className="h-4 w-4" strokeWidth={ICON} />
                ) : (
                  <SendHorizontal className="h-4 w-4" strokeWidth={ICON} />
                )}
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}

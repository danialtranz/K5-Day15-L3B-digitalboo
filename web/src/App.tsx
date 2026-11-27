import type { CSSProperties } from "react";
import {
  Search,
  Plus,
  Mic,
  Minus,
  Square,
  X,
  Star,
} from "lucide-react";

const dragRegion = { WebkitAppRegion: "drag" } as CSSProperties;
const noDrag = { WebkitAppRegion: "no-drag" } as CSSProperties;

function DigitalIcon({ size = 20 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-full bg-[#3B82F6] shrink-0"
      style={{ width: size, height: size }}
    >
      <div className="flex gap-[3px]">
        <span className="block h-[5px] w-[5px] rounded-full bg-white" />
        <span className="block h-[5px] w-[5px] rounded-full bg-white" />
      </div>
    </div>
  );
}

function WaveIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="5" width="2" height="6" rx="1" fill="white" />
      <rect x="5" y="3" width="2" height="10" rx="1" fill="white" />
      <rect x="9" y="5" width="2" height="6" rx="1" fill="white" />
      <rect x="13" y="4" width="2" height="8" rx="1" fill="white" />
    </svg>
  );
}

function HavenAvatar() {
  return (
    <div className="relative mx-auto h-16 w-16">
      <div className="flex h-full w-full items-center justify-center rounded-full bg-gradient-to-b from-slate-100 to-slate-200 shadow-sm ring-1 ring-black/5">
        {/* Ghost / bean face */}
        <svg viewBox="0 0 64 64" className="h-12 w-12">
          <ellipse cx="32" cy="34" rx="20" ry="22" fill="#F8FAFC" />
          <ellipse cx="32" cy="34" rx="20" ry="22" fill="url(#faceGrad)" />
          <circle cx="24" cy="32" r="3.2" fill="#1E293B" />
          <circle cx="40" cy="32" r="3.2" fill="#1E293B" />
          <circle cx="25.2" cy="30.8" r="1" fill="white" />
          <circle cx="41.2" cy="30.8" r="1" fill="white" />
          <path
            d="M28 40c1.5 2.5 6.5 2.5 8 0"
            stroke="#64748B"
            strokeWidth="1.6"
            strokeLinecap="round"
            fill="none"
          />
          <defs>
            <linearGradient id="faceGrad" x1="32" y1="12" x2="32" y2="56">
              <stop stopColor="#FFFFFF" />
              <stop offset="1" stopColor="#E2E8F0" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-orange-400 shadow-sm ring-2 ring-white">
        <Star className="h-3 w-3 fill-white text-white" />
      </div>
    </div>
  );
}

export default function App() {
  const api = window.electronAPI

  return (
    <div className="flex h-full min-h-screen overflow-hidden bg-white text-[#1A1A1A]">
      {/* ── Sidebar ── */}
      <aside className="flex w-[260px] shrink-0 flex-col border-r border-[#E5E7EB] bg-[#F8F9FA]">
        {/* Top actions — drag region for frameless Electron window */}
        <div
          className="flex items-center justify-between px-4 pt-4"
          style={dragRegion}
        >
          <button
            type="button"
            className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-200/70 hover:text-slate-800"
            style={noDrag}
            aria-label="Search"
          >
            <Search className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-200/70 hover:text-slate-800"
            style={noDrag}
            aria-label="New chat"
          >
            <Plus className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </button>
        </div>

        {/* Profile */}
        <div className="mt-6 flex flex-col items-center px-4">
          <HavenAvatar />
          <p className="mt-2.5 text-[15px] font-medium tracking-tight text-slate-800">
            Haven
          </p>
        </div>

        {/* Chat list */}
        <nav className="mt-8 flex-1 px-3">
          <button
            type="button"
            className="flex w-full items-center gap-2.5 rounded-xl bg-white px-3 py-2.5 text-left shadow-sm ring-1 ring-black/[0.04] transition"
          >
            <DigitalIcon size={22} />
            <span className="text-[14px] font-medium text-slate-800">Digital</span>
          </button>
        </nav>

        {/* Bottom bar */}
        <div className="flex items-center gap-2 border-t border-[#E5E7EB] px-3 py-3">
          <img
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix&backgroundColor=b6e3f4"
            alt="User"
            className="h-8 w-8 rounded-full object-cover ring-1 ring-black/5"
          />
          <button
            type="button"
            className="flex flex-1 items-center gap-2 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 shadow-sm ring-1 ring-black/[0.06] transition hover:bg-slate-50"
          >
            <span>Connect apps</span>
            <span className="ml-auto flex items-center -space-x-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#4A154B] text-[8px] font-bold text-white ring-1 ring-white">
                S
              </span>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black text-[8px] font-bold text-white ring-1 ring-white">
                N
              </span>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#0061FF] text-[8px] font-bold text-white ring-1 ring-white">
                +
              </span>
            </span>
          </button>
        </div>
      </aside>

      {/* ── Main chat ── */}
      <main className="relative flex min-w-0 flex-1 flex-col bg-white">
        {/* Top bar */}
        <header
          className="relative flex h-12 shrink-0 items-center justify-center border-b border-[#F1F5F9]"
          style={dragRegion}
        >
          <div
            className="flex items-center gap-2 rounded-full bg-[#F1F5F9] px-3.5 py-1.5 shadow-sm"
            style={noDrag}
          >
            <DigitalIcon size={18} />
            <span className="text-[13px] font-medium text-slate-700">Digital</span>
          </div>

          {/* Window controls */}
          <div
            className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5 text-slate-400"
            style={noDrag}
          >
            <button
              type="button"
              onClick={() => api?.minimize()}
              className="rounded-md p-2 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label="Minimize"
            >
              <Minus className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
            <button
              type="button"
              onClick={() => api?.maximize()}
              className="rounded-md p-2 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label="Maximize"
            >
              <Square className="h-3 w-3" strokeWidth={2} />
            </button>
            <button
              type="button"
              onClick={() => api?.close()}
              className="rounded-md p-2 transition hover:bg-red-50 hover:text-red-600"
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex flex-1 flex-col px-6 pt-8">
          <p className="mb-6 text-center text-[12px] text-slate-400">
            Today 9:51 PM
          </p>

          <div className="flex items-center gap-2.5">
            <DigitalIcon size={22} />
            <span className="text-[14px] text-slate-500">Typing...</span>
          </div>
        </div>

        {/* Input */}
        <div className="shrink-0 px-5 pb-5 pt-2">
          <div className="flex items-center gap-3 rounded-full bg-[#F1F5F9] px-4 py-2.5 shadow-sm ring-1 ring-black/[0.04]">
            <button
              type="button"
              className="rounded-full p-1 text-slate-500 transition hover:bg-slate-200/80 hover:text-slate-700"
              aria-label="Attach"
            >
              <Plus className="h-5 w-5" strokeWidth={1.75} />
            </button>

            <input
              type="text"
              placeholder="Message Digital"
              className="min-w-0 flex-1 bg-transparent text-[14px] text-slate-800 outline-none placeholder:text-slate-400"
            />

            <button
              type="button"
              className="rounded-full p-1 text-slate-500 transition hover:bg-slate-200/80 hover:text-slate-700"
              aria-label="Voice message"
            >
              <Mic className="h-[18px] w-[18px]" strokeWidth={1.75} />
            </button>

            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-[#3B82F6] shadow-sm transition hover:bg-[#2563EB]"
              aria-label="Voice mode"
            >
              <WaveIcon />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

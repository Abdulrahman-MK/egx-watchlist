/**
 * Header Component for EGX Terminal.
 *
 * Includes:
 * - Localhost identifier (127.0.0.1:8000).
 * - Cairo Live Clock & Market Hours Guard badge.
 * - Live Connection & Streaming Status Indicators.
 * - Stream Pause / Resume Control.
 * - Search & Add stock trigger.
 * - Red 'Exit App' Graceful Shutdown Trigger.
 */

import React, { useState } from 'react';
import {
  Terminal,
  RefreshCw,
  Plus,
  Wifi,
  WifiOff,
  Pause,
  Play,
  Power,
  AlertTriangle,
} from 'lucide-react';
import { MarketStatusBadge } from './MarketStatusBadge';

export function Header({
  connectionStatus,
  streamStatus,
  marketStatus,
  onOpenSearch,
  onRefresh,
  onToggleStream,
  onShutdown,
}) {
  const [showExitConfirm, setShowExitConfirm] = useState(false);

  return (
    <header className="border-b border-terminal-border bg-terminal-card/70 backdrop-blur-md sticky top-0 z-30 px-4 sm:px-6 py-3">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3.5">
        {/* Left: Branding & Local Isolation Indicators */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500/20 via-sky-500/20 to-emerald-500/20 border border-slate-700/60 flex items-center justify-center text-terminal-accent shadow-inner">
            <Terminal className="w-5 h-5 text-sky-400" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono font-extrabold text-lg text-slate-100 tracking-wider">
                EGX TERMINAL
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                127.0.0.1:8000
              </span>
            </div>
            <p className="text-[11px] text-terminal-muted flex items-center gap-1.5 font-sans">
              <span>Egyptian Exchange Live Screener</span>
              <span className="text-slate-600">•</span>
              <span className="font-mono text-[10px] text-sky-400/90">Local Only</span>
            </p>
          </div>
        </div>

        {/* Center: Market Session Hours Guard */}
        <div className="flex items-center">
          <MarketStatusBadge marketStatus={marketStatus} />
        </div>

        {/* Right: Controls & System Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Stream Status & Pause/Resume Toggle */}
          <button
            onClick={onToggleStream}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-mono font-medium transition-all ${
              streamStatus === 'ACTIVE'
                ? 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                : 'bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border-amber-500/40'
            }`}
            title={streamStatus === 'ACTIVE' ? 'Click to Pause upstream quote ingestion' : 'Click to Resume stream'}
          >
            {streamStatus === 'ACTIVE' ? (
              <>
                <Pause className="w-3.5 h-3.5 text-emerald-400" />
                <span>STREAMING</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                <span>PAUSED</span>
              </>
            )}
          </button>

          {/* WebSocket Link Status */}
          <div
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-mono ${
              connectionStatus === 'connected'
                ? 'bg-slate-800/80 text-slate-300 border-slate-700'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            }`}
          >
            {connectionStatus === 'connected' ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                <span>WS LIVE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
                <span>RECONNECTING</span>
              </>
            )}
          </div>

          {/* Refresh Snapshot */}
          <button
            onClick={onRefresh}
            title="Refresh market snapshot"
            className="p-2 rounded-lg bg-terminal-card hover:bg-terminal-cardHover border border-terminal-border text-terminal-muted hover:text-slate-100 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Search Trigger */}
          <button
            onClick={onOpenSearch}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/40 text-sky-300 hover:text-white text-xs font-mono font-semibold transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Search</span>
            <kbd className="hidden lg:inline px-1.5 py-0.2 rounded bg-terminal-bg text-[10px] text-sky-400 border border-terminal-border">
              Ctrl+K
            </kbd>
          </button>

          {/* Red Exit App Button */}
          {!showExitConfirm ? (
            <button
              onClick={() => setShowExitConfirm(true)}
              title="Gracefully shut down EGX Tracker and background server"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 hover:text-rose-100 text-xs font-mono font-semibold transition-all"
            >
              <Power className="w-3.5 h-3.5 text-rose-400" />
              <span>Exit App</span>
            </button>
          ) : (
            <div className="flex items-center gap-1.5 bg-rose-950/90 border border-rose-500/60 p-1 rounded-lg animate-in fade-in duration-150">
              <span className="text-[11px] font-mono text-rose-200 px-1.5 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-rose-400" />
                Confirm Shutdown?
              </span>
              <button
                onClick={() => {
                  setShowExitConfirm(false);
                  onShutdown();
                }}
                className="px-2 py-0.5 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-mono font-bold transition-colors"
              >
                Yes, Exit
              </button>
              <button
                onClick={() => setShowExitConfirm(false)}
                className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

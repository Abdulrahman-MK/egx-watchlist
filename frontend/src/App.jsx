/**
 * Master Application Component for EGX Watchlist Terminal.
 *
 * Implements:
 * - Real-time market streaming orchestration.
 * - Pinned benchmark cards (EGX30, EGX70EWI, EGX100EWI, SHARIAH).
 * - Full EGX watchlist table with cell flashing and sorting.
 * - Search modal with custom IPO ticker addition.
 * - Full-screen graceful shutdown overlay screen.
 */

import React, { useState, useEffect } from 'react';
import { useEGXWebSocket } from './hooks/useEGXWebSocket';
import { Header } from './components/Header';
import { IndexCards } from './components/IndexCards';
import { WatchlistTable } from './components/WatchlistTable';
import { StockSearchModal } from './components/StockSearchModal';
import { ShieldCheck, Info, Sparkles, CheckCircle2, XCircle } from 'lucide-react';

export function App() {
  const {
    connectionStatus,
    streamStatus,
    isShutDown,
    marketStatus,
    indices,
    watchlist,
    quotes,
    flashStates,
    togglePauseStream,
    shutdownApp,
    addToWatchlist,
    addCustomTicker,
    removeFromWatchlist,
    refreshSnapshot,
  } = useEGXWebSocket();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Keyboard shortcut Ctrl+K to trigger search
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleAddStock = async (ticker) => {
    const res = await addToWatchlist(ticker);
    if (res.success) {
      showToast(`Added ${ticker} to your watchlist`, 'success');
    } else {
      showToast(res.message, 'error');
    }
  };

  const handleAddCustomTicker = async (ticker) => {
    const res = await addCustomTicker(ticker);
    if (res.success) {
      showToast(`Subscribed & added EGX:${ticker} to watchlist`, 'success');
    } else {
      showToast(res.message, 'error');
    }
  };

  const handleRemoveStock = async (ticker) => {
    const res = await removeFromWatchlist(ticker);
    if (res.success) {
      showToast(`Removed ${ticker} from your watchlist`, 'info');
    } else {
      showToast(res.message, 'error');
    }
  };

  const handleToggleStream = async () => {
    const res = await togglePauseStream();
    if (res.success) {
      showToast(`Stream ${res.status === 'ACTIVE' ? 'Resumed' : 'Paused'}`, 'info');
    }
  };

  const handleShutdown = async () => {
    await shutdownApp();
  };

  // Graceful System Shutdown Screen
  if (isShutDown) {
    return (
      <div className="min-h-screen bg-[#07090e] text-slate-100 flex items-center justify-center p-6 font-mono">
        <div className="max-w-lg w-full p-8 rounded-2xl bg-terminal-card border border-terminal-border shadow-2xl text-center space-y-5 animate-in fade-in duration-300">
          <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold tracking-wider text-slate-100">
              SYSTEM SAFELY SHUT DOWN
            </h2>
            <p className="text-xs text-terminal-muted leading-relaxed font-sans">
              Upstream TradingView feeds have been disconnected, SQLite database handles committed, and the backend process terminated.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-terminal-bg border border-terminal-border text-[11px] text-slate-400 text-left space-y-1">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span>Port 127.0.0.1:8000 Released</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-400 font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span>Watchlist Saved to SQLite</span>
            </div>
          </div>

          <button
            onClick={() => window.close()}
            className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold tracking-wide transition-colors"
          >
            Close Window
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-terminal-bg text-slate-100 flex flex-col font-sans selection:bg-terminal-accent/30 selection:text-white">
      {/* Top Fixed Header */}
      <Header
        connectionStatus={connectionStatus}
        streamStatus={streamStatus}
        marketStatus={marketStatus}
        onOpenSearch={() => setIsSearchOpen(true)}
        onRefresh={refreshSnapshot}
        onToggleStream={handleToggleStream}
        onShutdown={handleShutdown}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Section 1: Pinned Benchmark Indices Bar */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h2 className="text-xs font-mono font-bold text-terminal-muted uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Core Benchmark Indices</span>
            </h2>
            <span className="text-[11px] text-terminal-muted font-mono hidden sm:inline">
              4 Pinned Cards • Real-Time Stream
            </span>
          </div>

          <IndexCards
            indices={indices}
            flashStates={flashStates}
          />
        </div>

        {/* Section 2: Watchlist Table */}
        <div>
          <WatchlistTable
            watchlist={watchlist}
            quotes={quotes}
            flashStates={flashStates}
            onRemove={handleRemoveStock}
            onOpenSearch={() => setIsSearchOpen(true)}
          />
        </div>

        {/* Informational Footer / Market Guard Info */}
        <div className="p-4 rounded-xl bg-terminal-card/40 border border-terminal-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-terminal-muted font-mono">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-terminal-accent shrink-0" />
            <span>
              EGX Trading Schedule: <strong>Sunday through Thursday (10:00 - 14:30 Cairo Time)</strong>.
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Local 127.0.0.1 Data Stream • SQLite Persistence</span>
          </div>
        </div>
      </main>

      {/* Stock Search Modal with Full Directory & Custom IPO Ticker */}
      <StockSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        watchlist={watchlist}
        onAddStock={handleAddStock}
        onAddCustomTicker={handleAddCustomTicker}
        onRemoveStock={handleRemoveStock}
      />

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 duration-200">
          <div className={`px-4 py-2.5 rounded-xl border shadow-xl text-xs font-mono flex items-center gap-2 ${
            toast.type === 'success'
              ? 'bg-emerald-950/90 border-emerald-500/40 text-emerald-300'
              : toast.type === 'error'
              ? 'bg-rose-950/90 border-rose-500/40 text-rose-300'
              : 'bg-slate-900/90 border-slate-700 text-slate-200'
          }`}>
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

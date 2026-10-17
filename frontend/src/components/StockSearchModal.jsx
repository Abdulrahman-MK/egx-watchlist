/**
 * Stock Search Modal Component.
 *
 * Searches the local SQLite database of ~296+ EGX securities (synced from TradingView Egypt Scanner).
 * Includes an immediate fallback "Add Custom EGX Ticker: [INPUT]" button allowing any ticker
 * (e.g., ACTF, COPR, or newly listed IPOs) to be added and subscribed to directly as EGX:[INPUT].
 */

import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Plus, Check, Building2, Sparkles, PlusCircle } from 'lucide-react';

export function StockSearchModal({
  isOpen,
  onClose,
  watchlist,
  onAddStock,
  onAddCustomTicker,
  onRemoveStock,
}) {
  const [query, setQuery] = useState('');
  const [stocksList, setStocksList] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  // Fetch stocks from SQLite backend API on query change
  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      const cleanQ = query.trim();
      const apiBase = typeof window !== 'undefined'
        ? (window.location.port === '5173' ? `${window.location.protocol}//${window.location.hostname}:8000/api` : `${window.location.protocol}//${window.location.host}/api`)
        : '/api';
      fetch(`${apiBase}/symbols?q=${encodeURIComponent(cleanQ)}`)
        .then(res => res.json())
        .then(data => {
          setStocksList(data.symbols || []);
          setLoading(false);
        })
        .catch(err => {
          console.error('Failed to search symbols:', err);
          setLoading(false);
        });

      setTimeout(() => {
        if (inputRef.current) inputRef.current.focus();
      }, 50);
    }
  }, [isOpen, query]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const cleanQueryTicker = query.trim().toUpperCase().replace(/^EGX:/, '');
  const exactMatchExists = stocksList.some(s => s.ticker.toUpperCase() === cleanQueryTicker);
  const isCustomCandidate = cleanQueryTicker.length >= 2 && !exactMatchExists;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl bg-terminal-card border border-terminal-border shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header & Search Bar */}
        <div className="p-4 border-b border-terminal-border bg-terminal-bg/70">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-mono text-sm font-bold text-slate-100 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-terminal-accent" />
              <span>SEARCH EGX SECURITIES DIRECTORY</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-terminal-border text-terminal-muted">
                ~296 Stocks
              </span>
            </h3>
            <button
              onClick={onClose}
              className="p-1 rounded-md text-terminal-muted hover:text-slate-100 hover:bg-terminal-border transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-terminal-muted" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search ticker, company name, or Arabic name (e.g. ACTF, COPR, فوري, حديد عز)..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-terminal-bg border border-terminal-border text-sm text-slate-100 placeholder:text-terminal-muted focus:outline-none focus:border-terminal-accent font-sans transition-colors"
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-terminal-muted hover:text-slate-200 text-xs font-mono"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Fallback Custom Ticker Button */}
        {cleanQueryTicker.length >= 2 && (
          <div className="p-3 bg-sky-950/40 border-b border-sky-800/40 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-mono text-sky-200">
              <Sparkles className="w-4 h-4 text-sky-400 shrink-0" />
              <span>
                Add any stock/IPO: <strong className="text-white font-bold">EGX:{cleanQueryTicker}</strong>
              </span>
            </div>
            <button
              onClick={() => {
                onAddCustomTicker(cleanQueryTicker);
                onClose();
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-mono font-bold transition-all shadow-md shrink-0"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Add Custom EGX Ticker: {cleanQueryTicker}</span>
            </button>
          </div>
        )}

        {/* Results List */}
        <div className="overflow-y-auto p-3 divide-y divide-terminal-border/30 flex-1">
          {loading ? (
            <div className="py-12 text-center text-terminal-muted font-mono text-xs">
              Filtering EGX securities directory...
            </div>
          ) : stocksList.length === 0 ? (
            <div className="py-12 text-center text-terminal-muted space-y-3 font-mono text-xs">
              <p>No securities matched "{query}"</p>
              <p className="text-[11px] text-slate-400 font-sans max-w-sm mx-auto">
                You can still track it immediately! Click the blue button above to subscribe to <strong>EGX:{cleanQueryTicker}</strong> directly.
              </p>
            </div>
          ) : (
            stocksList.map((stock) => {
              const inWatchlist = watchlist.includes(stock.ticker);

              return (
                <div
                  key={stock.ticker}
                  className="py-3 px-3 hover:bg-terminal-cardHover/60 rounded-xl transition-colors flex items-center justify-between gap-4"
                >
                  {/* Left: Ticker & Names */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono font-bold text-xs px-2 py-0.5 rounded bg-terminal-bg border border-terminal-border text-terminal-accent">
                        {stock.ticker}
                      </span>
                      <span className="text-xs font-semibold text-slate-200 truncate">
                        {stock.name_en}
                      </span>
                      {stock.is_custom === 1 && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
                          Custom
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-terminal-muted">
                      {stock.name_ar && (
                        <>
                          <span className="font-sans text-slate-300" dir="rtl">{stock.name_ar}</span>
                          <span className="text-terminal-border">•</span>
                        </>
                      )}
                      <span>{stock.sector}</span>
                      {stock.base_price > 0 && (
                        <>
                          <span className="text-terminal-border">•</span>
                          <span className="font-mono text-slate-400">Ref: ~{stock.base_price} EGP</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Right: Add / Remove Button */}
                  <div>
                    {inWatchlist ? (
                      <button
                        onClick={() => onRemoveStock(stock.ticker)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-rose-500/20 text-emerald-400 hover:text-rose-400 border border-emerald-500/30 hover:border-rose-500/30 text-xs font-mono font-medium transition-all group"
                      >
                        <Check className="w-3.5 h-3.5 group-hover:hidden" />
                        <X className="w-3.5 h-3.5 hidden group-hover:inline" />
                        <span className="group-hover:hidden">In Watchlist</span>
                        <span className="hidden group-hover:inline">Remove</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => onAddStock(stock.ticker)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 border border-sky-500/40 text-xs font-mono font-medium transition-all shadow-sm"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-terminal-border bg-terminal-bg/80 flex items-center justify-between text-[11px] text-terminal-muted font-mono">
          <span>{stocksList.length} EGX Securities matching query</span>
          <span className="text-slate-400">Press ESC to dismiss</span>
        </div>
      </div>
    </div>
  );
}

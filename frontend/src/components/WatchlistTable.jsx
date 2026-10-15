import React, { useState, useMemo } from 'react';
import { Trash2, ArrowUpDown, ChevronUp, ChevronDown, PlusCircle } from 'lucide-react';
import { formatPrice, formatChange, formatVolume, formatTimestamp } from '../utils/formatters';

export function WatchlistTable({
  watchlist,
  quotes,
  flashStates,
  onRemove,
  onOpenSearch,
}) {
  const [sortField, setSortField] = useState('ticker');
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc' | 'desc'
  const [displayLang, setDisplayLang] = useState('dual'); // 'dual' | 'en' | 'ar'

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const tableData = useMemo(() => {
    const rows = watchlist.map((sym) => {
      const q = quotes[sym] || {};
      return {
        ticker: sym,
        name_en: q.name_en || sym,
        name_ar: q.name_ar || sym,
        sector: q.sector || '—',
        sector_ar: q.sector_ar || '',
        last_price: q.last_price !== undefined ? q.last_price : null,
        change: q.change !== undefined ? q.change : null,
        change_pct: q.change_pct !== undefined ? q.change_pct : null,
        high: q.high !== undefined ? q.high : null,
        low: q.low !== undefined ? q.low : null,
        volume: q.volume || 0,
        updated_at: q.updated_at || '',
      };
    });

    return rows.sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];

      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;

      if (typeof valA === 'string') {
        return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortOrder === 'asc' ? valA - valB : valB - valA;
    });
  }, [watchlist, quotes, sortField, sortOrder]);

  const renderSortIcon = (field) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />;
    }
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-3 h-3 text-terminal-accent" />
    ) : (
      <ChevronDown className="w-3 h-3 text-terminal-accent" />
    );
  };

  return (
    <div className="rounded-xl bg-terminal-card border border-terminal-border shadow-sm overflow-hidden">
      {/* Table Toolbar */}
      <div className="p-4 border-b border-terminal-border/80 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="font-mono text-base font-bold text-slate-100 tracking-wide flex items-center gap-2">
            <span>MY WATCHLIST</span>
            <span className="px-2 py-0.5 rounded text-xs bg-terminal-cardHover border border-terminal-border text-terminal-accent">
              {watchlist.length} Stocks
            </span>
          </h2>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Language Toggle */}
          <div className="inline-flex rounded-lg border border-terminal-border p-0.5 bg-terminal-bg/50 text-xs font-mono">
            <button
              onClick={() => setDisplayLang('dual')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                displayLang === 'dual' ? 'bg-terminal-card border border-terminal-borderLight text-slate-100 font-semibold' : 'text-terminal-muted hover:text-slate-200'
              }`}
            >
              Dual (EN/AR)
            </button>
            <button
              onClick={() => setDisplayLang('en')}
              className={`px-2 py-1 rounded-md transition-colors ${
                displayLang === 'en' ? 'bg-terminal-card border border-terminal-borderLight text-slate-100 font-semibold' : 'text-terminal-muted hover:text-slate-200'
              }`}
            >
              EN
            </button>
            <button
              onClick={() => setDisplayLang('ar')}
              className={`px-2 py-1 rounded-md transition-colors ${
                displayLang === 'ar' ? 'bg-terminal-card border border-terminal-borderLight text-slate-100 font-semibold' : 'text-terminal-muted hover:text-slate-200'
              }`}
            >
              عربي
            </button>
          </div>

          {/* Quick Add Button */}
          <button
            onClick={onOpenSearch}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-400 text-xs font-mono font-medium transition-all"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>Add Stock</span>
          </button>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-terminal-bg/80 border-b border-terminal-border text-[11px] font-mono text-terminal-muted uppercase tracking-wider">
              <th className="py-3 px-4 group cursor-pointer" onClick={() => handleSort('ticker')}>
                <div className="flex items-center gap-1.5">
                  <span>Ticker</span>
                  {renderSortIcon('ticker')}
                </div>
              </th>

              <th className="py-3 px-4 group cursor-pointer" onClick={() => handleSort('name_en')}>
                <div className="flex items-center gap-1.5">
                  <span>Company Name</span>
                  {renderSortIcon('name_en')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer" onClick={() => handleSort('last_price')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>Last Price (EGP)</span>
                  {renderSortIcon('last_price')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer" onClick={() => handleSort('change')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>Change</span>
                  {renderSortIcon('change')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer" onClick={() => handleSort('change_pct')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>Change %</span>
                  {renderSortIcon('change_pct')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer hidden md:table-cell" onClick={() => handleSort('high')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>High</span>
                  {renderSortIcon('high')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer hidden md:table-cell" onClick={() => handleSort('low')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>Low</span>
                  {renderSortIcon('low')}
                </div>
              </th>

              <th className="py-3 px-3 text-right group cursor-pointer hidden sm:table-cell" onClick={() => handleSort('volume')}>
                <div className="flex items-center justify-end gap-1.5">
                  <span>Volume</span>
                  {renderSortIcon('volume')}
                </div>
              </th>

              <th className="py-3 px-3 text-right hidden lg:table-cell font-mono">
                <span>Updated</span>
              </th>

              <th className="py-3 px-3 text-center w-12 font-mono">
                <span>Action</span>
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-terminal-border/40 font-mono">
            {tableData.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-12 text-center text-terminal-muted">
                  <div className="max-w-sm mx-auto space-y-2">
                    <p className="text-sm font-sans">Your watchlist is currently empty.</p>
                    <button
                      onClick={onOpenSearch}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/20 text-sky-400 hover:bg-sky-500/30 text-xs transition"
                    >
                      <PlusCircle className="w-3.5 h-3.5" />
                      Browse & Add EGX Stocks
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              tableData.map((row) => {
                const flash = flashStates[row.ticker];
                const { text: changeText, pctText, isPositive, isNegative } = formatChange(row.change, row.change_pct);

                const flashCellClass = flash === 'up'
                  ? 'animate-flashGreen'
                  : flash === 'down'
                  ? 'animate-flashRed'
                  : '';

                return (
                  <tr
                    key={row.ticker}
                    className="hover:bg-terminal-cardHover/70 transition-colors group"
                  >
                    {/* Ticker */}
                    <td className="py-3 px-4 font-bold text-slate-100 flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-terminal-bg border border-terminal-border text-terminal-accent text-xs">
                        {row.ticker}
                      </span>
                    </td>

                    {/* Company Name */}
                    <td className="py-3 px-4">
                      {displayLang === 'dual' && (
                        <div>
                          <div className="font-sans font-medium text-slate-200 text-xs truncate max-w-[220px]">
                            {row.name_en}
                          </div>
                          <div className="font-sans text-[11px] text-terminal-muted truncate max-w-[220px]" dir="rtl">
                            {row.name_ar}
                          </div>
                        </div>
                      )}
                      {displayLang === 'en' && (
                        <div>
                          <div className="font-sans font-medium text-slate-200 text-xs truncate max-w-[240px]">
                            {row.name_en}
                          </div>
                          <div className="text-[10px] text-terminal-muted">{row.sector}</div>
                        </div>
                      )}
                      {displayLang === 'ar' && (
                        <div dir="rtl">
                          <div className="font-sans font-medium text-slate-200 text-xs truncate max-w-[240px]">
                            {row.name_ar}
                          </div>
                          <div className="text-[10px] text-terminal-muted">{row.sector_ar || row.sector}</div>
                        </div>
                      )}
                    </td>

                    {/* Last Price (with Flash Highlight) */}
                    <td className={`py-3 px-3 text-right font-bold text-slate-50 text-sm font-tabular ${flashCellClass}`}>
                      {formatPrice(row.last_price)}
                    </td>

                    {/* Change */}
                    <td className={`py-3 px-3 text-right font-medium font-tabular ${
                      isPositive ? 'text-emerald-400' : isNegative ? 'text-rose-400' : 'text-slate-400'
                    }`}>
                      {changeText}
                    </td>

                    {/* Change % */}
                    <td className="py-3 px-3 text-right font-semibold font-tabular">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] ${
                        isPositive
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                          : isNegative
                          ? 'bg-rose-500/15 text-rose-400 border border-rose-500/25'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {pctText}
                      </span>
                    </td>

                    {/* High */}
                    <td className="py-3 px-3 text-right text-slate-300 font-tabular hidden md:table-cell">
                      {formatPrice(row.high)}
                    </td>

                    {/* Low */}
                    <td className="py-3 px-3 text-right text-slate-300 font-tabular hidden md:table-cell">
                      {formatPrice(row.low)}
                    </td>

                    {/* Volume */}
                    <td className="py-3 px-3 text-right text-slate-400 font-tabular hidden sm:table-cell">
                      {formatVolume(row.volume)}
                    </td>

                    {/* Last Updated */}
                    <td className="py-3 px-3 text-right text-[11px] text-terminal-muted font-tabular hidden lg:table-cell">
                      {formatTimestamp(row.updated_at)}
                    </td>

                    {/* Remove Action */}
                    <td className="py-3 px-3 text-center">
                      <button
                        onClick={() => onRemove(row.ticker)}
                        title={`Remove ${row.ticker} from watchlist`}
                        className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors opacity-70 group-hover:opacity-100"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

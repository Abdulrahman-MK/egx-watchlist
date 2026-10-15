import React from 'react';
import { TrendingUp, TrendingDown, ShieldCheck, Activity } from 'lucide-react';
import { formatPrice, formatChange } from '../utils/formatters';

const PINNED_INDEX_KEYS = [
  { key: 'EGX30', label: 'EGX 30', nameAr: 'إيجي إكس 30', desc: 'Main Benchmark' },
  { key: 'EGX70EWI', label: 'EGX 70 EWI', nameAr: 'إيجي إكس 70', desc: 'SME & Growth' },
  { key: 'EGX100EWI', label: 'EGX 100 EWI', nameAr: 'إيجي إكس 100', desc: 'Broad Market' },
  { key: 'SHARIAH', label: 'EGX 33 Shariah', nameAr: 'مؤشر الشريعة', desc: 'Shariah Compliant', isShariah: true },
];

export function IndexCards({ indices, flashStates }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
      {PINNED_INDEX_KEYS.map((item) => {
        const quote = indices[item.key] || {};
        const flash = flashStates[item.key];
        const lastPrice = quote.last_price;
        const change = quote.change;
        const changePct = quote.change_pct;
        const { text: changeText, pctText, isPositive, isNegative } = formatChange(change, changePct);

        const flashClass = flash === 'up'
          ? 'animate-flashGreen border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
          : flash === 'down'
          ? 'animate-flashRed border-rose-500/80 shadow-[0_0_15px_rgba(244,63,94,0.3)]'
          : 'border-terminal-border hover:border-terminal-borderLight';

        return (
          <div
            key={item.key}
            className={`relative p-4 rounded-xl bg-terminal-card border transition-all duration-300 shadow-sm overflow-hidden ${flashClass}`}
          >
            {/* Header / Titles */}
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono font-bold text-sm text-slate-100 tracking-wider">
                    {item.label}
                  </span>
                  {item.isShariah && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      <ShieldCheck className="w-3 h-3" />
                      شريعة
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-terminal-muted flex items-center gap-1 mt-0.5" dir="rtl">
                  <span>{item.nameAr}</span>
                </div>
              </div>

              {/* Status / Trend Icon */}
              <div className={`p-1.5 rounded-lg ${isPositive ? 'bg-emerald-500/10 text-emerald-400' : isNegative ? 'bg-rose-500/10 text-rose-400' : 'bg-slate-800 text-slate-400'}`}>
                {isPositive ? (
                  <TrendingUp className="w-4 h-4" />
                ) : isNegative ? (
                  <TrendingDown className="w-4 h-4" />
                ) : (
                  <Activity className="w-4 h-4" />
                )}
              </div>
            </div>

            {/* Price & Change */}
            <div className="mt-1 flex items-baseline justify-between">
              <div className="font-mono font-bold text-2xl text-slate-50 tracking-tight font-tabular">
                {formatPrice(lastPrice, true)}
              </div>

              <div className={`font-mono text-xs font-semibold px-2 py-0.5 rounded flex items-center gap-1 ${
                isPositive
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                  : isNegative
                  ? 'bg-rose-500/15 text-rose-400 border border-rose-500/20'
                  : 'bg-slate-800 text-slate-400'
              }`}>
                <span>{changeText}</span>
                <span>({pctText})</span>
              </div>
            </div>

            {/* Daily Range & Prev Close Footer */}
            <div className="mt-3 pt-2.5 border-t border-terminal-border/60 flex items-center justify-between text-[11px] text-terminal-muted font-mono">
              <div>
                <span>Low: </span>
                <span className="text-slate-300 font-tabular">{formatPrice(quote.low, true)}</span>
              </div>
              <div className="text-right">
                <span>High: </span>
                <span className="text-slate-300 font-tabular">{formatPrice(quote.high, true)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

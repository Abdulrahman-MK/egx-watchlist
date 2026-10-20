import React from 'react';
import { TrendingUp, TrendingDown, ShieldCheck, Activity } from 'lucide-react';
import { formatPrice, formatChange } from '../utils/formatters';

const PINNED_INDEX_KEYS = [
  { key: 'EGX30', label: 'EGX 30', nameAr: 'إيجي إكس 30', desc: 'Main Benchmark' },
  { key: 'EGX70EWI', label: 'EGX 70 EWI', nameAr: 'إيجي إكس 70', desc: 'SME & Growth' },
  { key: 'EGX100EWI', label: 'EGX 100 EWI', nameAr: 'إيجي إكس 100', desc: 'Broad Market' },
  { key: 'SHARIAH', label: 'EGX 33 Shariah', nameAr: 'مؤشر الشريعة', desc: 'Shariah Compliant', isShariah: true },
];

/**
 * Trajectory sparkline plotting session Open (Start) -> Low/High -> Close (End).
 */
function IntradaySparkline({ open, low, high, close, isPositive }) {
  if (!close || !open) return null;

  const validLow = low !== null && low !== undefined ? Math.min(low, open, close) : Math.min(open, close);
  const validHigh = high !== null && high !== undefined ? Math.max(high, open, close) : Math.max(open, close);
  const range = validHigh - validLow || 1;

  // 4 trajectory milestones: Start (Open) -> Extremum 1 -> Extremum 2 -> End (Close)
  const points = isPositive
    ? [open, validLow, validHigh, close]
    : [open, validHigh, validLow, close];

  const width = 180;
  const height = 40;
  const paddingY = 6;
  const availableHeight = height - paddingY * 2;

  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * width;
    const y = height - paddingY - ((val - validLow) / range) * availableHeight;
    return { x, y };
  });

  let pathD = `M ${coords[0].x} ${coords[0].y}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const p0 = coords[i];
    const p1 = coords[i + 1];
    const mx = (p0.x + p1.x) / 2;
    pathD += ` C ${mx} ${p0.y}, ${mx} ${p1.y}, ${p1.x} ${p1.y}`;
  }

  const fillD = `${pathD} L ${width} ${height} L 0 ${height} Z`;
  const strokeColor = isPositive ? '#10b981' : '#f43f5e';
  const gradId = `spark-grad-${Math.round(open)}-${Math.round(close)}`;

  return (
    <div className="w-full mt-3 mb-1">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-10 overflow-visible"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.30" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <path d={fillD} fill={`url(#${gradId})`} />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.2" strokeLinecap="round" />
        {/* Start node */}
        <circle cx={coords[0].x} cy={coords[0].y} r="3" fill="#38bdf8" stroke="#0f172a" strokeWidth="1.5" />
        {/* End node */}
        <circle cx={coords[coords.length - 1].x} cy={coords[coords.length - 1].y} r="3.5" fill={strokeColor} stroke="#0f172a" strokeWidth="1.5" />
      </svg>

      {/* Starting point and End point markers */}
      <div className="flex items-center justify-between text-[10px] font-mono mt-1">
        <span className="flex items-center gap-1 text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
          <span>Start: <strong className="text-slate-200 font-semibold">{formatPrice(open, true)}</strong></span>
        </span>
        <span className="flex items-center gap-1 text-slate-400">
          <span className={`w-1.5 h-1.5 rounded-full ${isPositive ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
          <span>End: <strong className="text-slate-200 font-semibold">{formatPrice(close, true)}</strong></span>
        </span>
      </div>
    </div>
  );
}

export function IndexCards({ indices, flashStates, onSelectIndex }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
      {PINNED_INDEX_KEYS.map((item) => {
        const quote = indices[item.key] || {};
        const flash = flashStates[item.key];
        const lastPrice = quote.last_price;
        const change = quote.change;
        const changePct = quote.change_pct;
        const { text: changeText, pctText, isPositive, isNegative } = formatChange(change, changePct);

        const openPrice = quote.open || quote.prev_close;
        const lowPrice = quote.low || lastPrice;
        const highPrice = quote.high || lastPrice;

        // Day range calculation %
        const dayRangeSpan = (highPrice - lowPrice) || 1;
        const dayRangePct = Math.min(100, Math.max(0, ((lastPrice - lowPrice) / dayRangeSpan) * 100));

        const flashClass = flash === 'up'
          ? 'animate-flashGreen border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
          : flash === 'down'
          ? 'animate-flashRed border-rose-500/80 shadow-[0_0_15px_rgba(244,63,94,0.3)]'
          : 'border-terminal-border hover:border-terminal-borderLight';

        return (
          <div
            key={item.key}
            onClick={() => onSelectIndex && onSelectIndex(item.key)}
            title={`Click to view ${item.label} multi-timeframe chart and market catalysts`}
            className={`relative p-4 rounded-xl bg-terminal-card border transition-all duration-300 shadow-sm overflow-hidden flex flex-col justify-between cursor-pointer hover:border-sky-500/50 active:scale-[0.99] ${flashClass}`}
          >
            {/* Header / Titles */}
            <div>
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

              {/* Trajectory Sparkline Graph (Start -> Low/High -> End) */}
              <IntradaySparkline
                open={openPrice}
                low={lowPrice}
                high={highPrice}
                close={lastPrice}
                isPositive={isPositive}
              />
            </div>

            {/* Daily Range & Channel Bar */}
            <div className="mt-2 pt-2 border-t border-terminal-border/60">
              <div className="flex items-center justify-between text-[10px] text-terminal-muted font-mono mb-1">
                <span>Low: <strong className="text-slate-300 font-tabular">{formatPrice(lowPrice, true)}</strong></span>
                <span>High: <strong className="text-slate-300 font-tabular">{formatPrice(highPrice, true)}</strong></span>
              </div>
              <div className="w-full h-1.5 bg-slate-800/80 rounded-full overflow-hidden relative">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${isPositive ? 'bg-emerald-500' : 'bg-rose-500'}`}
                  style={{ width: `${dayRangePct}%` }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

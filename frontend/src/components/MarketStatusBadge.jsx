import React from 'react';
import { Clock, AlertCircle, CheckCircle2, Calendar } from 'lucide-react';

export function MarketStatusBadge({ marketStatus }) {
  if (!marketStatus) return null;

  const { is_open, status, cairo_time, next_open, trading_hours } = marketStatus;

  let badgeConfig = {
    bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    dot: 'bg-emerald-400',
    pulse: true,
    label: 'MARKET OPEN',
    icon: CheckCircle2,
  };

  if (status === 'WEEKEND') {
    badgeConfig = {
      bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
      dot: 'bg-amber-400',
      pulse: false,
      label: 'WEEKEND (EGX CLOSED)',
      icon: Calendar,
    };
  } else if (status === 'PRE_MARKET') {
    badgeConfig = {
      bg: 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400',
      dot: 'bg-cyan-400',
      pulse: true,
      label: 'PRE-MARKET',
      icon: Clock,
    };
  } else if (!is_open || status === 'CLOSED') {
    badgeConfig = {
      bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
      dot: 'bg-rose-400',
      pulse: false,
      label: 'MARKET CLOSED',
      icon: AlertCircle,
    };
  }

  const IconComponent = badgeConfig.icon;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Primary Badge */}
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-mono font-medium tracking-wide ${badgeConfig.bg}`}>
        <span className="relative flex h-2 w-2">
          {badgeConfig.pulse && (
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${badgeConfig.dot}`} />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${badgeConfig.dot}`} />
        </span>
        <IconComponent className="w-3.5 h-3.5" />
        <span>{badgeConfig.label}</span>
      </div>

      {/* Cairo Clock & Hours */}
      {cairo_time && (
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-terminal-card border border-terminal-border text-xs text-terminal-muted font-mono">
          <Clock className="w-3 h-3 text-terminal-accent" />
          <span>Cairo: <strong className="text-slate-200">{cairo_time.split(' ')[1] || cairo_time}</strong></span>
          <span className="text-terminal-border">|</span>
          <span className="text-[11px] text-slate-400">{trading_hours}</span>
        </div>
      )}

      {/* Next session indicator if closed */}
      {!is_open && next_open && (
        <div className="hidden md:flex items-center gap-1 px-2 py-0.5 rounded bg-terminal-card/80 border border-terminal-border text-[11px] text-amber-400/90 font-mono">
          <span>Opens: {next_open.split(' ')[0]} 10:00 Cairo</span>
        </div>
      )}
    </div>
  );
}

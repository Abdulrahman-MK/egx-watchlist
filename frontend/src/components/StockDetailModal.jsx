/**
 * Interactive Stock Detail Modal Component with Multi-Timeframe Charts & Scraped News Catalysts.
 *
 * Design & Financial Rationale:
 * ------------------------------
 * 1. Multi-Timeframe Charting (1D, 1W, 1M, 1Y):
 *    - '1D' resets every day at 09:00 AM Cairo time (1 hour before market opens at 10:00 AM).
 *      The session chart anchors at today's opening auction price, showing intraday progression
 *      strictly for today's trading rather than comparing against yesterday.
 *    - '1W', '1M', and '1Y' illustrate swing, monthly, and annual support/resistance trends.
 * 2. Scraped News & Catalyst Pressure Engine:
 *    - Scrapes trusted financial aggregators for real-time company coverage.
 *    - Classifies headlines into BULLISH, BEARISH, or NEUTRAL catalysts with explanatory
 *      annotations detailing whether forces are pulling the stock UP or pushing it DOWN.
 * 3. Institutional Bloomberg/Reuters Terminal Theme:
 *    - Pure tabular typography, zero emojis, high-contrast badges, and interactive SVG crosshairs.
 */

import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  X,
  TrendingUp,
  TrendingDown,
  Activity,
  Calendar,
  Globe,
  ExternalLink,
  RefreshCw,
  Clock,
  Layers,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { formatPrice, formatChange, formatVolume, formatTimestamp } from '../utils/formatters';

export function StockDetailModal({ ticker, onClose, quotes = {} }) {
  const [timeframe, setTimeframe] = useState('1D'); // '1D' | '1W' | '1M' | '1Y'
  const [activeTab, setActiveTab] = useState('chart'); // 'chart' | 'news'
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(true);
  const [newsData, setNewsData] = useState(null);
  const [newsLoading, setNewsLoading] = useState(true);
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  const quote = quotes[ticker] || {};

  // Close on ESC key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Fetch Chart Data on ticker or timeframe change
  useEffect(() => {
    if (!ticker) return;
    let isMounted = true;
    setChartLoading(true);

    fetch(`/api/symbols/chart/${ticker}?timeframe=${timeframe}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (isMounted) {
          setChartData(data);
          setChartLoading(false);
        }
      })
      .catch((err) => {
        console.warn('Failed to load chart data:', err);
        if (isMounted) setChartLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [ticker, timeframe]);

  // Fetch News and Catalyst Sentiment
  useEffect(() => {
    if (!ticker) return;
    let isMounted = true;
    setNewsLoading(true);

    fetch(`/api/symbols/news/${ticker}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (isMounted) {
          setNewsData(data);
          setNewsLoading(false);
        }
      })
      .catch((err) => {
        console.warn('Failed to load news data:', err);
        if (isMounted) setNewsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [ticker]);

  // Derived Financial Metrics
  const currentPrice = chartData?.current_price || quote.last_price || 0.0;
  const anchorPrice = chartData?.anchor_price || quote.open || quote.prev_close || currentPrice;
  const delta = chartData ? chartData.change : (currentPrice - anchorPrice);
  const deltaPct = chartData ? chartData.change_pct : (anchorPrice > 0 ? (delta / anchorPrice) * 100 : 0);
  const isPositive = delta >= 0;

  const candles = chartData?.candles || [];
  const activePoint = hoverIndex !== null && candles[hoverIndex] ? candles[hoverIndex] : null;

  // Pointer & Touch Movement Handler (Mathematical 1:1 SVG User-Space Coordinate Mapping)
  const updateHoverIndex = (clientX, clientY) => {
    if (!svgRef.current || !chartGeometry || candles.length === 0) return;
    const svg = svgRef.current;
    let svgX = null;

    // Utilize getScreenCTM() to invert DOM screen space into exact SVG internal viewBox space.
    // This eliminates any aspect ratio letterboxing, display scaling, or container margin distortions.
    const ctm = svg.getScreenCTM();
    if (ctm) {
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const transformed = pt.matrixTransform(ctm.inverse());
      svgX = transformed.x;
    } else {
      const rect = svg.getBoundingClientRect();
      svgX = ((clientX - rect.left) / rect.width) * chartGeometry.width;
    }

    if (svgX !== null) {
      const minX = chartGeometry.padding.left;
      const maxX = chartGeometry.width - chartGeometry.padding.right;
      const clampedX = Math.max(minX, Math.min(maxX, svgX));
      const pct = (clampedX - minX) / chartGeometry.plotW;
      const idx = Math.round(pct * (candles.length - 1));
      if (idx >= 0 && idx < candles.length) {
        setHoverIndex(idx);
      }
    }
  };

  const handleMouseMove = (e) => {
    updateHoverIndex(e.clientX, e.clientY);
  };

  const handleTouchMove = (e) => {
    if (e.touches && e.touches.length > 0) {
      updateHoverIndex(e.touches[0].clientX, e.touches[0].clientY);
    }
  };

  // SVG Chart Geometry Calculations
  const chartGeometry = useMemo(() => {
    if (!candles || candles.length === 0) return null;

    const width = 680;
    const height = 240;
    const padding = { top: 20, right: 25, bottom: 30, left: 55 };

    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const allPrices = candles.flatMap((c) => [c.high, c.low, c.close, c.open]);
    if (anchorPrice > 0) allPrices.push(anchorPrice);

    let minPrice = Math.min(...allPrices);
    let maxPrice = Math.max(...allPrices);

    // Add 2% padding so lines don't clip at top/bottom
    const priceRange = maxPrice - minPrice || 1.0;
    minPrice = minPrice - priceRange * 0.03;
    maxPrice = maxPrice + priceRange * 0.03;

    // Retain thousandths precision for small-cap equities (< 20 EGP)
    const priceDecimals = minPrice < 20 ? 3 : 2;

    const getX = (idx) => {
      if (candles.length === 1) return padding.left + plotW / 2;
      return padding.left + (idx / (candles.length - 1)) * plotW;
    };

    const getY = (price) => {
      return padding.top + plotH - ((price - minPrice) / (maxPrice - minPrice)) * plotH;
    };

    // Build SVG Path
    const points = candles.map((c, i) => `${getX(i).toFixed(1)},${getY(c.close).toFixed(1)}`);
    const linePath = `M ${points.join(' L ')}`;

    // Build Area Path
    const firstX = getX(0).toFixed(1);
    const lastX = getX(candles.length - 1).toFixed(1);
    const bottomY = (padding.top + plotH).toFixed(1);
    const areaPath = `M ${firstX},${bottomY} L ${points.join(' L ')} L ${lastX},${bottomY} Z`;

    // Anchor Line (Session Open for 1D)
    const anchorY = getY(anchorPrice);

    // Price Grid Lines (4 horizontal ticks)
    const yTicks = [0, 0.33, 0.66, 1].map((pct) => {
      const p = minPrice + pct * (maxPrice - minPrice);
      return { price: p, y: getY(p) };
    });

    return {
      width,
      height,
      padding,
      plotW,
      plotH,
      minPrice,
      maxPrice,
      priceDecimals,
      getX,
      getY,
      linePath,
      areaPath,
      anchorY,
      yTicks,
    };
  }, [candles, anchorPrice]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl bg-terminal-card border border-terminal-border shadow-2xl overflow-hidden font-sans text-slate-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="p-4 sm:p-5 border-b border-terminal-border/80 bg-terminal-bg/60 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded-lg bg-sky-500/10 border border-sky-500/30 font-mono text-sm font-bold text-sky-400">
              {ticker}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold text-slate-100 leading-tight">
                  {chartData?.name_en || quote.name_en || ticker}
                </h1>
                {chartData?.name_ar && (
                  <span className="text-xs text-terminal-muted font-sans" dir="rtl">
                    ({chartData.name_ar})
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-terminal-muted">
                <span>{chartData?.sector || quote.sector || 'Listed Equity'}</span>
                <span>•</span>
                <span>Currency: {chartData?.currency || quote.currency || 'EGP'}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Live Price and Change Display */}
            <div className="text-right">
              <div className="text-xl font-mono font-bold text-slate-100">
                {formatPrice(currentPrice)} <span className="text-xs text-slate-400 font-sans font-normal">EGP</span>
              </div>
              <div className="flex items-center justify-end gap-1.5 text-xs font-mono font-semibold">
                <span className={isPositive ? 'text-emerald-400' : 'text-rose-400'}>
                  {isPositive ? '+' : ''}{delta.toFixed(currentPrice < 20 ? 3 : 2)} ({isPositive ? '+' : ''}{deltaPct.toFixed(2)}%)
                </span>
                <span className="text-[10px] text-terminal-muted font-normal">
                  ({timeframe === '1D' ? 'Session' : timeframe})
                </span>
              </div>
            </div>

            {/* Close Modal Button */}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
              title="Close modal (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab Switcher & Timeframe Selector */}
        <div className="px-5 py-2.5 border-b border-terminal-border/60 bg-terminal-card/80 flex flex-wrap items-center justify-between gap-3">
          {/* Navigation Tabs */}
          <div className="flex items-center gap-1.5 bg-terminal-bg/80 p-1 rounded-xl border border-terminal-border text-xs font-medium">
            <button
              onClick={() => setActiveTab('chart')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'chart'
                  ? 'bg-terminal-card border border-terminal-borderLight text-slate-100 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-sky-400" />
              <span>Interactive Chart</span>
            </button>
            <button
              onClick={() => setActiveTab('news')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'news'
                  ? 'bg-terminal-card border border-terminal-borderLight text-slate-100 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Globe className="w-3.5 h-3.5 text-amber-400" />
              <span>Scraped News & Catalysts</span>
              {newsData && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300">
                  {newsData.total_articles}
                </span>
              )}
            </button>
          </div>

          {/* Timeframe Selector (Only shown on Chart tab) */}
          {activeTab === 'chart' && (
            <div className="flex items-center gap-1 bg-terminal-bg/80 p-1 rounded-xl border border-terminal-border text-xs font-mono">
              {[
                { id: '1D', label: '1D (Session)' },
                { id: '1W', label: '1W' },
                { id: '1M', label: '1M' },
                { id: '1Y', label: '1Y' },
              ].map((tf) => (
                <button
                  key={tf.id}
                  onClick={() => {
                    setTimeframe(tf.id);
                    setHoverIndex(null);
                  }}
                  className={`px-3 py-1 rounded-lg transition-colors ${
                    timeframe === tf.id
                      ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title={tf.id === '1D' ? 'Daily session resets at 09:00 AM Cairo time' : `${tf.id} History`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Modal Body Container */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5">
          {/* TAB 1: CHART VIEW */}
          {activeTab === 'chart' && (
            <div className="space-y-4">
              {/* Daily Reset & Anchor Indicator */}
              <div className="flex flex-wrap items-center justify-between text-xs font-mono text-slate-400 bg-terminal-bg/50 p-2.5 rounded-xl border border-terminal-border/60">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-sky-400" />
                  <span>
                    Anchor Baseline: <strong className="text-slate-200">{formatPrice(anchorPrice)} EGP</strong>
                    {timeframe === '1D' ? ' (Session Open)' : ` (${timeframe} Horizon)`}
                  </span>
                </div>
                {timeframe === '1D' && (
                  <div className="text-[11px] text-terminal-muted">
                    Session resets daily at 09:00 AM Cairo (1h before open)
                  </div>
                )}
              </div>

              {/* Chart SVG Rendering */}
              <div className="relative w-full rounded-xl bg-terminal-bg border border-terminal-border p-3 overflow-hidden">
                {chartLoading ? (
                  <div className="h-64 flex flex-col items-center justify-center gap-3 text-slate-400 font-mono text-xs">
                    <RefreshCw className="w-6 h-6 animate-spin text-sky-400" />
                    <span>Streaming authentic market series from TradingView...</span>
                  </div>
                ) : chartGeometry ? (
                  <div className="w-full overflow-x-auto">
                    <svg
                      ref={svgRef}
                      viewBox={`0 0 ${chartGeometry.width} ${chartGeometry.height}`}
                      preserveAspectRatio="none"
                      className="w-full h-64 select-none cursor-crosshair touch-none"
                      onMouseLeave={() => setHoverIndex(null)}
                      onMouseMove={handleMouseMove}
                      onTouchStart={handleTouchMove}
                      onTouchMove={handleTouchMove}
                      onTouchEnd={() => setHoverIndex(null)}
                    >
                      <defs>
                        <linearGradient id="chartGradientGreen" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity="0.28" />
                          <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                        </linearGradient>
                        <linearGradient id="chartGradientRed" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.28" />
                          <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
                        </linearGradient>
                      </defs>

                      {/* Horizontal Price Grid Lines */}
                      {chartGeometry.yTicks.map((tick, i) => (
                        <g key={i}>
                          <line
                            x1={chartGeometry.padding.left}
                            y1={tick.y}
                            x2={chartGeometry.width - chartGeometry.padding.right}
                            y2={tick.y}
                            stroke="#1e293b"
                            strokeDasharray="3 3"
                            strokeWidth="1"
                          />
                          <text
                            x={chartGeometry.padding.left - 8}
                            y={tick.y + 3}
                            textAnchor="end"
                            fill="#64748b"
                            fontSize="10"
                            fontFamily="monospace"
                          >
                            {tick.price.toFixed(chartGeometry.priceDecimals)}
                          </text>
                        </g>
                      ))}

                      {/* Anchor Reference Line (Session Open) */}
                      {anchorPrice > 0 && (
                        <line
                          x1={chartGeometry.padding.left}
                          y1={chartGeometry.anchorY}
                          x2={chartGeometry.width - chartGeometry.padding.right}
                          y2={chartGeometry.anchorY}
                          stroke="#38bdf8"
                          strokeDasharray="4 4"
                          strokeWidth="1.2"
                          opacity="0.7"
                        />
                      )}

                      {/* Area Fill */}
                      <path
                        d={chartGeometry.areaPath}
                        fill={isPositive ? 'url(#chartGradientGreen)' : 'url(#chartGradientRed)'}
                      />

                      {/* Main Price Line */}
                      <path
                        d={chartGeometry.linePath}
                        fill="none"
                        stroke={isPositive ? '#10b981' : '#f43f5e'}
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />

                      {/* Interactive Crosshair & Hover Tooltip */}
                      {activePoint && hoverIndex !== null && (
                        <g>
                          {/* Vertical Hairline */}
                          <line
                            x1={chartGeometry.getX(hoverIndex)}
                            y1={chartGeometry.padding.top}
                            x2={chartGeometry.getX(hoverIndex)}
                            y2={chartGeometry.height - chartGeometry.padding.bottom}
                            stroke="#94a3b8"
                            strokeDasharray="2 2"
                            strokeWidth="1"
                          />
                          {/* Focal Point Indicator */}
                          <circle
                            cx={chartGeometry.getX(hoverIndex)}
                            cy={chartGeometry.getY(activePoint.close)}
                            r="4.5"
                            fill={isPositive ? '#10b981' : '#f43f5e'}
                            stroke="#0f172a"
                            strokeWidth="2"
                          />
                        </g>
                      )}
                    </svg>
                  </div>
                ) : (
                  <div className="h-64 flex items-center justify-center text-slate-500 font-mono text-xs">
                    No series points available for this timeframe.
                  </div>
                )}

                {/* Hover Details Panel */}
                {activePoint && (
                  <div
                    className={`absolute top-3 ${
                      hoverIndex !== null && hoverIndex > candles.length / 2 ? 'left-4' : 'right-4'
                    } bg-slate-900/95 border border-slate-700/80 rounded-lg p-2.5 shadow-xl text-xs font-mono space-y-1 pointer-events-none transition-all duration-75`}
                  >
                    <div className="text-slate-400 text-[11px]">
                      {timeframe === '1D'
                        ? new Date(activePoint.time * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
                        : new Date(activePoint.time * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                    <div className="text-slate-100 font-bold">
                      Price: {formatPrice(activePoint.close)} EGP
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-2">
                      <span>O: {formatPrice(activePoint.open)}</span>
                      <span>H: {formatPrice(activePoint.high)}</span>
                      <span>L: {formatPrice(activePoint.low)}</span>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Volume: {formatVolume(activePoint.volume)}
                    </div>
                  </div>
                )}
              </div>

              {/* Key Financial Statistics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-terminal-bg border border-terminal-border">
                  <div className="text-[11px] font-mono text-terminal-muted">Day Open (Anchor)</div>
                  <div className="text-sm font-mono font-bold text-slate-100 mt-1">
                    {formatPrice(chartData?.open || quote.open || anchorPrice)} EGP
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-terminal-bg border border-terminal-border">
                  <div className="text-[11px] font-mono text-terminal-muted">Range High ({timeframe})</div>
                  <div className="text-sm font-mono font-bold text-emerald-400 mt-1">
                    {formatPrice(chartData?.high || quote.high || currentPrice)} EGP
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-terminal-bg border border-terminal-border">
                  <div className="text-[11px] font-mono text-terminal-muted">Range Low ({timeframe})</div>
                  <div className="text-sm font-mono font-bold text-rose-400 mt-1">
                    {formatPrice(chartData?.low || quote.low || currentPrice)} EGP
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-terminal-bg border border-terminal-border">
                  <div className="text-[11px] font-mono text-terminal-muted">Session Volume</div>
                  <div className="text-sm font-mono font-bold text-slate-100 mt-1">
                    {formatVolume(chartData?.volume || quote.volume || 0)}
                  </div>
                </div>
              </div>

              {/* Technical Signal & Momentum Panel */}
              <div className="p-3.5 rounded-xl bg-terminal-bg border border-terminal-border flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Technical Consensus:</span>
                  <span
                    className={`px-2.5 py-0.5 rounded text-[11px] font-bold ${
                      quote.signal === 'BULLISH'
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : quote.signal === 'BEARISH'
                        ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {quote.signal || 'NEUTRAL'}
                  </span>
                  <span className="text-slate-500 text-[11px]">
                    (Score: {quote.rating_score !== undefined ? quote.rating_score : 0.0})
                  </span>
                </div>

                {quote.rsi && (
                  <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                    <span>RSI (14):</span>
                    <strong className="text-slate-200">{Number(quote.rsi).toFixed(1)}</strong>
                    <span className="text-slate-500">
                      ({Number(quote.rsi) > 70 ? 'Overbought' : Number(quote.rsi) < 30 ? 'Oversold' : 'Neutral Range'})
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: SCRAPED NEWS & CATALYSTS VIEW */}
          {activeTab === 'news' && (
            <div className="space-y-4">
              {newsLoading ? (
                <div className="h-48 flex flex-col items-center justify-center gap-3 text-slate-400 font-mono text-xs">
                  <RefreshCw className="w-5 h-5 animate-spin text-amber-400" />
                  <span>Aggregating real-time financial headlines and evaluating catalysts...</span>
                </div>
              ) : newsData ? (
                <>
                  {/* Consensus Catalyst Card */}
                  <div className="p-4 rounded-xl bg-terminal-bg border border-terminal-border space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                          Consensus Directional Catalyst:
                        </span>
                        <span
                          className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold flex items-center gap-1 ${
                            newsData.overall_catalyst === 'BULLISH_CATALYST'
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                              : newsData.overall_catalyst === 'BEARISH_CATALYST'
                              ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}
                        >
                          {newsData.overall_catalyst === 'BULLISH_CATALYST' && <ArrowUpRight className="w-3.5 h-3.5" />}
                          {newsData.overall_catalyst === 'BEARISH_CATALYST' && <ArrowDownRight className="w-3.5 h-3.5" />}
                          <span>{newsData.overall_catalyst.replace('_', ' ')}</span>
                        </span>
                      </div>
                      <span className="text-xs font-mono text-terminal-muted">
                        {newsData.articles.length} Recent Articles
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed font-sans">
                      {newsData.overall_summary}
                    </p>
                  </div>

                  {/* Scraped Articles List */}
                  <div className="space-y-2.5">
                    {newsData.articles.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-terminal-bg/70 border border-terminal-border/80 hover:border-terminal-borderLight hover:bg-terminal-bg transition-colors space-y-2"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold">
                              {item.source}
                            </span>
                            <span className="text-slate-500">{item.published_at}</span>
                          </div>

                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              item.catalyst === 'BULLISH'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : item.catalyst === 'BEARISH'
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                : 'bg-slate-800/80 text-slate-400 border border-slate-700/50'
                            }`}
                          >
                            {item.catalyst === 'BULLISH' ? 'Bullish Catalyst (Upward)' : item.catalyst === 'BEARISH' ? 'Bearish Catalyst (Downward)' : 'Neutral Context'}
                          </span>
                        </div>

                        {/* Article Headline */}
                        <a
                          href={item.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-sm font-medium text-slate-100 hover:text-sky-400 transition-colors group flex items-start justify-between gap-2"
                          dir={item.language === 'ar' ? 'rtl' : 'ltr'}
                        >
                          <span>{item.title}</span>
                          <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-sky-400 shrink-0 mt-1" />
                        </a>

                        {/* Directional Impact Analysis */}
                        <div className="text-[11px] text-slate-400 bg-slate-900/60 p-2 rounded-lg border border-slate-800/80">
                          <strong className="text-slate-300 font-mono">Potential Price Impact: </strong>
                          <span>{item.impact}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="p-8 text-center text-slate-500 font-mono text-xs">
                  No verified news articles available for this security.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export default StockDetailModal;

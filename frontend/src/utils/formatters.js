/**
 * Formatting utilities for Egyptian Exchange financial metrics.
 */

export function formatPrice(value, isIndex = false) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  const decimals = isIndex ? 2 : (value < 10 ? 3 : 2);
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatChange(change, changePct) {
  if (change === null || change === undefined || isNaN(change)) {
    return { text: '—', pctText: '0.00%', isPositive: false, isNegative: false };
  }
  const isPositive = change > 0;
  const isNegative = change < 0;
  const sign = isPositive ? '+' : '';
  
  return {
    text: `${sign}${Number(change).toFixed(2)}`,
    pctText: `${sign}${Number(changePct || 0).toFixed(2)}%`,
    isPositive,
    isNegative,
  };
}

export function formatVolume(volume) {
  if (!volume || isNaN(volume)) return '0';
  const v = Number(volume);
  if (v >= 1_000_000_000) {
    return (v / 1_000_000_000).toFixed(2) + 'B';
  }
  if (v >= 1_000_000) {
    return (v / 1_000_000).toFixed(2) + 'M';
  }
  if (v >= 1_000) {
    return (v / 1_000).toFixed(1) + 'K';
  }
  return v.toLocaleString('en-US');
}

export function formatTimestamp(timeStr) {
  if (!timeStr) return '—';
  // If timeStr is already "YYYY-MM-DD HH:MM:SS", return the time portion
  if (timeStr.includes(' ')) {
    return timeStr.split(' ')[1];
  }
  try {
    const d = new Date(timeStr);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return timeStr;
  }
}

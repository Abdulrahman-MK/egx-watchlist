/**
 * Formatting utilities for Egyptian Exchange financial metrics.
 */

export function formatPrice(value, isIndex = false) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  const num = Number(value);
  // Benchmark indices: standard 2 decimal places (e.g. 52,089.00)
  // Equities: For stocks below 20 EGP (e.g. COPR at 0.439), format in thousandths (3 decimals)
  // or 4 decimals if active 4th decimal exists, preserving fluid charts and real buy precision
  let decimals = 2;
  if (!isIndex) {
    if (num < 20) {
      decimals = 3;
      const str = num.toString();
      const fracPart = str.split('.')[1] || '';
      if (fracPart.length >= 4 && fracPart[3] !== '0') {
        decimals = 4;
      }
    }
  }
  return num.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatChange(change, changePct) {
  if (change === null || change === undefined || isNaN(change)) {
    return { text: '—', pctText: '0.00%', isPositive: false, isNegative: false };
  }
  const num = Number(change);
  const isPositive = num > 0;
  const isNegative = num < 0;
  const sign = isPositive ? '+' : '';
  const absVal = Math.abs(num);
  // Preserve thousandths for fractional changes (< 1.0) so changes like -0.001 are visible
  const decimals = absVal > 0 && absVal < 1 ? 3 : 2;

  return {
    text: `${sign}${num.toFixed(decimals)}`,
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

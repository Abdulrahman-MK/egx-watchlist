/**
 * Custom React Hook for Real-Time EGX WebSocket Streaming.
 *
 * Manages:
 * - WebSocket connection with automatic backoff reconnection to ws://127.0.0.1:8000/ws.
 * - Live quote ticks and cell flash directional states ('up' | 'down').
 * - Stream pause and resume toggling.
 * - System graceful shutdown events.
 * - Local Watchlist synchronization with backend SQLite database.
 * - Adding custom / IPO tickers directly.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://127.0.0.1:8000/ws';
const API_BASE = 'http://127.0.0.1:8000/api';

export function useEGXWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // 'connected' | 'connecting' | 'disconnected'
  const [streamStatus, setStreamStatus] = useState('ACTIVE'); // 'ACTIVE' | 'PAUSED'
  const [isShutDown, setIsShutDown] = useState(false);
  const [marketStatus, setMarketStatus] = useState({
    is_open: true,
    status: 'OPEN',
    message: 'Connecting to EGX terminal...',
    cairo_time: '',
    next_open: '',
    trading_hours: '10:00 - 14:30 Cairo',
  });
  const [indices, setIndices] = useState({});
  const [watchlist, setWatchlist] = useState([]);
  const [quotes, setQuotes] = useState({});
  const [flashStates, setFlashStates] = useState({}); // { [ticker]: 'up' | 'down' }

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const flashTimeoutsRef = useRef({});

  // Trigger temporary flash state for a ticker
  const triggerFlash = useCallback((ticker, direction) => {
    if (!ticker || !direction) return;

    if (flashTimeoutsRef.current[ticker]) {
      clearTimeout(flashTimeoutsRef.current[ticker]);
    }

    setFlashStates(prev => ({ ...prev, [ticker]: direction }));

    flashTimeoutsRef.current[ticker] = setTimeout(() => {
      setFlashStates(prev => {
        const next = { ...prev };
        delete next[ticker];
        return next;
      });
      delete flashTimeoutsRef.current[ticker];
    }, 1200);
  }, []);

  // Update a single quote and detect tick direction
  const handleTickUpdate = useCallback((newQuote) => {
    if (!newQuote || !newQuote.ticker) return;
    const ticker = newQuote.ticker;

    setQuotes(prevQuotes => {
      const prevQuote = prevQuotes[ticker];
      let direction = null;

      if (prevQuote && prevQuote.last_price !== undefined) {
        if (newQuote.last_price > prevQuote.last_price) {
          direction = 'up';
        } else if (newQuote.last_price < prevQuote.last_price) {
          direction = 'down';
        }
      }

      if (direction) {
        triggerFlash(ticker, direction);
      }

      const merged = {
        ...(prevQuote || {}),
        ...newQuote,
        tickDirection: direction,
      };

      return {
        ...prevQuotes,
        [ticker]: merged,
      };
    });

    // Pinned indices check
    if (newQuote.is_index || ['EGX30', 'EGX70EWI', 'EGX100EWI', 'SHARIAH'].includes(ticker)) {
      setIndices(prevIndices => ({
        ...prevIndices,
        [ticker]: {
          ...(prevIndices[ticker] || {}),
          ...newQuote,
        }
      }));
    }
  }, [triggerFlash]);

  // Connect WebSocket
  useEffect(() => {
    let isMounted = true;

    function connect() {
      if (isShutDown) return;
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        return;
      }

      setConnectionStatus('connecting');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        setConnectionStatus('connected');
        console.log('[WebSocket] Connected to EGX backend at', WS_URL);
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'INITIAL_STATE') {
            if (msg.market) setMarketStatus(msg.market);
            if (msg.stream_status) setStreamStatus(msg.stream_status);
            if (msg.watchlist) setWatchlist(msg.watchlist);
            if (msg.indices) setIndices(msg.indices);
            if (msg.quotes) setQuotes(msg.quotes);
          } else if (msg.type === 'TICK') {
            handleTickUpdate(msg.data);
          } else if (msg.type === 'STREAM_STATUS') {
            if (msg.status) setStreamStatus(msg.status);
          } else if (msg.type === 'SYSTEM_SHUTDOWN') {
            setIsShutDown(true);
            setConnectionStatus('disconnected');
            if (wsRef.current) wsRef.current.close();
          } else if (msg.type === 'MARKET_STATUS') {
            if (msg.data) setMarketStatus(msg.data);
          } else if (msg.type === 'WATCHLIST_UPDATED') {
            if (msg.watchlist) setWatchlist(msg.watchlist);
            if (msg.new_quote) {
              handleTickUpdate(msg.new_quote);
            }
          }
        } catch (err) {
          console.error('[WebSocket] Parse error:', err);
        }
      };

      ws.onclose = () => {
        if (!isMounted || isShutDown) return;
        setConnectionStatus('disconnected');
        console.log('[WebSocket] Disconnected. Reconnecting in 3s...');
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.warn('[WebSocket] Warning:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
      Object.values(flashTimeoutsRef.current).forEach(clearTimeout);
    };
  }, [handleTickUpdate, isShutDown]);

  // Pause / Resume Stream
  const togglePauseStream = async () => {
    try {
      const endpoint = streamStatus === 'ACTIVE' ? `${API_BASE}/system/pause` : `${API_BASE}/system/resume`;
      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setStreamStatus(data.status);
        return { success: true, status: data.status };
      }
      return { success: false, message: 'Failed to toggle stream' };
    } catch (e) {
      console.error('Error toggling stream:', e);
      return { success: false, message: e.message };
    }
  };

  // Graceful System Shutdown
  const shutdownApp = async () => {
    try {
      setIsShutDown(true);
      await fetch(`${API_BASE}/system/shutdown`, { method: 'POST' });
      return { success: true };
    } catch (e) {
      console.error('Shutdown request initiated:', e);
      setIsShutDown(true);
      return { success: true };
    }
  };

  // Add symbol to watchlist via API
  const addToWatchlist = async (symbol) => {
    try {
      const clean = symbol.trim().toUpperCase();
      const res = await fetch(`${API_BASE}/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: clean }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setWatchlist(prev => prev.includes(clean) ? prev : [...prev, clean]);
        return { success: true, message: data.message };
      }
      return { success: false, message: data.message || data.detail || 'Failed to add' };
    } catch (e) {
      console.error('Error adding symbol:', e);
      return { success: false, message: e.message };
    }
  };

  // Add custom / IPO ticker
  const addCustomTicker = async (ticker) => {
    try {
      const clean = ticker.trim().toUpperCase().replace(/^EGX:/, '');
      const res = await fetch(`${API_BASE}/symbols/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: clean }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Automatically add to active watchlist as well
        return await addToWatchlist(clean);
      }
      return { success: false, message: data.message || 'Failed to register custom ticker' };
    } catch (e) {
      console.error('Error registering custom ticker:', e);
      return { success: false, message: e.message };
    }
  };

  // Remove symbol from watchlist via API
  const removeFromWatchlist = async (symbol) => {
    try {
      const clean = symbol.trim().toUpperCase();
      const res = await fetch(`${API_BASE}/watchlist/${encodeURIComponent(clean)}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setWatchlist(prev => prev.filter(s => s !== clean));
        return { success: true, message: data.message };
      }
      return { success: false, message: data.message || data.detail || 'Failed to remove' };
    } catch (e) {
      console.error('Error removing symbol:', e);
      return { success: false, message: e.message };
    }
  };

  // Manual snapshot refresh
  const refreshSnapshot = async () => {
    try {
      const res = await fetch(`${API_BASE}/snapshot`);
      if (res.ok) {
        const data = await res.json();
        if (data.market) setMarketStatus(data.market);
        if (data.indices) setIndices(data.indices);
        if (data.raw) setQuotes(data.raw);
      }
    } catch (e) {
      console.error('Error refreshing snapshot:', e);
    }
  };

  return {
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
  };
}

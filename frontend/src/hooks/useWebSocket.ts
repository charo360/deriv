import { useState, useEffect, useCallback, useRef } from 'react';
import { BotState, WebSocketMessage } from '../types';

const apiBaseFromEnv =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL;
const wsBase =
  apiBaseFromEnv?.replace(/^http/i, (match) =>
    match.toLowerCase() === 'https' ? 'wss' : 'ws'
  ) || `ws://${window.location.hostname}:8000`;
const WS_URL = `${wsBase.replace(/\/$/, '')}/ws`;

export function useWebSocket() {
  const [state, setState] = useState<BotState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        if (message.type === 'state_update') {
          setState(message.data);
        } else if (message.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      wsRef.current = null;

      // Reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { state, isConnected, reconnect: connect };
}

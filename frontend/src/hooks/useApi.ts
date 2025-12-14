import { useState, useCallback, useEffect } from 'react';

const apiBaseFromEnv =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL;
const API_BASE = (apiBaseFromEnv || `http://${window.location.hostname}:8000`)
  .replace(/\/$/, '') + '/api';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Clear error after 5 seconds automatically
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const request = useCallback(async (
    endpoint: string,
    method: string = 'GET',
    body?: object
  ) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
      }

      return data;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Unknown error';
      setError(message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const startBot = useCallback((apiToken: string) => {
    return request('/start', 'POST', { api_token: apiToken });
  }, [request]);

  const stopBot = useCallback(() => {
    return request('/stop', 'POST');
  }, [request]);

  const enableTrading = useCallback(() => {
    return request('/trading/enable', 'POST');
  }, [request]);

  const disableTrading = useCallback(() => {
    return request('/trading/disable', 'POST');
  }, [request]);

  const manualTrade = useCallback((direction: 'CALL' | 'PUT') => {
    return request('/trade', 'POST', { direction });
  }, [request]);

  const updateSettings = useCallback((settings: object) => {
    return request('/settings', 'PUT', settings);
  }, [request]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    loading,
    error,
    clearError,
    startBot,
    stopBot,
    enableTrading,
    disableTrading,
    manualTrade,
    updateSettings,
  };
}

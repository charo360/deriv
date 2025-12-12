import { useState, useCallback } from 'react';

const API_BASE = `http://${window.location.hostname}:8000/api`;

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return {
    loading,
    error,
    startBot,
    stopBot,
    enableTrading,
    disableTrading,
    manualTrade,
    updateSettings,
  };
}

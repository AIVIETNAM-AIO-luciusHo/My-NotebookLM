import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';

// Trạng thái backend: GET /health định kỳ (và khi gọi refresh).
export const useHealth = (intervalMs = 5000) => {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setHealth(await api.health());
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, intervalMs);
    return () => clearInterval(t);
  }, [refresh, intervalMs]);

  return { health, error, refresh };
};

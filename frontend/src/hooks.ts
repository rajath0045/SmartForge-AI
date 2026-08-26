import { useCallback, useEffect, useRef, useState } from 'react';

export function useAsyncData<T>(loader: () => Promise<T>, initial: T) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await loaderRef.current());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void reload(); }, [reload]);
  return { data, loading, error, reload, setData };
}

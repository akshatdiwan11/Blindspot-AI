import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
}

/** Runs `fn` when `deps` change; exposes loading / error / reload. Ignores stale responses. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [tick, setTick] = useState(0);
  // Key of the request whose result is currently held. Loading is derived from it, so there is
  // never a render where a newly enabled request looks finished before it has started.
  const [settledKey, setSettledKey] = useState<string | null>(null);
  const seq = useRef(0);
  const key = JSON.stringify([...deps, tick]);

  useEffect(() => {
    if (!enabled) return;
    const id = ++seq.current;
    setError(undefined);
    fn().then(
      (d) => { if (id === seq.current) { setData(d); setSettledKey(key); } },
      (e) => { if (id === seq.current) { setError(e instanceof Error ? e : new Error(String(e))); setSettledKey(key); } },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const loading = enabled && settledKey !== key;
  return { data, error: loading ? undefined : error, loading, reload, setData };
}

/** Wraps an async action with pending + error state. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();
  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    setPending(true);
    setError(undefined);
    try {
      return await fn(...args);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setPending(false);
    }
  }, [fn]);
  return { run, pending, error, setError };
}

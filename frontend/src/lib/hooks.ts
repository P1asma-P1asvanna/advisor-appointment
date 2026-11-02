import { DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

/** Load data on mount and whenever `deps` change. `reload()` refetches without flashing a spinner. */
export function useLoad<T>(fn: () => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);

  const run = useCallback(async (silent: boolean) => {
    const n = ++seq.current;
    if (!silent) setLoading(true);
    try {
      const d = await fnRef.current();
      if (n === seq.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (n === seq.current) setError(e instanceof ApiError ? e.message : "เกิดข้อผิดพลาด");
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => void run(false), deps);
  return { data, error, loading, reload: () => run(true) };
}

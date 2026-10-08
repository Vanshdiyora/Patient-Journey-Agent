import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync(asyncFn, deps = [], enabled = true) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null });
  const requestId = useRef(0);

  const execute = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const data = await asyncFn();
      if (currentRequest === requestId.current) setState({ data, loading: false, error: null });
      return data;
    } catch (error) {
      if (currentRequest === requestId.current) setState({ data: null, loading: false, error });
      throw error;
    }
  }, deps);

  useEffect(() => {
    if (enabled) execute().catch(() => {});
    return () => { requestId.current += 1; };
  }, [execute, enabled]);

  return { ...state, refetch: execute };
}

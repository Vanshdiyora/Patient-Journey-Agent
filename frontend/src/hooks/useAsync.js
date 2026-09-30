import { useCallback, useEffect, useState } from "react";

export function useAsync(asyncFn, deps = [], enabled = true) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null });

  const execute = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const data = await asyncFn();
      setState({ data, loading: false, error: null });
      return data;
    } catch (error) {
      setState({ data: null, loading: false, error });
      throw error;
    }
  }, deps);

  useEffect(() => {
    if (enabled) execute().catch(() => {});
  }, [execute, enabled]);

  return { ...state, refetch: execute };
}

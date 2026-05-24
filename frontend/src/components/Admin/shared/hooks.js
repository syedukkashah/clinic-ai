import { useEffect, useRef, useState } from "react";

export function useAdminResource(loader, deps = []) {
  const [state, setState] = useState({ loading: true, result: null });

  const load = async () => {
    setState((current) => ({ ...current, loading: true }));
    const result = await loader();
    setState({ loading: false, result });
  };

  useEffect(() => {
    load();
  }, deps);

  return { ...state, reload: load, data: state.result?.data, ok: Boolean(state.result?.ok) };
}

export function useCountUp(targetValue, duration = 400) {
  const [value, setValue] = useState(Number(targetValue) || 0);
  const startRef = useRef(value);

  useEffect(() => {
    const target = Number(targetValue) || 0;
    startRef.current = value;
    const start = performance.now();
    let frame;
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(startRef.current + (target - startRef.current) * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [targetValue]);

  return value;
}

export function formatAge(lastUpdated) {
  if (!lastUpdated) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - lastUpdated) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

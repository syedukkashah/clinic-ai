import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { adminApi } from "@/api/adminApi";
import { parsePrometheusText } from "@/api/prometheusParser";

const MetricsContext = createContext(null);

export function MetricsProvider({ children }) {
  const [rawText, setRawText] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [live, setLive] = useState(true);
  const [error, setError] = useState(null);

  const refresh = async () => {
    const result = await adminApi.getMetricsText();
    if (result.ok) {
      setRawText(result.data);
      setLastUpdated(Date.now());
      setError(null);
    } else {
      setError(result);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!live) return undefined;
    const interval = window.setInterval(refresh, 15_000);
    return () => window.clearInterval(interval);
  }, [live]);

  const metrics = useMemo(() => parsePrometheusText(rawText), [rawText]);
  const value = useMemo(
    () => ({ metrics, rawText, lastUpdated, live, setLive, error, refresh }),
    [metrics, rawText, lastUpdated, live, error],
  );

  return <MetricsContext.Provider value={value}>{children}</MetricsContext.Provider>;
}

export function useMetrics() {
  return useContext(MetricsContext);
}

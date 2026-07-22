import { useEffect, useState } from 'react';

const CACHE_KEY = 'freemocap-r2-sizes';
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour — R2 objects are immutable per-version, longer TTL than the releases cache is fine

function readCache(): Record<string, number> {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return {};
    const entry: { timestamp: number; data: Record<string, number> } = JSON.parse(raw);
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
      sessionStorage.removeItem(CACHE_KEY);
      return {};
    }
    return entry.data;
  } catch {
    return {};
  }
}

function writeCache(data: Record<string, number>): void {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ timestamp: Date.now(), data }));
  } catch {
    // sessionStorage may be full or unavailable
  }
}

/**
 * Real byte sizes for R2-hosted files, measured via HEAD request — never estimated.
 * A URL that fails to resolve (network error, CORS not configured, object missing)
 * is simply absent from the returned map; callers render no size badge for it.
 */
export function useR2FileSizes(urls: string[]): Record<string, number> {
  const [sizes, setSizes] = useState<Record<string, number>>(() => readCache());
  const key = urls.slice().sort().join(',');

  useEffect(() => {
    if (urls.length === 0) return;

    const cached = readCache();
    const missing = urls.filter(u => cached[u] == null);
    if (missing.length === 0) {
      setSizes(cached);
      return;
    }

    let cancelled = false;

    Promise.all(
      missing.map(url =>
        fetch(url, { method: 'HEAD' })
          .then(res => {
            const len = res.headers.get('content-length');
            return len ? ([url, Number(len)] as const) : null;
          })
          .catch(() => null),
      ),
    ).then(results => {
      if (cancelled) return;
      const merged = { ...cached };
      for (const r of results) {
        if (r) merged[r[0]] = r[1];
      }
      writeCache(merged);
      setSizes(merged);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return sizes;
}

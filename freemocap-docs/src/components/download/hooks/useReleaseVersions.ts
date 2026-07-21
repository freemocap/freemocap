import { useState, useEffect } from 'react';
import type { GitHubRelease } from '../downloads';
import { REPO } from '../downloads';

const CACHE_KEY = 'freemocap-releases';
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

interface CacheEntry {
  timestamp: number;
  data: GitHubRelease[];
}

interface UseReleaseVersionsResult {
  releases: GitHubRelease[];
  isLoading: boolean;
  error: string | null;
}

function readCache(): GitHubRelease[] | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const entry: CacheEntry = JSON.parse(raw);
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
      sessionStorage.removeItem(CACHE_KEY);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

function writeCache(data: GitHubRelease[]): void {
  try {
    const entry: CacheEntry = { timestamp: Date.now(), data };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(entry));
  } catch {
    // sessionStorage may be full or unavailable
  }
}

export function useReleaseVersions(): UseReleaseVersionsResult {
  const [releases, setReleases] = useState<GitHubRelease[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cached = readCache();
    if (cached) {
      setReleases(cached);
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`, {
      headers: { Accept: 'application/vnd.github.v3+json' },
    })
      .then(res => {
        if (!res.ok) throw new Error(`GitHub API ${res.status}`);
        return res.json();
      })
      .then((data: GitHubRelease[]) => {
        if (cancelled) return;
        writeCache(data);
        setReleases(data);
        setIsLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        setError(err.message);
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { releases, isLoading, error };
}

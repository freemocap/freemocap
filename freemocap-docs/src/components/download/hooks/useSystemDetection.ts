import { useState, useEffect } from 'react';
import type { OsType, ArchType } from '../downloads';

export interface SystemInfo {
  os: OsType | 'unknown';
  arch: ArchType;
}

export function useSystemDetection(): SystemInfo {
  const [system, setSystem] = useState<SystemInfo>({ os: 'unknown', arch: 'x64' });

  useEffect(() => {
    const ua = navigator.userAgent.toLowerCase();
    const platform = (navigator as any).platform?.toLowerCase() ?? '';

    let os: OsType | 'unknown' = 'unknown';
    if (ua.includes('win')) os = 'windows';
    else if (ua.includes('mac')) os = 'macos';
    else if (ua.includes('linux') || ua.includes('x11')) os = 'linux';

    let arch: ArchType = 'x64';
    if (ua.includes('arm64') || ua.includes('aarch64') || platform.includes('arm')) {
      arch = 'arm64';
    }

    // macOS: try WebGL renderer to detect Apple Silicon
    if (os === 'macos') {
      try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
        if (gl && gl instanceof WebGLRenderingContext) {
          const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
          if (debugInfo) {
            const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            if (/Apple\s+(M[1-9]|GPU)/.test(renderer)) {
              arch = 'arm64';
            }
          }
        }
      } catch {
        // ignore
      }
    }

    setSystem({ os, arch });

    // macOS: async High Entropy API for more accurate detection
    if (os === 'macos' && (navigator as any).userAgentData) {
      (navigator as any).userAgentData
        .getHighEntropyValues?.(['architecture'])
        .then((v: { architecture?: string }) => {
          if (v.architecture === 'arm') {
            setSystem({ os, arch: 'arm64' });
          }
        })
        .catch(() => {});
    }
  }, []);

  return system;
}

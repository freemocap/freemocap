import { useState, useEffect } from 'react';
import type { VariantType } from '../downloads';

export interface GpuInfo {
  variant: VariantType;
  /** True only on a positive NVIDIA match — false means "no evidence found", not "confirmed absent". */
  detected: boolean;
}

// Reuses the WebGL renderer-string trick useSystemDetection already uses to spot
// Apple Silicon: some browsers mask/restrict this (Firefox resistFingerprinting,
// Safari), and hybrid-graphics laptops may report the wrong GPU — so this is a
// best-effort hint, not a guarantee. We only ever flip to 'cuda' on a positive
// match; anything inconclusive stays on the universally-compatible CPU default.
export function useGpuDetection(): GpuInfo {
  const [gpu, setGpu] = useState<GpuInfo>({ variant: 'cpu', detected: false });

  useEffect(() => {
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (gl && gl instanceof WebGLRenderingContext) {
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
          const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
          if (typeof renderer === 'string' && /NVIDIA/i.test(renderer)) {
            setGpu({ variant: 'cuda', detected: true });
          }
        }
      }
    } catch {
      // ignore — falls back to the CPU default
    }
  }, []);

  return gpu;
}

import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { DEFAULT_VISIBILITY, ViewportStats, ViewportVisibility } from "../helpers/viewport3d-types";

interface ViewportStateContextValue {
    visibility: ViewportVisibility;
    setVisibility: React.Dispatch<React.SetStateAction<ViewportVisibility>>;
    /** Mutable stats ref — renderers write here each frame, overlay reads on a poll timer. */
    statsRef: React.MutableRefObject<ViewportStats>;
}

const ViewportStateContext = createContext<ViewportStateContextValue | null>(null);

export function ViewportStateProvider({ children }: { children: React.ReactNode }) {
    const [visibility, setVisibility] = useState<ViewportVisibility>(DEFAULT_VISIBILITY);
    const statsRef = useRef<ViewportStats>({
        keypointsRaw: 0,
        keypointsFiltered: 0,
        rigidBodies: 0,
        facePoints: 0,
        connections: 0,
        cameras: 0,
    });

    const value = useMemo(() => ({ visibility, setVisibility, statsRef }), [visibility]);

    return (
        <ViewportStateContext.Provider value={value}>
            {children}
        </ViewportStateContext.Provider>
    );
}

export function useViewportState() {
    const ctx = useContext(ViewportStateContext);
    if (!ctx) throw new Error("useViewportState must be used within ViewportStateProvider");
    return ctx;
}

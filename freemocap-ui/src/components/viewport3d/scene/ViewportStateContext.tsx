import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import {
    DEFAULT_VISIBILITY,
    EMPTY_STATS,
    InspectionTarget,
    ViewportStats,
    ViewportVisibility,
} from "../helpers/viewport3d-types";

interface ViewportStateContextValue {
    visibility: ViewportVisibility;
    setVisibility: React.Dispatch<React.SetStateAction<ViewportVisibility>>;
    /** Mutable stats ref — renderers write here each frame, overlay reads on a poll timer. */
    statsRef: React.MutableRefObject<ViewportStats>;
    /** The entity currently under the pointer (for the hover tooltip). */
    hovered: InspectionTarget | null;
    setHovered: React.Dispatch<React.SetStateAction<InspectionTarget | null>>;
    /** The entity pinned by a click (for the info panel). */
    pinned: InspectionTarget | null;
    setPinned: React.Dispatch<React.SetStateAction<InspectionTarget | null>>;
}

const ViewportStateContext = createContext<ViewportStateContextValue | null>(null);

export function ViewportStateProvider({ children }: { children: React.ReactNode }) {
    const [visibility, setVisibility] = useState<ViewportVisibility>(DEFAULT_VISIBILITY);
    const [hovered, setHovered] = useState<InspectionTarget | null>(null);
    const [pinned, setPinned] = useState<InspectionTarget | null>(null);
    const statsRef = useRef<ViewportStats>({ ...EMPTY_STATS });

    const value = useMemo(
        () => ({ visibility, setVisibility, statsRef, hovered, setHovered, pinned, setPinned }),
        [visibility, hovered, pinned],
    );

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

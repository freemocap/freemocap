import {memo, useEffect, useRef, useState, useSyncExternalStore} from "react";
import {useAppSelector} from "@/store/hooks";
import {selectIsPipelineConnected} from "@/store/slices/realtime";
import {useServerOptional} from "@/services/server/server-context";
import type {SkeletonFitStates} from "@/services/server/server-helpers/skeleton-fit-state-store";
import type {SkeletonFitStateSnapshot} from "@/services/server/server-helpers/websocket-message-types";

const FITTED_TOAST_MS = 5000;
// Display-only heuristic: median |captured - seed| / seed above this reads as a bonked fit.
const PRIOR_DEVIATION_WARN = 0.15;

// Higher-priority state wins when several pipelines report at once.
const STATE_PRIORITY: Record<string, number> = {countdown: 3, capturing: 2, fitted: 1, idle: 0};

const EMPTY_STATES: SkeletonFitStates = {};
const NOOP_SUBSCRIBE = () => () => {};
const getEmptyStates = (): SkeletonFitStates => EMPTY_STATES;

function pickMostActive(states: SkeletonFitStates): SkeletonFitStateSnapshot | null {
    let best: SkeletonFitStateSnapshot | null = null;
    for (const state of Object.values(states)) {
        if (state && (best === null || (STATE_PRIORITY[state.state] ?? 0) > (STATE_PRIORITY[best.state] ?? 0))) {
            best = state;
        }
    }
    return best;
}

/**
 * Renders the segment-fit calibration ritual (armed by the Reset Fitter button)
 * as a top-center viewport overlay: countdown → hold-still capture with quality
 * hints → "locked" confirmation. State arrives pushed over the websocket
 * (server sends only on change); renders nothing while the fitter is idle.
 * All gating rules live server-side — this only visualizes the snapshot.
 */
export const SkeletonFitRitualIndicator = memo(function SkeletonFitRitualIndicator() {
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const server = useServerOptional();
    const store = server?.getSkeletonFitStateStore();
    const states = useSyncExternalStore(
        store?.subscribe ?? NOOP_SUBSCRIBE,
        store?.getSnapshot ?? getEmptyStates,
    );
    const snap = pickMostActive(states);

    const [toastAt, setToastAt] = useState<number | null>(null);
    // null until the first state is observed, so a ritual that finished before
    // this component mounted doesn't replay its "locked" toast.
    const prevStateRef = useRef<string | null>(null);

    useEffect(() => {
        const state = snap?.state ?? "idle";
        const prev = prevStateRef.current;
        prevStateRef.current = state;
        if (prev === null) return; // baseline observation, not a transition
        if (state === "fitted" && prev !== "fitted") {
            setToastAt(Date.now());
        } else if (state === "countdown" || state === "capturing") {
            setToastAt(null); // a (re-)armed ritual clears any stale toast
        }
    }, [snap]);

    // FITTED is quiescent (no further pushes), so the toast needs its own
    // timer to disappear.
    useEffect(() => {
        if (toastAt === null) return;
        const remaining = FITTED_TOAST_MS - (Date.now() - toastAt);
        const timer = window.setTimeout(() => setToastAt(null), Math.max(0, remaining));
        return () => window.clearTimeout(timer);
    }, [toastAt]);

    if (!isConnected || !snap) return null;

    const toastVisible = snap.state === "fitted" && toastAt !== null;
    if (snap.state !== "countdown" && snap.state !== "capturing" && !toastVisible) return null;

    return (
        <div
            className="pos-abs"
            style={{
                top: 12,
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 100,
                pointerEvents: "none",
                minWidth: 260,
                textAlign: "center",
                background: "rgba(20, 20, 20, 0.85)",
                border: "1px solid #444",
                borderRadius: 6,
                padding: "10px 18px",
                color: "#ddd",
                userSelect: "none",
            }}
        >
            {snap.state === "countdown" && <CountdownBody remainingS={snap.countdown_remaining_s} />}
            {snap.state === "capturing" && <CapturingBody snap={snap} />}
            {toastVisible && <FittedBody snap={snap} />}
        </div>
    );
});

function CountdownBody({remainingS}: {remainingS: number}) {
    return (
        <>
            <div style={{fontSize: "0.75rem", letterSpacing: 2, color: "#aaa"}}>
                GET INTO POSITION
            </div>
            <div style={{fontSize: "2rem", fontWeight: "bold", lineHeight: 1.2}}>
                {Math.max(1, Math.ceil(remainingS))}
            </div>
            <div style={{fontSize: "0.7rem", color: "#888"}}>
                skeleton calibration starts at zero — hold still
            </div>
        </>
    );
}

function CapturingBody({snap}: {snap: SkeletonFitStateSnapshot}) {
    const progress = Math.min(1, snap.capture_good_streak / Math.max(1, snap.capture_required_good_frames));

    let hint: string;
    if (snap.visible_fraction < snap.capture_min_visible_fraction) {
        hint = "partial view — fitting what the cameras can see";
    } else if (snap.mean_error_px !== null && snap.mean_error_px > snap.capture_max_mean_error_px) {
        hint = "hold still — tracking is noisy";
    } else {
        hint = "capturing calibration frames…";
    }

    return (
        <>
            <div style={{fontSize: "0.75rem", letterSpacing: 2, color: "#aaa"}}>HOLD STILL</div>
            <div
                style={{
                    width: 220,
                    height: 6,
                    background: "#333",
                    borderRadius: 3,
                    margin: "8px auto",
                    overflow: "hidden",
                }}
            >
                <div
                    style={{
                        width: `${progress * 100}%`,
                        height: "100%",
                        background: "#4da3ff",
                        transition: "width 0.2s linear",
                    }}
                />
            </div>
            <div style={{fontSize: "0.7rem", color: hint.endsWith("…") ? "#888" : "#e0a030"}}>
                {hint}
            </div>
            <div style={{fontSize: "0.65rem", color: "#666", marginTop: 4}}>
                finishes automatically in {Math.max(1, Math.ceil(snap.capture_timeout_remaining_s))}s
            </div>
        </>
    );
}

function FittedBody({snap}: {snap: SkeletonFitStateSnapshot}) {
    const deviation = snap.median_seed_deviation;
    const devPct = deviation !== null ? Math.round(deviation * 100) : null;
    const devHigh = deviation !== null && deviation > PRIOR_DEVIATION_WARN;

    return (
        <>
            <div style={{fontSize: "0.8rem", letterSpacing: 1, color: "#8fd18f"}}>
                SKELETON LOCKED — {snap.n_fitted_body_bones} bones fitted
            </div>
            {devPct !== null && (
                <div style={{fontSize: "0.7rem", color: devHigh ? "#e0a030" : "#888"}}>
                    {devHigh
                        ? `deviates ${devPct}% from priors — check subject height`
                        : `${devPct}% from priors`}
                </div>
            )}
        </>
    );
}

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { ViewportVisibility } from "../helpers/viewport3d-types";
import { useViewportState } from "./ViewportStateContext";

interface ViewportOverlayProps {
    onFitCamera: () => void;
    onResetCamera: () => void;
}

export function ViewportOverlay({ onFitCamera, onResetCamera }: ViewportOverlayProps) {
    const { visibility, setVisibility, statsRef } = useViewportState();
    const [expanded, setExpanded] = useState(false);

    const rawCountRef         = useRef<HTMLSpanElement | null>(null);
    const filteredCountRef    = useRef<HTMLSpanElement | null>(null);
    const rigidBodiesCountRef = useRef<HTMLSpanElement | null>(null);
    const facePointsCountRef  = useRef<HTMLSpanElement | null>(null);
    const connectionsCountRef = useRef<HTMLSpanElement | null>(null);
    const camerasCountRef     = useRef<HTMLSpanElement | null>(null);
    const totalPointsRef      = useRef<HTMLSpanElement | null>(null);
    const totalBodiesRef      = useRef<HTMLSpanElement | null>(null);

    useEffect(() => {
        const id = setInterval(() => {
            const s = statsRef.current;
            if (rawCountRef.current)          rawCountRef.current.textContent         = String(s.keypointsRaw);
            if (filteredCountRef.current)     filteredCountRef.current.textContent    = String(s.keypointsFiltered);
            if (rigidBodiesCountRef.current)  rigidBodiesCountRef.current.textContent = String(s.rigidBodies);
            if (facePointsCountRef.current)   facePointsCountRef.current.textContent  = String(s.facePoints);
            if (connectionsCountRef.current)  connectionsCountRef.current.textContent = String(s.connections);
            if (camerasCountRef.current)      camerasCountRef.current.textContent     = String(s.cameras);
            if (totalPointsRef.current)       totalPointsRef.current.textContent      = String(s.keypointsRaw + s.keypointsFiltered + s.facePoints);
            if (totalBodiesRef.current)       totalBodiesRef.current.textContent      = String(s.rigidBodies);
        }, 500);
        return () => clearInterval(id);
    }, [statsRef]);

    const toggle = useCallback((key: keyof ViewportVisibility) => {
        setVisibility(prev => ({ ...prev, [key]: !prev[key] }));
    }, [setVisibility]);

    const toggleEnvironment  = useCallback(() => toggle("environment"),       [toggle]);
    const toggleKeypointsRaw = useCallback(() => toggle("keypointsRaw"),      [toggle]);
    const toggleFiltered     = useCallback(() => toggle("keypointsFiltered"), [toggle]);
    const toggleRigidBodies  = useCallback(() => toggle("rigidBodies"),       [toggle]);
    const toggleFace         = useCallback(() => toggle("face"),              [toggle]);
    const toggleConnections  = useCallback(() => toggle("connections"),       [toggle]);
    const toggleCameras      = useCallback(() => toggle("cameras"),           [toggle]);

    return (
        <>
            <div style={{
                position: "absolute", top: 8, left: 8,
                padding: 8, backgroundColor: "rgba(0,0,0,0.75)", color: "#ccc",
                minWidth: 180, userSelect: "none", borderRadius: 4,
            }}>
                <div className="flex flex-row items-center justify-content-space-between">
                    <p className="text sm" style={{fontWeight: 'bold', margin: 0}}>Viewport</p>
                    <button
                        className="button icon-button br-1"
                        onClick={() => setExpanded(e => !e)}
                        style={{color: "#ccc", padding: 2}}
                    >
                        <span className={`icon icon-size-20 ${expanded ? 'collapse-icon' : 'expand-icon'}`}/>
                    </button>
                </div>

                <VisToggle label="Environment"  checked={visibility.environment}      onChange={toggleEnvironment} />
                <VisToggle label="Raw"          countRef={rawCountRef}                checked={visibility.keypointsRaw}      onChange={toggleKeypointsRaw} />
                <VisToggle label="Filtered"     countRef={filteredCountRef}           checked={visibility.keypointsFiltered} onChange={toggleFiltered} />
                <VisToggle label="Rigid bodies" countRef={rigidBodiesCountRef}        checked={visibility.rigidBodies}       onChange={toggleRigidBodies} />
                <VisToggle label="Face"         countRef={facePointsCountRef}         checked={visibility.face}              onChange={toggleFace} />
                <VisToggle label="Connections"  countRef={connectionsCountRef}        checked={visibility.connections}       onChange={toggleConnections} />
                <VisToggle label="Cameras"      countRef={camerasCountRef}            checked={visibility.cameras}           onChange={toggleCameras} />

                {expanded && (
                    <p className="text sm" style={{marginTop: 4, color: "#888", display: "block"}}>
                        Total points: <span ref={totalPointsRef}>0</span>
                        <br />
                        Total bodies: <span ref={totalBodiesRef}>0</span>
                    </p>
                )}
            </div>

            <div className="flex flex-row gap-1" style={{position: "absolute", bottom: 8, right: 8}}>
                <button
                    title="Fit to skeleton (F)"
                    className="button icon-button br-1"
                    onClick={onFitCamera}
                    style={{backgroundColor: "rgba(0,0,0,0.6)", color: "#ccc"}}
                >
                    <span className="icon search-icon icon-size-20"/>
                </button>
                <button
                    title="Reset view"
                    className="button icon-button br-1"
                    onClick={onResetCamera}
                    style={{backgroundColor: "rgba(0,0,0,0.6)", color: "#ccc"}}
                >
                    <span className="icon back-icon icon-size-20"/>
                </button>
            </div>

            <p className="text sm" style={{position: "absolute", bottom: 8, left: 8, color: "#666", pointerEvents: "none", margin: 0}}>
                Rotate: drag · Zoom: scroll · Pan: right-drag
            </p>
        </>
    );
}

const VisToggle = memo(function VisToggle({
    label,
    countRef,
    checked,
    onChange,
}: {
    label: string;
    countRef?: React.RefObject<HTMLSpanElement | null>;
    checked: boolean;
    onChange: () => void;
}) {
    const labelNode = countRef
        ? <span>{ label } (<span ref={countRef}>0</span>)</span>
        : label;
    return (
        <div
            className="flex flex-row items-center justify-content-space-between gap-1"
            style={{margin: '2px 0', cursor: 'pointer'}}
            onClick={onChange}
        >
            <span style={{fontSize: '0.7rem', color: '#ccc'}}>{labelNode}</span>
            <div className={`icon toggle-container sm ${checked ? "on" : "off"}`}>
                <div className="icon toggle-circle" />
            </div>
        </div>
    );
});

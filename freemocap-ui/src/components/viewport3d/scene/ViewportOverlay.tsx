import { memo, useCallback, useEffect, useRef, useState } from "react";
import { ViewportVisibility } from "../helpers/viewport3d-types";
import { useViewportState } from "./ViewportStateContext";
import IconButton from "@/components/ui-components/IconButton";

interface ViewportOverlayProps {
  onFitCamera: () => void;
  onResetCamera: () => void;
}

export function ViewportOverlay({
  onFitCamera,
  onResetCamera,
}: ViewportOverlayProps) {
  const { visibility, setVisibility, statsRef } = useViewportState();
  const [expanded, setExpanded] = useState(false);

  const rawCountRef = useRef<HTMLSpanElement | null>(null);
  const filteredCountRef = useRef<HTMLSpanElement | null>(null);
  const rigidBodiesCountRef = useRef<HTMLSpanElement | null>(null);
  const facePointsCountRef = useRef<HTMLSpanElement | null>(null);
  const connectionsCountRef = useRef<HTMLSpanElement | null>(null);
  const camerasCountRef = useRef<HTMLSpanElement | null>(null);
  const comCountRef = useRef<HTMLSpanElement | null>(null);
  const totalPointsRef = useRef<HTMLSpanElement | null>(null);
  const totalBodiesRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      const s = statsRef.current;
      if (rawCountRef.current)
        rawCountRef.current.textContent = String(s.keypointsRaw);
      if (filteredCountRef.current)
        filteredCountRef.current.textContent = String(s.keypointsFiltered);
      if (rigidBodiesCountRef.current)
        rigidBodiesCountRef.current.textContent = String(s.rigidBodies);
      if (facePointsCountRef.current)
        facePointsCountRef.current.textContent = String(s.facePoints);
      if (connectionsCountRef.current)
        connectionsCountRef.current.textContent = String(s.connections);
      if (camerasCountRef.current)
        camerasCountRef.current.textContent = String(s.cameras);
      if (comCountRef.current)
        comCountRef.current.textContent = String(s.centerOfMass);
      if (totalPointsRef.current)
        totalPointsRef.current.textContent = String(
          s.keypointsRaw + s.keypointsFiltered + s.facePoints,
        );
      if (totalBodiesRef.current)
        totalBodiesRef.current.textContent = String(s.rigidBodies);
    }, 500);
    return () => clearInterval(id);
  }, [statsRef]);

  const toggle = useCallback(
    (key: keyof ViewportVisibility) => {
      setVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
    },
    [setVisibility],
  );

  const toggleEnvironment = useCallback(() => toggle("environment"), [toggle]);
  const toggleKeypointsRaw = useCallback(
    () => toggle("keypointsRaw"),
    [toggle],
  );
  const toggleFiltered = useCallback(
    () => toggle("keypointsFiltered"),
    [toggle],
  );
  const toggleRigidBodies = useCallback(() => toggle("rigidBodies"), [toggle]);
  const toggleFace = useCallback(() => toggle("face"), [toggle]);
  const toggleConnections = useCallback(() => toggle("connections"), [toggle]);
  const toggleCameras = useCallback(() => toggle("cameras"), [toggle]);
  const toggleCenterOfMass = useCallback(() => toggle("centerOfMass"), [toggle]);
  const toggleComSphere = useCallback(() => toggle("centerOfMassSphere"), [toggle]);
  const toggleComProjection = useCallback(() => toggle("centerOfMassProjection"), [toggle]);
  const toggleComConnection = useCallback(() => toggle("centerOfMassConnection"), [toggle]);

  return (
    <>
      <div
        className="viewport-options pos-abs top-8 left-8 p-2 br-1"
        style={{
          minWidth: 180,
          userSelect: "none",
        }}
      >
        <div className="flex flex-row items-center justify-content-space-between">
          <p className="text sm m-0" style={{ fontWeight: "bold" }}>
            Viewport
          </p>
          <IconButton
            icon={expanded ? "arrowup-icon" : "arrowdown-icon"}
            className="icon-size-25 p-1"
            onClick={() => setExpanded((e) => !e)}
            style={{ color: "#ccc" }}
            tooltip={true}
            tooltipText="bodies & points"
            tooltipPosition="pos-left"
          />
        </div>

        {expanded && (
          <>
            <VisToggle
              label="Environment"
              checked={visibility.environment}
              onChange={toggleEnvironment}
            />
            <VisToggle
              label="Raw"
              countRef={rawCountRef}
              checked={visibility.keypointsRaw}
              onChange={toggleKeypointsRaw}
            />
            <VisToggle
              label="Filtered"
              countRef={filteredCountRef}
              checked={visibility.keypointsFiltered}
              onChange={toggleFiltered}
            />
            <VisToggle
              label="Rigid bodies"
              countRef={rigidBodiesCountRef}
              checked={visibility.rigidBodies}
              onChange={toggleRigidBodies}
            />
            <VisToggle
              label="Face"
              countRef={facePointsCountRef}
              checked={visibility.face}
              onChange={toggleFace}
            />
            <VisToggle
              label="Connections"
              countRef={connectionsCountRef}
              checked={visibility.connections}
              onChange={toggleConnections}
            />
            <VisToggle
              label="Cameras"
              countRef={camerasCountRef}
              checked={visibility.cameras}
              onChange={toggleCameras}
            />
            <CollapsibleVisibilityGroup
              label="Center of Mass"
              checked={visibility.centerOfMass}
              onToggle={toggleCenterOfMass}
              countRef={comCountRef}
            >
              <VisToggle
                label="COM Sphere"
                checked={visibility.centerOfMassSphere}
                onChange={toggleComSphere}
              />
              <VisToggle
                label="Vertical Projection"
                checked={visibility.centerOfMassProjection}
                onChange={toggleComProjection}
              />
              <VisToggle
                label="COM-VP Connection"
                checked={visibility.centerOfMassConnection}
                onChange={toggleComConnection}
              />
            </CollapsibleVisibilityGroup>
            <p className="text sm mt-1 block" style={{ color: "#888" }}>
              Total points: <span ref={totalPointsRef}>0</span>
              <br />
              Total bodies: <span ref={totalBodiesRef}>0</span>
            </p>
          </>
        )}
      </div>

      <div className="flex flex-row gap-1 pos-abs bottom-8 right-8">
        <IconButton
          icon="frame-icon"
          onClick={onFitCamera}
          tooltip={true}
          tooltipText="Fit to skeleton F"
          tooltipPosition="pos-top"
        />
        <IconButton
          icon="rotate-icon"
          onClick={onResetCamera}
          tooltip={true}
          tooltipText="Reset view"
          tooltipPosition="pos-top-right"
        />
      </div>

      <p
        className="text sm pos-abs bottom-8 left-8 m-0"
        style={{ color: "#666", pointerEvents: "none" }}
      >
        Rotate: drag · Zoom: scroll · Pan: right-drag
      </p>
    </>
  );
}

/**
 * Reusable collapsible visibility group with a master toggle and
 * expandable sub-item toggles. Toggle switches align vertically
 * across nesting levels via a fixed-width toggle column.
 */
const COLLAPSE_ICON_STYLE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 18,
  height: 18,
  fontSize: 10,
  color: "#888",
  transition: "transform 0.15s",
  flexShrink: 0,
};

const CollapsibleVisibilityGroup = memo(function CollapsibleVisibilityGroup({
  label,
  checked,
  onToggle,
  countRef,
  children,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
  countRef?: React.RefObject<HTMLSpanElement | null>;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);

  const labelNode = countRef ? (
    <span>
      {label} (<span ref={countRef}>0</span>)
    </span>
  ) : (
    label
  );

  return (
    <div className="flex flex-col">
      <div
        className="flex flex-row items-center justify-content-space-between gap-1"
        style={{ margin: "2px 0", cursor: "pointer" }}
      >
        <span
          className="flex flex-row items-center gap-1"
          style={{ fontSize: "0.7rem", color: "#ccc", flex: 1 }}
          onClick={() => setExpanded((e) => !e)}
        >
          <span
            style={{
              ...COLLAPSE_ICON_STYLE,
              transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
            }}
          >
            ▾
          </span>
          {labelNode}
        </span>
        <div
          className={`icon toggle-container sm ${checked ? "on" : "off"}`}
          onClick={onToggle}
        >
          <div className="icon toggle-circle" />
        </div>
      </div>
      {expanded && (
        <div style={{ paddingLeft: 26, opacity: 0.85 }}>{children}</div>
      )}
    </div>
  );
});

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
  const labelNode = countRef ? (
    <span>
      {label} (<span ref={countRef}>0</span>)
    </span>
  ) : (
    label
  );
  return (
    <div
      className="flex flex-row items-center justify-content-space-between gap-1"
      style={{ margin: "2px 0", cursor: "pointer" }}
      onClick={onChange}
    >
      <span style={{ fontSize: "0.7rem", color: "#ccc" }}>{labelNode}</span>
      <div className={`icon toggle-container sm ${checked ? "on" : "off"}`}>
        <div className="icon toggle-circle" />
      </div>
    </div>
  );
});

import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
    Box,
    Checkbox,
    Collapse,
    FormControlLabel,
    IconButton,
    Paper,
    Tooltip,
    Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import HomeIcon from "@mui/icons-material/Home";
import { ViewportVisibility } from "../helpers/viewport3d-types";
import { useViewportState } from "./ViewportStateContext";

interface ViewportOverlayProps {
    onFitCamera: () => void;
    onResetCamera: () => void;
}

export function ViewportOverlay({ onFitCamera, onResetCamera }: ViewportOverlayProps) {
    const { visibility, setVisibility, statsRef } = useViewportState();
    const [expanded, setExpanded] = useState(false);

    // DOM refs for count spans — mutated directly so stats never trigger React re-renders.
    const rawCountRef         = useRef<HTMLSpanElement | null>(null);
    const filteredCountRef    = useRef<HTMLSpanElement | null>(null);
    const rigidBodiesCountRef = useRef<HTMLSpanElement | null>(null);
    const facePointsCountRef  = useRef<HTMLSpanElement | null>(null);
    const connectionsCountRef = useRef<HTMLSpanElement | null>(null);
    const camerasCountRef     = useRef<HTMLSpanElement | null>(null);
    const eyeGazeCountRef     = useRef<HTMLSpanElement | null>(null);
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
            if (eyeGazeCountRef.current)      eyeGazeCountRef.current.textContent     = String(s.eyeGaze);
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
    const toggleEyeGaze      = useCallback(() => toggle("eyeGaze"),           [toggle]);

    return (
        <>
            {/* Top-left: visibility + stats */}
            <Paper
                sx={{
                    position: "absolute", top: 8, left: 8,
                    p: 1, bgcolor: "rgba(0,0,0,0.75)", color: "#ccc",
                    minWidth: 180, userSelect: "none",
                }}
                elevation={3}
            >
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Typography variant="caption" fontWeight="bold">Viewport</Typography>
                    <IconButton size="small" onClick={() => setExpanded(e => !e)} sx={{ color: "#ccc" }}>
                        {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                    </IconButton>
                </Box>

                <VisToggle label="Environment"  checked={visibility.environment}      onChange={toggleEnvironment} />
                <VisToggle label="Raw"          countRef={rawCountRef}                checked={visibility.keypointsRaw}      onChange={toggleKeypointsRaw} />
                <VisToggle label="Filtered"     countRef={filteredCountRef}           checked={visibility.keypointsFiltered} onChange={toggleFiltered} />
                <VisToggle label="Rigid bodies" countRef={rigidBodiesCountRef}        checked={visibility.rigidBodies}       onChange={toggleRigidBodies} />
                <VisToggle label="Face"         countRef={facePointsCountRef}         checked={visibility.face}              onChange={toggleFace} />
                <VisToggle label="Connections"  countRef={connectionsCountRef}        checked={visibility.connections}       onChange={toggleConnections} />
                <VisToggle label="Cameras"      countRef={camerasCountRef}            checked={visibility.cameras}           onChange={toggleCameras} />
                <VisToggle label="Eye gaze"     countRef={eyeGazeCountRef}           checked={visibility.eyeGaze}           onChange={toggleEyeGaze} />

                <Collapse in={expanded}>
                    <Typography variant="caption" sx={{ mt: 1, display: "block", color: "#888" }}>
                        Total points: <span ref={totalPointsRef}>0</span>
                        <br />
                        Total bodies: <span ref={totalBodiesRef}>0</span>
                    </Typography>
                </Collapse>
            </Paper>

            {/* Bottom-right: camera buttons */}
            <Box sx={{ position: "absolute", bottom: 8, right: 8, display: "flex", gap: 0.5 }}>
                <Tooltip title="Fit to skeleton (F)">
                    <IconButton onClick={onFitCamera} size="small" sx={btnSx}>
                        <CenterFocusStrongIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <Tooltip title="Reset view">
                    <IconButton onClick={onResetCamera} size="small" sx={btnSx}>
                        <HomeIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Bottom-left: hint */}
            <Typography
                variant="caption"
                sx={{ position: "absolute", bottom: 8, left: 8, color: "#666", pointerEvents: "none" }}
            >
                Rotate: drag · Zoom: scroll · Pan: right-drag
            </Typography>
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
        <FormControlLabel
            sx={{ m: 0, ml: -0.5, "& .MuiTypography-root": { fontSize: "0.7rem" } }}
            control={<Checkbox size="small" checked={checked} onChange={onChange} sx={{ p: 0.3, color: "#888", "&.Mui-checked": { color: "#aaa" } }} />}
            label={labelNode}
        />
    );
});

const btnSx = {
    bgcolor: "rgba(0,0,0,0.6)",
    color: "#ccc",
    boxShadow: 2,
    "&:hover": { bgcolor: "rgba(60,60,60,0.8)" },
};

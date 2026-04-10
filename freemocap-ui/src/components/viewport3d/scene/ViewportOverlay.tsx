import { useCallback, useEffect, useState } from "react";
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
import { ViewportStats, ViewportVisibility } from "../helpers/viewport3d-types";
import { useViewportState } from "./ViewportStateContext";

interface ViewportOverlayProps {
    onFitCamera: () => void;
    onResetCamera: () => void;
}

export function ViewportOverlay({ onFitCamera, onResetCamera }: ViewportOverlayProps) {
    const { visibility, setVisibility, statsRef } = useViewportState();
    const [stats, setStats] = useState<ViewportStats>({ keypointsRaw: 0, keypointsFiltered: 0, rigidBodies: 0, facePoints: 0 });
    const [expanded, setExpanded] = useState(false);

    // Poll stats from the mutable ref at ~4 Hz (no re-render coupling to the frame loop)
    useEffect(() => {
        const id = setInterval(() => setStats({ ...statsRef.current }), 250);
        return () => clearInterval(id);
    }, [statsRef]);

    const toggle = useCallback((key: keyof ViewportVisibility) => {
        setVisibility(prev => ({ ...prev, [key]: !prev[key] }));
    }, [setVisibility]);

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

                <VisToggle label="Environment" checked={visibility.environment} onChange={() => toggle("environment")} />
                <VisToggle label={`Raw (${stats.keypointsRaw})`} checked={visibility.keypointsRaw} onChange={() => toggle("keypointsRaw")} />
                <VisToggle label={`Filtered (${stats.keypointsFiltered})`} checked={visibility.keypointsFiltered} onChange={() => toggle("keypointsFiltered")} />
                <VisToggle label={`Rigid bodies (${stats.rigidBodies})`} checked={visibility.rigidBodies} onChange={() => toggle("rigidBodies")} />
                <VisToggle label={`Face (${stats.facePoints})`} checked={visibility.face} onChange={() => toggle("face")} />

                <Collapse in={expanded}>
                    <Typography variant="caption" sx={{ mt: 1, display: "block", color: "#888" }}>
                        Total points: {stats.keypointsRaw + stats.keypointsFiltered + stats.facePoints}
                        <br />
                        Total bodies: {stats.rigidBodies}
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

function VisToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
    return (
        <FormControlLabel
            sx={{ m: 0, ml: -0.5, "& .MuiTypography-root": { fontSize: "0.7rem" } }}
            control={<Checkbox size="small" checked={checked} onChange={onChange} sx={{ p: 0.3, color: "#888", "&.Mui-checked": { color: "#aaa" } }} />}
            label={label}
        />
    );
}

const btnSx = {
    bgcolor: "rgba(0,0,0,0.6)",
    color: "#ccc",
    boxShadow: 2,
    "&:hover": { bgcolor: "rgba(60,60,60,0.8)" },
};

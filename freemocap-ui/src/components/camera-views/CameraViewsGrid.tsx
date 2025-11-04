import React from "react";
import { Box } from "@mui/material";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useTheme } from "@mui/material/styles";
import { CameraView } from "./CameraView";

import {useServer} from "@/hooks/useServer";

interface CameraSettings {
    columns: number | null;
}

interface CameraViewsGridProps {
    settings?: CameraSettings;
}

interface CameraViewsGridProps {
    settings?: CameraSettings;
    resetKey?: number;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ settings, resetKey }) => {
    const theme = useTheme();
    const { connectedCameraIds } = useServer();

    const getColumns = (total: number): number => {
        if (settings?.columns !== null && settings?.columns !== undefined) {
            return settings.columns;
        }

        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };

    if (connectedCameraIds.length === 0) {
        return (
            <Box sx={{
                height: '100%',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'text.secondary',
                fontSize: '1.2rem',
                padding: 4,
                textAlign: 'center',
            }}>
                <div>
                    <div>No cameras connected</div>
                    <div style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
                        Waiting for camera streams...
                    </div>
                </div>
            </Box>
        );
    }

    const columns = getColumns(connectedCameraIds.length);

    // Organize cameras into rows
    const rows: string[][] = [];
    for (let i = 0; i < connectedCameraIds.length; i += columns) {
        rows.push(connectedCameraIds.slice(i, i + columns));
    }

    // Calculate default size for each panel
    const defaultRowSize = 100 / rows.length;
    const minRowSize = Math.max(10, 100 / (rows.length * 2));

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            overflow: 'hidden',
            padding: 1,
        }}>
            <PanelGroup key={`camera-grid-${resetKey ?? 0}`} direction="vertical">
                {rows.map((row, rowIndex) => {
                    const defaultCameraSize = 100 / row.length;
                    const minCameraSize = Math.max(10, 100 / (row.length * 2));

                    return (
                        <React.Fragment key={`row-${rowIndex}`}>
                            <Panel
                                defaultSize={defaultRowSize}
                                minSize={minRowSize}
                            >
                                <PanelGroup direction="horizontal">
                                    {row.map((cameraId, cameraIndex) => (
                                        <React.Fragment key={cameraId}>
                                            <Panel
                                                defaultSize={defaultCameraSize}
                                                minSize={minCameraSize}
                                            >
                                                <Box sx={{
                                                    height: '100%',
                                                    width: '100%',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    overflow: 'hidden',
                                                }}>
                                                    <CameraView cameraId={cameraId} />
                                                </Box>
                                            </Panel>

                                            {/* Horizontal resize handle between cameras in same row */}
                                            {cameraIndex < row.length - 1 && (
                                                <PanelResizeHandle
                                                    style={{
                                                        width: "2px",
                                                        cursor: "col-resize",
                                                        backgroundColor: theme.palette.primary.dark,
                                                    }}
                                                />
                                            )}
                                        </React.Fragment>
                                    ))}
                                </PanelGroup>
                            </Panel>

                            {/* Vertical resize handle between rows */}
                            {rowIndex < rows.length - 1 && (
                                <PanelResizeHandle
                                    style={{
                                        height: "2px",
                                        cursor: "row-resize",
                                        backgroundColor: theme.palette.primary.dark,
                                    }}
                                />
                            )}
                        </React.Fragment>
                    );
                })}
            </PanelGroup>
        </Box>
    );
};

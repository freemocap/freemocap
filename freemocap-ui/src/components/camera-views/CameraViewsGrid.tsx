import React from "react";
import { Box } from "@mui/material";
import { CameraView } from "./CameraView";
import { useServer } from "@/services/server/ServerContextProvider";

interface CameraSettings {
    columns: number | null;
}

interface CameraViewsGridProps {
    settings?: CameraSettings;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({
                                                                    settings
                                                                }) => {
    const { connectedCameraIds } = useServer();

    const getColumns = (total: number): number => {
        // If manual columns setting is provided, use it
        if (settings?.columns !== null && settings?.columns !== undefined) {
            return settings.columns;
        }

        // Otherwise, auto-calculate
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };

    const columns = getColumns(connectedCameraIds.length);

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

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            display: 'grid',
            gridTemplateColumns: `repeat(${columns}, 1fr)`,
            gridAutoRows: 'minmax(200px, 420px)',
            gap: 1,
            padding: 1,
            overflow: 'auto',
        }}>
            {connectedCameraIds.map(cameraId => (
                <Box key={cameraId} sx={{
                    maxHeight: '420px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden'
                }}>
                    <CameraView cameraId={cameraId} />
                </Box>
            ))}
        </Box>
    );
};

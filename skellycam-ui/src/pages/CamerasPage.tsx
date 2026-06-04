import React, { useState, useCallback } from 'react';
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { Footer } from "@/components/ui-components/Footer";
import { CameraViewsGrid } from "@/components/camera-views/CameraViewsGrid";
import { CamerasViewSettingsOverlay } from "@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay";

export const CamerasPage = () => {
    const [manualColumns, setManualColumns] = useState<number | null>(null);
    const [resetKey, setResetKey] = useState<number>(0);

    const handleSettingsChange = useCallback((settings: { columns: number | null }) => {
        setManualColumns(settings.columns);
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    return (
        <div className="cameras-page p-0">
            <CamerasViewSettingsOverlay
                onSettingsChange={handleSettingsChange}
                onResetLayout={handleResetLayout}
            />
            <div className="cameras-page-content">
                <ErrorBoundary>
                    <CameraViewsGrid
                        manualColumns={manualColumns}
                        resetKey={resetKey}
                    />
                </ErrorBoundary>
            </div>
            <footer className="cameras-page-footer">
                <Footer />
            </footer>
        </div>
    );
};

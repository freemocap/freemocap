import { useCallback } from "react";
import IconButton from "@/components/ui-components/IconButton";
import { useAppDispatch } from "@/store/hooks";
import { resetSkeletonFitter } from "@/store/slices/realtime";
import { ViewportPanel } from "./ViewportPanel";
import "./viewport-overlay.css";

interface ViewportOverlayProps {
    onFitCamera: () => void;
    onResetCamera: () => void;
}

/** DOM chrome drawn over the 3D canvas: the viewport panel (top-left), camera actions
 *  (bottom-right) and the mouse-controls hint (bottom-left). */
export function ViewportOverlay({ onFitCamera, onResetCamera }: ViewportOverlayProps) {
    const dispatch = useAppDispatch();
    const handleResetSkeleton = useCallback(() => {
        dispatch(resetSkeletonFitter());
    }, [dispatch]);

    return (
        <>
            <ViewportPanel />

            <div className="vp-actions">
                <IconButton
                    icon="fit-icon"
                    onClick={handleResetSkeleton}
                    ariaLabel="Re-fit skeleton"
                    tooltip={true}
                    tooltipText="Re-fit skeleton from scratch"
                    tooltipPosition="pos-top-right"
                />
                <IconButton
                    icon="frame-icon"
                    onClick={onFitCamera}
                    ariaLabel="Frame the subject"
                    tooltip={true}
                    tooltipText="Frame the subject (F)"
                    tooltipPosition="pos-top"
                />
                <IconButton
                    icon="rotate-icon"
                    onClick={onResetCamera}
                    ariaLabel="Reset camera"
                    tooltip={true}
                    tooltipText="Reset camera"
                    tooltipPosition="pos-top-right"
                />
            </div>

            <p className="vp-controls-hint">
                Drag to orbit · Right-drag to pan · Scroll to zoom · Click a point or bone to inspect it
            </p>
        </>
    );
}

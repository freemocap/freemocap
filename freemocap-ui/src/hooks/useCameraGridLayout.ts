import { useMemo } from 'react';
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

interface GridLayout {
    rows: number;
    columns: number;
}

/**
 * Hook to calculate optimal grid layout for camera views
 * @param imageData The camera image data
 * @param containerWidth The container width
 * @param containerHeight The container height
 * @param manualRows Optional manual row setting
 * @param manualColumns Optional manual column setting
 */
export function useCameraGridLayout(
    imageData: Record<string, CameraImageData>,
    containerWidth?: number,
    containerHeight?: number,
    manualRows?: number,
    manualColumns?: number
): GridLayout {
    return useMemo(() => {
        // If manual values are provided, use them
        if (manualRows !== undefined && manualColumns !== undefined) {
            return { rows: manualRows, columns: manualColumns };
        }

        const imageDataArray:CameraImageData[] = Object.values(imageData);
        if (!imageDataArray || imageDataArray.length === 0) return { rows: 1, columns: 1 };

        // For static grid without container dimensions, use simple layout
        if (!containerWidth || !containerHeight) {
            // Simple layout calculation based on number of cameras
            if (imageDataArray.length <= 1) return { rows: 1, columns: 1 };
            if (imageDataArray.length <= 2) return { rows: 1, columns: 2 };
            if (imageDataArray.length <= 4) return { rows: 2, columns: 2 };
            if (imageDataArray.length <= 6) return { rows: 2, columns: 3 };
            if (imageDataArray.length <= 9) return { rows: 3, columns: 3 };
            return {
                rows: Math.ceil(Math.sqrt(imageDataArray.length)),
                columns: Math.ceil(Math.sqrt(imageDataArray.length))
            };
        }

        // Advanced layout calculation for dynamic grid with container dimensions
        // Find the grid configuration that maximizes image size while handling both portrait and landscape orientations
        let bestLayout = { columns: 1, rows: 1, area: 0 };

        // Calculate average aspect ratio to inform grid layout
        const avgAspectRatio = imageDataArray.reduce((sum, img) =>
            sum + (img.imageWidth / img.imageHeight), 0) / imageDataArray.length;

        // Container aspect ratio
        const containerAspect = containerWidth / containerHeight;

        // Try different grid configurations
        for (let columns = 1; columns <= imageDataArray.length; columns++) {
            const rows = Math.ceil(imageDataArray.length / columns);

            // Calculate the area each image would get
            const cellWidth = containerWidth / columns;
            const cellHeight = containerHeight / rows;
            const cellAspect = cellWidth / cellHeight;

            // Calculate how well images would fit in this grid
            let totalFitScore = 0;
            imageDataArray.forEach(image => {
                const imgAspect = image.imageWidth / image.imageHeight;

                // Calculate how well the image fits the cell (1.0 = perfect fit)
                // This handles both portrait and landscape orientations equally well
                const fitScore = Math.min(
                    imgAspect / cellAspect,
                    cellAspect / imgAspect
                );
                totalFitScore += fitScore;
            });

            // Average fit score for this configuration
            const avgFitScore = totalFitScore / imageDataArray.length;

            // Calculate effective area with fit score as a factor
            // Add a slight bias toward more balanced layouts (closer to square)
            const balanceFactor = 1 - 0.2 * Math.abs(columns/rows - containerAspect/avgAspectRatio);
            const effectiveArea = avgFitScore * balanceFactor * (cellWidth * cellHeight);

            if (effectiveArea > bestLayout.area) {
                bestLayout = { columns, rows, area: effectiveArea };
            }
        }

        return { columns: bestLayout.columns, rows: bestLayout.rows };
    }, [imageData, containerWidth, containerHeight, manualRows, manualColumns]);
}

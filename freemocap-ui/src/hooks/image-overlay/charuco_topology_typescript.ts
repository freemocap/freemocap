import { OverlayTopology } from './overlay-topology';
import { PointElement, LineElement, TextElement } from './overlay-elements';
import { PointsDict } from './overlay-types';

// ============================================================================
// CHARUCO OVERLAY TOPOLOGY
// ============================================================================

interface CharucoTopologyOptions {
  width: number;
  height: number;
  showCharucoCorners?: boolean;
  showCharucoIds?: boolean;
  showArucoMarkers?: boolean;
  showArucoIds?: boolean;
  showBoardOutline?: boolean;
  maxCharucoCorners?: number;
  maxArucoMarkers?: number;
}

export function createCharucoTopology(options: CharucoTopologyOptions): OverlayTopology {
  const {
    width,
    height,
    showCharucoCorners = true,
    showCharucoIds = true,
    showArucoMarkers = true,
    showArucoIds = true,
    showBoardOutline = true,
    maxCharucoCorners = 100,
    maxArucoMarkers = 30
  } = options;

  const topology = new OverlayTopology('charuco_board_tracking', width, height);

  // === CHARUCO CORNERS ===

  if (showCharucoCorners) {
    const charucoStyle = {
      radius: 5,
      fill: 'rgb(0, 255, 0)',
      stroke: 'rgb(0, 150, 0)',
      strokeWidth: 2,
      opacity: 1.0
    };

    const charucoLabelStyle = {
      fontSize: 10,
      fontFamily: 'Arial, sans-serif',
      fill: 'rgb(0, 255, 0)',
      stroke: 'black',
      strokeWidth: 2,
      fontWeight: 'normal' as const,
      textAlign: 'start' as const
    };

    for (let cornerId = 0; cornerId < maxCharucoCorners; cornerId++) {
      topology.add(
        new PointElement(
          `charuco_corner_${cornerId}`,
          ['charuco', `charuco_${cornerId}`],
          charucoStyle,
          showCharucoIds ? String(cornerId) : undefined,
          [8, -8],
          charucoLabelStyle
        )
      );
    }
  }

  // === ARUCO MARKERS ===

  if (showArucoMarkers) {
    const arucoLineStyle = {
      stroke: 'rgb(255, 100, 0)',
      strokeWidth: 3,
      opacity: 0.9
    };

    const arucoCornerStyle = {
      radius: 4,
      fill: 'rgb(255, 150, 0)',
      stroke: 'rgb(200, 80, 0)',
      strokeWidth: 1,
      opacity: 1.0
    };

    for (let markerId = 0; markerId < maxArucoMarkers; markerId++) {
      // Draw 4 corners
      for (let cornerIdx = 0; cornerIdx < 4; cornerIdx++) {
        topology.add(
          new PointElement(
            `aruco_${markerId}_corner_${cornerIdx}`,
            ['aruco', `aruco_${markerId}_corner_${cornerIdx}`],
            arucoCornerStyle
          )
        );
      }

      // Draw lines connecting corners (forming square)
      const connections: [number, number][] = [
        [0, 1], [1, 2], [2, 3], [3, 0]
      ];

      for (let idx = 0; idx < connections.length; idx++) {
        const [cornerA, cornerB] = connections[idx];
        topology.add(
          new LineElement(
            `aruco_${markerId}_line_${idx}`,
            ['aruco', `aruco_${markerId}_corner_${cornerA}`],
            ['aruco', `aruco_${markerId}_corner_${cornerB}`],
            arucoLineStyle
          )
        );
      }

      // Add marker ID label at center
      if (showArucoIds) {
        topology.addComputedPoint({
          dataType: 'computed',
          name: `aruco_${markerId}_center`,
          computation: (points: PointsDict) => {
            if (!points.aruco) return [NaN, NaN];

            const corners: [number, number][] = [];
            for (let cornerIdx = 0; cornerIdx < 4; cornerIdx++) {
              const cornerName = `aruco_${markerId}_corner_${cornerIdx}`;
              const corner = points.aruco[cornerName];
              if (corner) corners.push(corner);
            }

            if (corners.length === 0) return [NaN, NaN];

            const sumX = corners.reduce((s, c) => s + c[0], 0);
            const sumY = corners.reduce((s, c) => s + c[1], 0);
            return [sumX / corners.length, sumY / corners.length];
          },
          description: `Center of ArUco marker ${markerId}`
        });

        topology.add(
          new TextElement(
            `aruco_${markerId}_label`,
            ['computed', `aruco_${markerId}_center`],
            String(markerId),
            [0, 0],
            {
              fontSize: 14,
              fontFamily: 'Arial, sans-serif',
              fill: 'rgb(255, 255, 255)',
              stroke: 'rgb(255, 100, 0)',
              strokeWidth: 3,
              fontWeight: 'bold',
              textAlign: 'start'
            }
          )
        );
      }
    }
  }

  // === FRAME INFO ===

  topology.addComputedPoint({
    dataType: 'computed',
    name: 'info_corner',
    computation: () => [10, 25],
    description: 'Top-left corner for info text'
  });

  topology.add(
    new TextElement(
      'frame_info',
      ['computed', 'info_corner'],
      (metadata) => {
        const frameIdx = metadata.frameIdx ?? 0;
        const totalFrames = metadata.totalFrames ?? 0;
        const nCharuco = metadata.nCharucoDetected ?? 0;
        const nCharucoTotal = metadata.nCharucoTotal ?? 0;
        const nAruco = metadata.nArucoDetected ?? 0;
        const nArucoTotal = metadata.nArucoTotal ?? 0;
        const hasPose = metadata.hasPose ?? false;
        const poseStr = hasPose ? ' | POSE ✓' : '';

        return `Frame: ${frameIdx}/${totalFrames} | ` +
               `Charuco: ${nCharuco}/${nCharucoTotal} | ` +
               `ArUco: ${nAruco}/${nArucoTotal}${poseStr}`;
      },
      [0, 0],
      {
        fontSize: 16,
        fontFamily: 'Consolas, monospace',
        fill: 'white',
        stroke: 'black',
        strokeWidth: 2,
        fontWeight: 'normal',
        textAlign: 'start'
      }
    )
  );

  // === DETECTION STATUS ===

  topology.addComputedPoint({
    dataType: 'computed',
    name: 'status_corner',
    computation: () => [10, 55],
    description: 'Status text position'
  });

  topology.add(
    new TextElement(
      'status_info',
      ['computed', 'status_corner'],
      (metadata) => {
        const nCharuco = metadata.nCharucoDetected ?? 0;
        const nAruco = metadata.nArucoDetected ?? 0;

        if (nCharuco === 0 && nAruco === 0) {
          return '⚠ NO BOARD DETECTED';
        } else if (nCharuco < 4) {
          return '⚠ INSUFFICIENT CORNERS';
        } else {
          return '✓ BOARD DETECTED';
        }
      },
      [0, 0],
      {
        fontSize: 14,
        fontFamily: 'Arial, sans-serif',
        fill: 'rgb(0, 255, 0)',
        stroke: 'black',
        strokeWidth: 2,
        fontWeight: 'normal',
        textAlign: 'start'
      }
    )
  );

  return topology;
}

// ============================================================================
// DATA FORMAT TYPES
// ============================================================================

export interface CharucoDetectionData {
  charuco?: Record<string, [number, number]>;  // charuco_0, charuco_1, ...
  aruco?: Record<string, [number, number]>;    // aruco_0_corner_0, ...
}

export interface CharucoMetadata {
  frameIdx: number;
  totalFrames: number;
  nCharucoDetected: number;
  nCharucoTotal: number;
  nArucoDetected: number;
  nArucoTotal: number;
  imageWidth: number;
  imageHeight: number;
  hasPose: boolean;
  translation?: [number, number, number];
  rotation?: [number, number, number];
}

// ============================================================================
// EXAMPLE WEBSOCKET MESSAGE FORMAT
// ============================================================================

/*
Expected WebSocket message from Python backend:

{
  "points": {
    "charuco": {
      "charuco_0": [120.5, 340.2],
      "charuco_1": [145.3, 338.9],
      "charuco_15": [180.1, 360.5],
      ...
    },
    "aruco": {
      "aruco_0_corner_0": [100.0, 100.0],
      "aruco_0_corner_1": [150.0, 100.0],
      "aruco_0_corner_2": [150.0, 150.0],
      "aruco_0_corner_3": [100.0, 150.0],
      "aruco_5_corner_0": [200.0, 200.0],
      ...
    }
  },
  "metadata": {
    "frameIdx": 42,
    "totalFrames": 1000,
    "nCharucoDetected": 16,
    "nCharucoTotal": 48,
    "nArucoDetected": 6,
    "nArucoTotal": 12,
    "imageWidth": 1920,
    "imageHeight": 1080,
    "hasPose": true,
    "translation": [0.5, 0.3, 10.0],
    "rotation": [0.1, 0.2, 0.3]
  }
}

*/

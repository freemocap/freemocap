import { OverlayTopology } from './overlay-topology';
import {
  PointElement,
  LineElement,
  CircleElement,
  CrosshairElement,
  TextElement,
  EllipseElement
} from './overlay-elements';
import { PointsDict } from './overlay-types';

// ============================================================================
// CREATE EYE TRACKING TOPOLOGY
// ============================================================================

interface EyeTopologyOptions {
  width: number;
  height: number;
  showCleaned?: boolean;
  showRaw?: boolean;
  showDots?: boolean;
  showEllipse?: boolean;
  showSnake?: boolean;
  nSnakePoints?: number;
}

export function createFullEyeTopology(options: EyeTopologyOptions): OverlayTopology {
  const {
    width,
    height,
    showCleaned = true,
    showRaw = false,
    showDots = true,
    showEllipse = true,
    showSnake = false,
    nSnakePoints = 50
  } = options;

  const topology = new OverlayTopology('full_eye_tracking', width, height);

  // Define required points
  if (showCleaned) {
    for (let i = 1; i <= 8; i++) {
      topology.requiredPoints.push(['cleaned', `p${i}`]);
    }
    topology.requiredPoints.push(['cleaned', 'tear_duct']);
    topology.requiredPoints.push(['cleaned', 'outer_eye']);
  }

  if (showRaw) {
    for (let i = 1; i <= 8; i++) {
      topology.requiredPoints.push(['raw', `p${i}`]);
    }
    topology.requiredPoints.push(['raw', 'tear_duct']);
    topology.requiredPoints.push(['raw', 'outer_eye']);
  }

  // === COMPUTED PUPIL CENTERS ===

  if (showRaw) {
    topology.addComputedPoint({
      dataType: 'computed',
      name: 'pupil_center_raw',
      computation: (points: PointsDict) => {
        if (!points.raw) return [NaN, NaN];

        const pupilPoints: [number, number][] = [];
        for (let i = 1; i <= 8; i++) {
          const pt = points.raw[`p${i}`];
          if (pt) pupilPoints.push(pt);
        }

        if (pupilPoints.length === 0) return [NaN, NaN];

        const sumX = pupilPoints.reduce((sum, pt) => sum + pt[0], 0);
        const sumY = pupilPoints.reduce((sum, pt) => sum + pt[1], 0);
        return [sumX / pupilPoints.length, sumY / pupilPoints.length];
      },
      description: 'Mean of raw pupil points'
    });
  }

  if (showCleaned) {
    topology.addComputedPoint({
      dataType: 'computed',
      name: 'pupil_center_cleaned',
      computation: (points: PointsDict) => {
        if (!points.cleaned) return [NaN, NaN];

        const pupilPoints: [number, number][] = [];
        for (let i = 1; i <= 8; i++) {
          const pt = points.cleaned[`p${i}`];
          if (pt) pupilPoints.push(pt);
        }

        if (pupilPoints.length === 0) return [NaN, NaN];

        const sumX = pupilPoints.reduce((sum, pt) => sum + pt[0], 0);
        const sumY = pupilPoints.reduce((sum, pt) => sum + pt[1], 0);
        return [sumX / pupilPoints.length, sumY / pupilPoints.length];
      },
      description: 'Mean of cleaned pupil points'
    });
  }

  // === CONNECTION LINES (CLEANED ONLY) ===

  if (showCleaned) {
    const lineStyle = {
      stroke: 'rgb(0, 200, 255)',
      strokeWidth: 2,
      opacity: 1.0
    };

    // Pupil outline (closed loop)
    for (let i = 1; i <= 7; i++) {
      topology.add(
        new LineElement(
          `pupil_connection_${i}`,
          ['cleaned', `p${i}`],
          ['cleaned', `p${i + 1}`],
          lineStyle
        )
      );
    }
    topology.add(
      new LineElement(
        'pupil_connection_8',
        ['cleaned', 'p8'],
        ['cleaned', 'p1'],
        lineStyle
      )
    );

    // Eye corner connections
    topology.add(
      new LineElement(
        'eye_span',
        ['cleaned', 'tear_duct'],
        ['cleaned', 'outer_eye'],
        lineStyle
      )
    );
    topology.add(
      new LineElement(
        'tear_to_pupil',
        ['cleaned', 'tear_duct'],
        ['cleaned', 'p1'],
        lineStyle
      )
    );
  }

  // === LANDMARK POINTS ===

  if (showCleaned && showDots) {
    const cleanedPointStyle = {
      radius: 3,
      fill: 'rgb(0, 200, 255)',
      opacity: 1.0
    };

    // Pupil points
    for (let i = 1; i <= 8; i++) {
      topology.add(
        new PointElement(
          `pupil_point_${i}_cleaned`,
          ['cleaned', `p${i}`],
          cleanedPointStyle,
          `p${i}`,
          [5, -5]
        )
      );
    }

    // Eye corners
    const cleanedCornerStyle = {
      radius: 4,
      fill: 'rgb(0, 220, 255)',
      opacity: 1.0
    };

    topology.add(
      new PointElement(
        'tear_duct_point_cleaned',
        ['cleaned', 'tear_duct'],
        cleanedCornerStyle,
        'Tear Duct',
        [5, -5]
      )
    );
    topology.add(
      new PointElement(
        'outer_eye_point_cleaned',
        ['cleaned', 'outer_eye'],
        cleanedCornerStyle,
        'Outer Eye',
        [5, -5]
      )
    );
  }

  if (showRaw && showDots) {
    const rawPointStyle = {
      radius: 2,
      fill: 'rgb(255, 100, 50)',
      opacity: 1.0
    };

    // Pupil points
    for (let i = 1; i <= 8; i++) {
      topology.add(
        new PointElement(
          `pupil_point_${i}_raw`,
          ['raw', `p${i}`],
          rawPointStyle,
          showCleaned ? undefined : `p${i}`,
          [5, -5]
        )
      );
    }

    // Eye corners
    const rawCornerStyle = {
      radius: 4,
      fill: 'rgb(255, 120, 0)',
      opacity: 1.0
    };

    topology.add(
      new PointElement(
        'tear_duct_point_raw',
        ['raw', 'tear_duct'],
        rawCornerStyle,
        showCleaned ? undefined : 'Tear Duct',
        [5, -5]
      )
    );
    topology.add(
      new PointElement(
        'outer_eye_point_raw',
        ['raw', 'outer_eye'],
        rawCornerStyle,
        showCleaned ? undefined : 'Outer Eye',
        [5, -5]
      )
    );
  }

  // === FITTED ELLIPSES ===

  if (showCleaned && showEllipse) {
    topology.addComputedPoint({
      dataType: 'computed',
      name: 'fitted_ellipse_cleaned',
      computation: (points: PointsDict) => {
        if (!points.cleaned) return [NaN, NaN, NaN, NaN, NaN] as any;

        try {
          const pupilPoints: [number, number][] = [];
          for (let i = 1; i <= 8; i++) {
            const pt = points.cleaned[`p${i}`];
            if (pt) pupilPoints.push(pt);
          }

          // Simple ellipse fitting (you'd replace this with actual fitting)
          // For now, return dummy params: [cx, cy, a, b, theta]
          const cx = pupilPoints.reduce((s, p) => s + p[0], 0) / pupilPoints.length;
          const cy = pupilPoints.reduce((s, p) => s + p[1], 0) / pupilPoints.length;
          return [cx, cy, 20, 15, 0] as any; // Dummy ellipse
        } catch {
          return [NaN, NaN, NaN, NaN, NaN] as any;
        }
      },
      description: 'Fitted ellipse parameters for cleaned pupil points'
    });

    topology.add(
      new EllipseElement(
        'pupil_ellipse_cleaned',
        ['computed', 'fitted_ellipse_cleaned'],
        100,
        {
          stroke: 'rgb(255, 0, 255)',
          strokeWidth: 2,
          opacity: 0.8
        }
      )
    );
  }

  // === PUPIL CENTERS ===

  if (showCleaned) {
    topology.add(
      new CircleElement(
        'pupil_center_circle_cleaned',
        ['computed', 'pupil_center_cleaned'],
        5,
        { radius: 5, fill: 'rgb(255, 250, 0)', opacity: 1.0 }
      )
    );

    topology.add(
      new CrosshairElement(
        'pupil_center_crosshair_cleaned',
        ['computed', 'pupil_center_cleaned'],
        10,
        { stroke: 'rgb(255, 250, 0)', strokeWidth: 2, opacity: 1.0 }
      )
    );
  }

  if (showRaw) {
    topology.add(
      new CircleElement(
        'pupil_center_circle_raw',
        ['computed', 'pupil_center_raw'],
        5,
        { radius: 5, fill: 'rgb(255, 200, 0)', opacity: 1.0 }
      )
    );

    topology.add(
      new CrosshairElement(
        'pupil_center_crosshair_raw',
        ['computed', 'pupil_center_raw'],
        10,
        { stroke: 'rgb(255, 200, 0)', strokeWidth: 2, opacity: 1.0 }
      )
    );
  }

  // === FRAME INFO (DYNAMIC TEXT) ===

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
        const viewMode = metadata.viewMode ?? 'unknown';
        const snakeStatus = metadata.snakeStatus ?? '';
        const statusStr = snakeStatus ? ` | ${snakeStatus}` : '';
        return `Frame: ${frameIdx}/${totalFrames} | Mode: ${viewMode}${statusStr}`;
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

  return topology;
}

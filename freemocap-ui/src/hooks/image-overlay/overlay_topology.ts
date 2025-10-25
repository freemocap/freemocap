import { OverlayElement } from './overlay-elements';
import { ComputedPoint, PointsDict, Metadata } from './overlay-types';

// ============================================================================
// TOPOLOGY
// ============================================================================

export class OverlayTopology {
  public requiredPoints: Array<[string, string]> = [];
  public computedPoints: ComputedPoint[] = [];
  public elements: OverlayElement[] = [];

  constructor(
    public readonly name: string,
    public readonly width: number,
    public readonly height: number
  ) {}

  add(element: OverlayElement): this {
    this.elements.push(element);
    return this;
  }

  addComputedPoint(computed: ComputedPoint): this {
    this.computedPoints.push(computed);
    return this;
  }

  toJSON(): object {
    return {
      name: this.name,
      requiredPoints: this.requiredPoints,
      width: this.width,
      height: this.height,
      elements: this.elements.map(elem => ({
        elementType: elem.elementType,
        name: elem.name,
        visible: elem.visible
      }))
    };
  }
}

// ============================================================================
// RENDERER
// ============================================================================

export class OverlayRenderer {
  constructor(public readonly topology: OverlayTopology) {}

  private computeAllPoints(points: PointsDict): PointsDict {
    // Deep copy input points
    const allPoints: PointsDict = {};
    for (const [dataType, pointsDict] of Object.entries(points)) {
      allPoints[dataType] = { ...pointsDict };
    }

    // Compute derived points
    for (const computed of this.topology.computedPoints) {
      try {
        const result = computed.computation(allPoints);

        // Ensure the data type dict exists
        if (!allPoints[computed.dataType]) {
          allPoints[computed.dataType] = {};
        }

        allPoints[computed.dataType][computed.name] = result;
      } catch (e) {
        console.warn(
          `Failed to compute '${computed.dataType}.${computed.name}':`,
          e
        );
      }
    }

    return allPoints;
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata = {}
  ): void {
    const allPoints = this.computeAllPoints(points);

    // Render all visible elements
    for (const element of this.topology.elements) {
      if (element.visible) {
        try {
          element.render(ctx, allPoints, metadata);
        } catch (e) {
          console.warn(`Failed to render element '${element.name}':`, e);
        }
      }
    }
  }

  // Convenience method for rendering on top of existing canvas content
  renderOverlay(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata = {},
    clearFirst: boolean = false
  ): void {
    if (clearFirst) {
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    }

    this.render(ctx, points, metadata);
  }
}

// ============================================================================
// CONVENIENCE FUNCTIONS
// ============================================================================

export function renderOverlay(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  topology: OverlayTopology,
  points: PointsDict,
  metadata: Metadata = {}
): void {
  const renderer = new OverlayRenderer(topology);
  renderer.render(ctx, points, metadata);
}

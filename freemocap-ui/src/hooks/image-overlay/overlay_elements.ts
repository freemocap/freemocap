import {
  PointStyle,
  LineStyle,
  TextStyle,
  PointReference,
  PointsDict,
  isValidPoint,
  Metadata,
  DynamicText,
} from './overlay-types';

// ============================================================================
// BASE ELEMENT
// ============================================================================

export abstract class OverlayElement {
  constructor(
    public readonly elementType: string,
    public readonly name: string,
    public visible: boolean = true
  ) {}

  abstract render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void;

  protected parseColor(color: string, opacity: number = 1.0): string {
    const trimmed = color.trim().toLowerCase();
    
    if (trimmed.startsWith('rgb(') && trimmed.endsWith(')')) {
      const values = trimmed.slice(4, -1).split(',').map(v => parseInt(v.trim()));
      return `rgba(${values[0]}, ${values[1]}, ${values[2]}, ${opacity})`;
    }
    
    // Support named colors directly with opacity
    return opacity < 1.0 ? `rgba(0, 0, 0, ${opacity})` : color;
  }
}

// ============================================================================
// POINT ELEMENT
// ============================================================================

export class PointElement extends OverlayElement {
  private pointRef: PointReference;
  
  constructor(
    name: string,
    pointName: string | [string, string] | PointReference,
    public style: PointStyle = {
      radius: 3,
      fill: 'rgb(0, 255, 0)',
      opacity: 1.0
    },
    public label?: string,
    public labelOffset: [number, number] = [5, -5],
    public labelStyle: TextStyle = {
      fontSize: 12,
      fontFamily: 'Arial, sans-serif',
      fill: 'white',
      stroke: 'black',
      strokeWidth: 1,
      fontWeight: 'normal',
      textAlign: 'start'
    }
  ) {
    super('point', name);
    this.pointRef = PointReference.parse(pointName);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    const point = this.pointRef.getPoint(points);
    if (!isValidPoint(point)) return;

    const [x, y] = point;
    const r = this.style.radius;

    // Draw circle
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = this.parseColor(this.style.fill, this.style.opacity);
    ctx.fill();

    if (this.style.stroke) {
      ctx.strokeStyle = this.parseColor(this.style.stroke, this.style.opacity);
      ctx.lineWidth = this.style.strokeWidth ?? 1;
      ctx.stroke();
    }

    // Draw label if present
    if (this.label) {
      const labelX = x + this.labelOffset[0];
      const labelY = y + this.labelOffset[1];

      ctx.font = `${this.labelStyle.fontWeight} ${this.labelStyle.fontSize}px ${this.labelStyle.fontFamily}`;
      ctx.textAlign = this.labelStyle.textAlign;
      ctx.textBaseline = 'middle';

      // Draw stroke outline
      if (this.labelStyle.stroke && this.labelStyle.strokeWidth) {
        ctx.strokeStyle = this.labelStyle.stroke;
        ctx.lineWidth = this.labelStyle.strokeWidth * 2;
        ctx.strokeText(this.label, labelX, labelY);
      }

      // Draw fill
      ctx.fillStyle = this.labelStyle.fill;
      ctx.fillText(this.label, labelX, labelY);
    }
  }
}

// ============================================================================
// LINE ELEMENT
// ============================================================================

export class LineElement extends OverlayElement {
  private pointARef: PointReference;
  private pointBRef: PointReference;

  constructor(
    name: string,
    pointA: string | [string, string] | PointReference,
    pointB: string | [string, string] | PointReference,
    public style: LineStyle = {
      stroke: 'rgb(255, 55, 55)',
      strokeWidth: 2,
      opacity: 1.0
    }
  ) {
    super('line', name);
    this.pointARef = PointReference.parse(pointA);
    this.pointBRef = PointReference.parse(pointB);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    const ptA = this.pointARef.getPoint(points);
    const ptB = this.pointBRef.getPoint(points);

    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return;

    ctx.beginPath();
    ctx.moveTo(ptA[0], ptA[1]);
    ctx.lineTo(ptB[0], ptB[1]);

    ctx.strokeStyle = this.parseColor(this.style.stroke, this.style.opacity);
    ctx.lineWidth = this.style.strokeWidth;

    if (this.style.strokeDasharray) {
      ctx.setLineDash(this.style.strokeDasharray);
    }

    ctx.stroke();
    ctx.setLineDash([]); // Reset
  }
}

// ============================================================================
// CIRCLE ELEMENT
// ============================================================================

export class CircleElement extends OverlayElement {
  private centerRef: PointReference;

  constructor(
    name: string,
    centerPoint: string | [string, string] | PointReference,
    public radius: number,
    public style: PointStyle = {
      radius: 5,
      fill: 'rgb(255, 250, 0)',
      opacity: 1.0
    }
  ) {
    super('circle', name);
    this.centerRef = PointReference.parse(centerPoint);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    const center = this.centerRef.getPoint(points);
    if (!isValidPoint(center)) return;

    ctx.beginPath();
    ctx.arc(center[0], center[1], this.radius, 0, Math.PI * 2);
    ctx.fillStyle = this.parseColor(this.style.fill, this.style.opacity);
    ctx.fill();

    if (this.style.stroke) {
      ctx.strokeStyle = this.parseColor(this.style.stroke, this.style.opacity);
      ctx.lineWidth = this.style.strokeWidth ?? 1;
      ctx.stroke();
    }
  }
}

// ============================================================================
// CROSSHAIR ELEMENT
// ============================================================================

export class CrosshairElement extends OverlayElement {
  private centerRef: PointReference;

  constructor(
    name: string,
    centerPoint: string | [string, string] | PointReference,
    public size: number = 10,
    public style: LineStyle = {
      stroke: 'rgb(255, 250, 0)',
      strokeWidth: 2,
      opacity: 1.0
    }
  ) {
    super('crosshair', name);
    this.centerRef = PointReference.parse(centerPoint);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    const center = this.centerRef.getPoint(points);
    if (!isValidPoint(center)) return;

    const [cx, cy] = center;

    ctx.strokeStyle = this.parseColor(this.style.stroke, this.style.opacity);
    ctx.lineWidth = this.style.strokeWidth;

    // Horizontal line
    ctx.beginPath();
    ctx.moveTo(cx - this.size, cy);
    ctx.lineTo(cx + this.size, cy);
    ctx.stroke();

    // Vertical line
    ctx.beginPath();
    ctx.moveTo(cx, cy - this.size);
    ctx.lineTo(cx, cy + this.size);
    ctx.stroke();
  }
}

// ============================================================================
// TEXT ELEMENT
// ============================================================================

export class TextElement extends OverlayElement {
  private pointRef: PointReference;

  constructor(
    name: string,
    pointName: string | [string, string] | PointReference,
    public text: DynamicText,
    public offset: [number, number] = [0, 0],
    public style: TextStyle = {
      fontSize: 12,
      fontFamily: 'Arial, sans-serif',
      fill: 'white',
      stroke: 'black',
      strokeWidth: 1,
      fontWeight: 'normal',
      textAlign: 'start'
    }
  ) {
    super('text', name);
    this.pointRef = PointReference.parse(pointName);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    const point = this.pointRef.getPoint(points);
    if (!isValidPoint(point)) return;

    const x = point[0] + this.offset[0];
    const y = point[1] + this.offset[1];

    const textToRender = typeof this.text === 'function' 
      ? this.text(metadata) 
      : this.text;

    ctx.font = `${this.style.fontWeight} ${this.style.fontSize}px ${this.style.fontFamily}`;
    ctx.textAlign = this.style.textAlign;
    ctx.textBaseline = 'middle';

    // Draw stroke outline
    if (this.style.stroke && this.style.strokeWidth) {
      ctx.strokeStyle = this.style.stroke;
      ctx.lineWidth = this.style.strokeWidth * 2;
      ctx.strokeText(textToRender, x, y);
    }

    // Draw fill
    ctx.fillStyle = this.style.fill;
    ctx.fillText(textToRender, x, y);
  }
}

// ============================================================================
// ELLIPSE ELEMENT
// ============================================================================

export class EllipseElement extends OverlayElement {
  private paramsRef: PointReference;

  constructor(
    name: string,
    paramsPoint: string | [string, string] | PointReference,
    public nPoints: number = 100,
    public style: LineStyle = {
      stroke: 'rgb(255, 0, 255)',
      strokeWidth: 2,
      opacity: 0.8
    }
  ) {
    super('ellipse', name);
    this.paramsRef = PointReference.parse(paramsPoint);
  }

  render(
    ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
    points: PointsDict,
    metadata: Metadata
  ): void {
    // Get params as [cx, cy, a, b, theta]
    const params = this.paramsRef.getPoint(points) as unknown as number[] | null;
    
    if (!params || params.length !== 5 || params.some(isNaN)) return;

    const [cx, cy, semiMajor, semiMinor, rotation] = params;

    const angleStep = (2 * Math.PI) / this.nPoints;
    const cosT = Math.cos(rotation);
    const sinT = Math.sin(rotation);

    ctx.beginPath();

    for (let i = 0; i <= this.nPoints; i++) {
      const theta = i * angleStep;
      const xLocal = semiMajor * Math.cos(theta);
      const yLocal = semiMinor * Math.sin(theta);

      const x = cx + xLocal * cosT - yLocal * sinT;
      const y = cy + xLocal * sinT + yLocal * cosT;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.closePath();
    ctx.strokeStyle = this.parseColor(this.style.stroke, this.style.opacity);
    ctx.lineWidth = this.style.strokeWidth;
    ctx.stroke();
  }
}

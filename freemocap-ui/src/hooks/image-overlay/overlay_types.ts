// ============================================================================
// STYLE TYPES
// ============================================================================

export interface PointStyle {
  radius: number;
  fill: string;
  stroke?: string;
  strokeWidth?: number;
  opacity: number;
}

export interface LineStyle {
  stroke: string;
  strokeWidth: number;
  opacity: number;
  strokeDasharray?: number[];
}

export interface TextStyle {
  fontSize: number;
  fontFamily: string;
  fill: string;
  stroke?: string;
  strokeWidth?: number;
  fontWeight: string;
  textAlign: CanvasTextAlign;
}

// ============================================================================
// POINT REFERENCE SYSTEM
// ============================================================================

export class PointReference {
  constructor(
    public readonly dataType: string,
    public readonly name: string
  ) {}

  static parse(reference: string | [string, string] | PointReference): PointReference {
    if (reference instanceof PointReference) {
      return reference;
    }
    
    if (Array.isArray(reference)) {
      return new PointReference(reference[0], reference[1]);
    }
    
    if (typeof reference === 'string') {
      const parts = reference.includes('.') 
        ? reference.split('.', 2)
        : reference.split('/', 2);
      
      if (parts.length !== 2) {
        throw new Error(`Invalid point reference: ${reference}`);
      }
      
      return new PointReference(parts[0], parts[1]);
    }
    
    throw new Error(`Invalid reference type: ${typeof reference}`);
  }

  getPoint(points: PointsDict): [number, number] | null {
    const dataTypeDict = points[this.dataType];
    if (!dataTypeDict) return null;
    return dataTypeDict[this.name] ?? null;
  }

  toString(): string {
    return `${this.dataType}.${this.name}`;
  }
}

export type PointsDict = Record<string, Record<string, [number, number]>>;

export function isValidPoint(point: [number, number] | null): point is [number, number] {
  return point !== null && !isNaN(point[0]) && !isNaN(point[1]);
}

// ============================================================================
// COMPUTED POINTS
// ============================================================================

export interface ComputedPoint {
  dataType: string;
  name: string;
  computation: (points: PointsDict) => [number, number];
  description?: string;
}

// ============================================================================
// METADATA
// ============================================================================

export type Metadata = Record<string, unknown>;
export type DynamicText = string | ((metadata: Metadata) => string);

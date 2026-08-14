export interface GeoJSONFeature {
  type: "Feature";
  id?: number;
  properties: {
    name?: string;
    description?: string;
    [key: string]: any;
  };
  geometry: {
    type: string;
    coordinates: any[];
  };
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

export interface BoundsResponse {
  bbox: [number, number, number, number];
  bounds: [[number, number], [number, number]];
  center: [number, number];
}

export interface DeltaResponse {
  path: string;
  vmin: number;
  vmax: number;
}

export type ViewMode = "single" | "delta";
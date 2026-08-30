export interface AnalyzeResponse {
  location_name: string;
  bbox: number[];
  deforestation_score: number;
  greenery_coverage_pct: number;
  total_area_analyzed_km2: number;
  canopy_change_pct: number;
  images: {
    [year: string]: string;
  };
}
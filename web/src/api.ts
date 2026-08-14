import { GeoJSONFeatureCollection, BoundsResponse, DeltaResponse } from "./types";

export async function getYears(): Promise<number[]> {
  const res = await fetch("/api/years");
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to load years (${res.status}): ${text}`);
  }
  const json = await res.json();
  return json.years;
}

export async function fetchAOIGeoJSON(): Promise<GeoJSONFeatureCollection> {
  const res = await fetch("/api/aoi");
  if (!res.ok) {
    throw new Error(`Failed to query PostGIS AOI (${res.status})`);
  }
  return await res.json();
}

export async function buildDelta(fromYear: number, toYear: number): Promise<DeltaResponse> {
  const res = await fetch("/api/delta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_year: fromYear, to_year: toYear }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to build delta (${res.status}): ${text}`);
  }

  return await res.json();
}

export async function getBounds(year: number): Promise<BoundsResponse> {
  const res = await fetch(`/api/bounds/${year}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`getBounds failed (${res.status}): ${text}`);
  }
  return await res.json();
}
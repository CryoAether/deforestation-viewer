import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";

import { getYears, buildDelta, getBounds, fetchAOIGeoJSON } from "./api";
import NDVILayer from "./layers/NDVILayer";
import DeltaLayer from "./layers/DeltaLayer";
import Legend from "./components/Legend";
import { ViewMode, GeoJSONFeatureCollection } from "./types";

const ESRI_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function FitBounds({ bounds }: { bounds: [[number, number], [number, number]] | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length === 2) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }, [bounds, map]);
  return null;
}

export default function App() {
  const [bounds, setBounds] = useState<[[number, number], [number, number]] | null>(null);
  const [years, setYears] = useState<number[]>([]);
  const [mode, setMode] = useState<ViewMode>("single");

  const [year, setYear] = useState<number | null>(null);
  const [fromYear, setFromYear] = useState<number | null>(null);
  const [toYear, setToYear] = useState<number | null>(null);

  const [showContext, setShowContext] = useState<boolean>(true);
  const [deltaRange, setDeltaRange] = useState<{ vmin: number; vmax: number }>({ vmin: -0.3, vmax: 0.3 });
  const [aoiData, setAoiData] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const parseYear = (value: string): number | null => {
    const v = Number.parseInt(value, 10);
    return Number.isFinite(v) ? v : null;
  };

  useEffect(() => {
    (async () => {
      try {
        setError(null);
        const ys = await getYears();
        setYears(ys);

        const first = ys[0] ?? null;
        const latest = ys.length ? ys[ys.length - 1] : null;

        setYear(latest);
        setFromYear(first);
        setToYear(latest);

        if (latest != null) {
          const b = await getBounds(latest);
          setBounds(b.bounds as [[number, number], [number, number]]);
        }

        // Fetch PostGIS geometry
        const geojson = await fetchAOIGeoJSON();
        setAoiData(geojson);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    })();
  }, []);

  useEffect(() => {
    if (mode !== "single" || !year) return;
    (async () => {
      try {
        setError(null);
        const b = await getBounds(year);
        setBounds(b.bounds as [[number, number], [number, number]]);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    })();
  }, [mode, year]);

  useEffect(() => {
    if (mode !== "delta" || !fromYear || !toYear) return;
    (async () => {
      try {
        setError(null);
        const res = await buildDelta(fromYear, toYear);
        setDeltaRange({ vmin: res.vmin, vmax: res.vmax });
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    })();
  }, [mode, fromYear, toYear]);

  return (
    <div className="shell">
      <div className="panel">
        <div className="panelHeader">
          <div className="titleRow">
            <h1 className="h1">Remote Sensing Pipeline Dashboard</h1>
            <span className="badge">{mode === "single" ? "Single Year" : "ΔNDVI"}</span>
          </div>
          {error && <div className="errorBox">{error}</div>}
        </div>

        <div className="panelBody">
          <div className="section">
            <label className="label">Mode</label>
            <select className="select" value={mode} onChange={(e) => setMode(e.target.value as ViewMode)}>
              <option value="single">Single Year Composite</option>
              <option value="delta">Temporal Change (ΔNDVI)</option>
            </select>
          </div>

          {mode === "single" && (
            <div className="section">
              <label className="label">Year</label>
              <select className="select" value={year ?? ""} onChange={(e) => setYear(parseYear(e.target.value))}>
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          )}

          {mode === "delta" && (
            <div className="section">
              <div className="row">
                <div>
                  <label className="label">From</label>
                  <select className="select" value={fromYear ?? ""} onChange={(e) => setFromYear(parseYear(e.target.value))}>
                    {years.map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">To</label>
                  <select className="select" value={toYear ?? ""} onChange={(e) => setToYear(parseYear(e.target.value))}>
                    {years.map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mapWrap">
        <MapContainer center={[0, 0]} zoom={2} style={{ height: "100%", width: "100%" }}>
          <FitBounds bounds={bounds} />
          <TileLayer url={ESRI_TILE_URL} />

          {mode === "single" && year && <NDVILayer year={year} bounds={bounds} />}

          {mode === "delta" && fromYear && toYear && (
            <>
              {showContext && <NDVILayer year={toYear} opacity={0.65} bounds={bounds} />}
              <DeltaLayer fromYear={fromYear} toYear={toYear} bounds={bounds} />
            </>
          )}

          {aoiData && <GeoJSON data={aoiData as any} style={{ color: "#ff7800", weight: 2, fillOpacity: 0.1 }} />}

          <Legend mode={mode} year={year} fromYear={fromYear} toYear={toYear} deltaRange={deltaRange} />
        </MapContainer>
      </div>
    </div>
  );
}
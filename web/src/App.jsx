import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";

import { getYears, buildDelta, getBounds } from "./api.js";
import NDVILayer from "./layers/NDVILayer.jsx";
import DeltaLayer from "./layers/DeltaLayer.jsx";
import Legend from "./components/Legend.jsx";

const ESRI =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function FitBounds({ bounds }) {
  const map = useMap();

  useEffect(() => {
    if (bounds && bounds.length === 2) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }, [bounds, map]);

  return null;
}

export default function App() {
  const [bounds, setBounds] = useState(null);

  const [years, setYears] = useState([]);
  const [mode, setMode] = useState("single");

  const [year, setYear] = useState(null);
  const [fromYear, setFromYear] = useState(null);
  const [toYear, setToYear] = useState(null);

  const [showContext, setShowContext] = useState(true);
  const [deltaRange, setDeltaRange] = useState({ vmin: -0.3, vmax: 0.3 });

  const [error, setError] = useState(null);

  const parseYear = (value) => {
    const v = Number.parseInt(value, 10);
    return Number.isFinite(v) ? v : null;
  };

  // initial load
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
          setBounds(b.bounds);
        }
      } catch (e) {
        setError(e?.message ?? String(e));
      }
    })();
  }, []);

  // refit bounds when year changes in single mode
  useEffect(() => {
    if (mode !== "single") return;
    if (!Number.isFinite(year)) return;

    (async () => {
      try {
        setError(null);
        const b = await getBounds(year);
        setBounds(b.bounds);
      } catch (e) {
        setError(e?.message ?? String(e));
      }
    })();
  }, [mode, year]);

  // build delta range when in delta mode
  useEffect(() => {
    if (mode !== "delta") return;
    if (!Number.isFinite(fromYear) || !Number.isFinite(toYear)) return;

    (async () => {
      try {
        setError(null);
        const res = await buildDelta(fromYear, toYear);
        setDeltaRange({ vmin: res.vmin, vmax: res.vmax });
      } catch (e) {
        setError(e?.message ?? String(e));
      }
    })();
  }, [mode, fromYear, toYear]);

  const resetView = async () => {
    try {
      setError(null);
      const target = Number.isFinite(year) ? year : (years[years.length - 1] ?? null);
      if (target == null) return;
      const b = await getBounds(target);
      setBounds(b.bounds);
    } catch (e) {
      setError(e?.message ?? String(e));
    }
  };

  const modeLabel = mode === "single" ? "Single year" : "ΔNDVI change";

  return (
    <div className="shell">
      <div className="panel">
        <div className="panelHeader">
          <div className="titleRow">
            <h1 className="h1">Deforestation Viewer</h1>
            <span className="badge">{modeLabel}</span>
          </div>
          <p className="sub">
            Interactive NDVI composites and ΔNDVI change tiles served by FastAPI. Basemap: Esri World Imagery.
          </p>

          {error && <div className="errorBox">{error}</div>}
        </div>

        <div className="panelBody">
          <div className="section">
            <label className="label">Mode</label>
            <select className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="single">View single year</option>
              <option value="delta">Compare change (ΔNDVI)</option>
            </select>
          </div>

          {mode === "single" && (
            <div className="section">
              <label className="label">Year</label>
              <select
                className="select"
                value={year ?? ""}
                onChange={(e) => setYear(parseYear(e.target.value))}
              >
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>

              <div className="small">
                Tip: median seasonal composite is usually smoother than max for cloud edge artifacts.
              </div>
            </div>
          )}

          {mode === "delta" && (
            <div className="section">
              <div className="row">
                <div>
                  <label className="label">From</label>
                  <select
                    className="select"
                    value={fromYear ?? ""}
                    onChange={(e) => setFromYear(parseYear(e.target.value))}
                  >
                    {years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">To</label>
                  <select
                    className="select"
                    value={toYear ?? ""}
                    onChange={(e) => setToYear(parseYear(e.target.value))}
                  >
                    {years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="section" style={{ borderTop: "none", paddingTop: 12, marginTop: 0 }}>
                <div className="toggleRow">
                  <input
                    type="checkbox"
                    checked={showContext}
                    onChange={(e) => setShowContext(e.target.checked)}
                  />
                  <span>Show NDVI {toYear} under ΔNDVI</span>
                </div>

                <div className="small">
                  Robust ΔNDVI scale: {deltaRange.vmin.toFixed(2)} to {deltaRange.vmax.toFixed(2)}
                </div>
              </div>
            </div>
          )}

          <div className="section">
            <div className="buttonRow">
              <button className="button" onClick={resetView}>
                Reset view to AOI
              </button>
              <button
                className="buttonSecondary"
                onClick={() => {
                  setMode("single");
                  const latest = years.length ? years[years.length - 1] : null;
                  if (latest != null) setYear(latest);
                }}
              >
                Jump to latest
              </button>
            </div>

            <div className="small">
              In dev: React proxies <code>/api</code> and <code>/tiles</code> to FastAPI.
            </div>
          </div>
        </div>
      </div>

      <div className="mapWrap">
        <MapContainer center={[0, 0]} zoom={2} style={{ height: "100%", width: "100%" }}>
          <FitBounds bounds={bounds} />
          <TileLayer url={ESRI} noWrap />

          {mode === "single" && Number.isFinite(year) && (
            <NDVILayer year={year} bounds={bounds} />
          )}

          {mode === "delta" && Number.isFinite(fromYear) && Number.isFinite(toYear) && (
            <>
              {showContext && <NDVILayer year={toYear} opacity={0.65} bounds={bounds} />}
              <DeltaLayer fromYear={fromYear} toYear={toYear} bounds={bounds} />
            </>
          )}

          <Legend mode={mode} year={year} fromYear={fromYear} toYear={toYear} deltaRange={deltaRange} />
        </MapContainer>
      </div>
    </div>
  );
}
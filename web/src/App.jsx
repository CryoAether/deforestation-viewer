import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { getYears, buildDelta } from "./api.js";
import NDVILayer from "./layers/NDVILayer.jsx";
import DeltaLayer from "./layers/DeltaLayer.jsx";

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

export default function App() {
  const [years, setYears] = useState([]);
  const [mode, setMode] = useState("single");
  const [year, setYear] = useState(null);
  const [fromYear, setFromYear] = useState(null);
  const [toYear, setToYear] = useState(null);
  const [showContext, setShowContext] = useState(true);
  const [deltaRange, setDeltaRange] = useState({ vmin: -0.3, vmax: 0.3 });

  useEffect(() => {
    (async () => {
      const ys = await getYears();
      setYears(ys);
      setYear(ys[0] ?? null);
      setFromYear(ys[0] ?? null);
      setToYear(ys[ys.length - 1] ?? null);
    })();
  }, []);

  useEffect(() => {
    if (mode !== "delta" || !fromYear || !toYear) return;
    (async () => {
      const res = await buildDelta(fromYear, toYear);
      setDeltaRange({ vmin: res.vmin, vmax: res.vmax });
    })();
  }, [mode, fromYear, toYear]);

  const center = useMemo(() => [0, 0], []);

  return (
    <div style={{ height: "100vh", display: "grid", gridTemplateColumns: "360px 1fr" }}>
      <div style={{ padding: 16, borderRight: "1px solid #eee", overflowY: "auto" }}>
        <h2 style={{ margin: 0 }}>Deforestation Viewer</h2>
        <p style={{ marginTop: 8, opacity: 0.8 }}>
          NDVI composites and ΔNDVI change tiles served by FastAPI.
        </p>

        <div style={{ marginTop: 12 }}>
          <label style={{ display: "block", fontWeight: 600 }}>Mode</label>
          <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: "100%", padding: 10 }}>
            <option value="single">View single year</option>
            <option value="delta">Compare change (ΔNDVI)</option>
          </select>
        </div>

        {mode === "single" && (
          <div style={{ marginTop: 12 }}>
            <label style={{ display: "block", fontWeight: 600 }}>Year</label>
            <select value={year ?? ""} onChange={(e) => setYear(parseInt(e.target.value))} style={{ width: "100%", padding: 10 }}>
              {years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        )}

        {mode === "delta" && (
          <>
            <div style={{ marginTop: 12 }}>
              <label style={{ display: "block", fontWeight: 600 }}>From year</label>
              <select value={fromYear ?? ""} onChange={(e) => setFromYear(parseInt(e.target.value))} style={{ width: "100%", padding: 10 }}>
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div style={{ marginTop: 12 }}>
              <label style={{ display: "block", fontWeight: 600 }}>To year</label>
              <select value={toYear ?? ""} onChange={(e) => setToYear(parseInt(e.target.value))} style={{ width: "100%", padding: 10 }}>
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>

            <div style={{ marginTop: 12 }}>
              <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <input type="checkbox" checked={showContext} onChange={(e) => setShowContext(e.target.checked)} />
                Show NDVI {toYear} under ΔNDVI
              </label>
              <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
                ΔNDVI range (robust): {deltaRange.vmin.toFixed(2)} to {deltaRange.vmax.toFixed(2)}
              </div>
            </div>
          </>
        )}

        <div style={{ marginTop: 16, fontSize: 12, opacity: 0.75 }}>
          Tip: in dev, React proxies <code>/api</code> and <code>/tiles</code> to FastAPI.
        </div>
      </div>

      <div style={{ height: "100vh" }}>
        <MapContainer center={center} zoom={10} style={{ height: "100%", width: "100%" }}>
          <TileLayer url={ESRI} />

          {mode === "single" && year && <NDVILayer year={year} />}
          {mode === "delta" && fromYear && toYear && (
            <>
              {showContext && <NDVILayer year={toYear} opacity={0.65} />}
              <DeltaLayer fromYear={fromYear} toYear={toYear} />
            </>
          )}
        </MapContainer>
      </div>
    </div>
  );
}

import React, { useState } from "react";
import { analyzeTown } from "./api";
import { AnalyzeResponse } from "./types";
import "./styles.css";

export default function App() {
  const [town, setTown] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sliderPos, setSliderPos] = useState(50);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!town.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const data = await analyzeTown(town);
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to process region.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Visual Canvas Stage (Top) */}
      <main className="display-stage">
        {result ? (
          <div className="result-card">
            <div className="header-row">
              <span className="location-tag">
                {result.location_name.split(",").slice(0, 2).join(",")}
              </span>
              <div className="stat-group">
                <span className="stat-number">
                  {result.greenery_coverage_pct.toFixed(1)}
                </span>
                <span className="stat-unit">%</span>
              </div>
            </div>

            {/* Split Comparison Slider */}
            <div className="slider-container">
              <img
                src={result.images["2024"]}
                alt="2024 Foliage"
                className="slider-img"
              />
              <div
                className="slider-overlay"
                style={{ clipPath: `inset(0 ${100 - sliderPos}% 0 0)` }}
              >
                <img
                  src={result.images["2020"]}
                  alt="2020 Foliage"
                  className="slider-img"
                />
              </div>


              {/* White divider needle line */}
              <div
                className="slider-divider-line"
                style={{ left: `${sliderPos}%` }}
              />

              <div className="floating-pills">
                <span className="pill">2020</span>
                <span className="pill">2024</span>
              </div>

              {/* Invisible interactive overlay scrubber */}
              <input
                type="range"
                min="0"
                max="100"
                value={sliderPos}
                onChange={(e) => setSliderPos(Number(e.target.value))}
                className="floating-input"
              />
            </div>

            <div className="meta-footer">
              <span>{result.total_area_analyzed_km2.toFixed(1)} km² surveyed</span>
              <span
                className={`delta-badge ${
                  result.canopy_change_pct >= 0 ? "positive" : "negative"
                }`}
              >
                {result.canopy_change_pct >= 0 ? "+" : ""}
                {result.canopy_change_pct.toFixed(1)}% shift
              </span>
            </div>
          </div>
        ) : (
          <div className="placeholder-stage">
            <div className="pulse-dot" />
            <span>Ready for spatial query</span>
          </div>
        )}
      </main>

      {/* Docked Control Deck (Bottom) */}
      <footer className="bottom-dock">
        <h1 className="dock-title">How green is your town?</h1>

        <form onSubmit={handleSearch} className="search-bar">
          <input
            type="text"
            className="search-input"
            placeholder="Search city, town, or coordinates..."
            value={town}
            onChange={(e) => setTown(e.target.value)}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="search-button" disabled={loading}>
            {loading ? "Synthesizing..." : "Analyze"}
          </button>
        </form>

        {error && <div className="error-banner">{error}</div>}
      </footer>
    </div>
  );
}
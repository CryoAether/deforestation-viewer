import React from "react";
import { ViewMode } from "../types";

interface LegendProps {
  mode: ViewMode;
  year: number | null;
  fromYear: number | null;
  toYear: number | null;
  deltaRange: { vmin: number; vmax: number };
}

export const Legend: React.FC<LegendProps> = ({ mode, year, fromYear, toYear, deltaRange }) => {
  return (
    <div className="legend panel">
      <h4>{mode === "single" ? `NDVI Composite (${year})` : `ΔNDVI (${fromYear} → ${toYear})`}</h4>
      {mode === "single" ? (
        <div className="legendGradient ndviGradient">
          <span>0.0 (Barren)</span>
          <span>1.0 (Dense Veg)</span>
        </div>
      ) : (
        <div className="legendGradient deltaGradient">
          <span>{deltaRange.vmin.toFixed(2)} (Loss)</span>
          <span>0.0</span>
          <span>+{deltaRange.vmax.toFixed(2)} (Gain)</span>
        </div>
      )}
    </div>
  );
};

export default Legend;
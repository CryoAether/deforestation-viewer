import React, { useMemo } from "react";

function GradientBar({ stops }) {
  const background = useMemo(() => {
    const parts = stops.map((s) => `${s.color} ${s.at}%`);
    return `linear-gradient(90deg, ${parts.join(", ")})`;
  }, [stops]);

  return <div className="legendBar" style={{ background }} />;
}

export default function Legend({ mode, year, fromYear, toYear, deltaRange }) {
  if (mode === "single") {
    // NDVI colormap feel: red -> yellow -> green
    const stops = [
      { at: 0, color: "#b2182b" },
      { at: 50, color: "#fddc6c" },
      { at: 100, color: "#1a9850" },
    ];

    return (
      <div className="mapHud">
        <div className="legendTitle">NDVI {year ?? ""}</div>
        <GradientBar stops={stops} />
        <div className="legendTicks">
          <span>0.0</span>
          <span>0.5</span>
          <span>1.0</span>
        </div>
        <div className="legendHint">
          Higher NDVI generally indicates denser/healthier vegetation. Water/cloud-masked pixels are transparent.
        </div>
      </div>
    );
  }

  // Delta mode: coolwarm (blue -> white -> red)
  const vmin = deltaRange?.vmin ?? -0.3;
  const vmax = deltaRange?.vmax ?? 0.3;

  const stops = [
    { at: 0, color: "#3b4cc0" },
    { at: 50, color: "#f7f7f7" },
    { at: 100, color: "#b40426" },
  ];

  return (
    <div className="mapHud">
      <div className="legendTitle">
        ΔNDVI {fromYear} → {toYear}
      </div>
      <GradientBar stops={stops} />
      <div className="legendTicks">
        <span>{vmin.toFixed(2)}</span>
        <span>0</span>
        <span>{vmax.toFixed(2)}</span>
      </div>
      <div className="legendHint">
        Negative values often indicate vegetation loss. Range is robust-percentile scaled (2%–98%).
      </div>
    </div>
  );
}
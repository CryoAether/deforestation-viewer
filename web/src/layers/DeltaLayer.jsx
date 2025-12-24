import React from "react";
import { TileLayer } from "react-leaflet";

export default function DeltaLayer({ fromYear, toYear, opacity = 0.85 }) {
  const url = `/tiles/delta/${fromYear}/${toYear}/{z}/{x}/{y}.png`;
  return <TileLayer url={url} opacity={opacity} />;
}

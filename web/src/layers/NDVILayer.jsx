import React from "react";
import { TileLayer } from "react-leaflet";

export default function NDVILayer({ year, opacity = 0.9 }) {
  const url = `/tiles/ndvi/${year}/{z}/{x}/{y}.png`;
  return <TileLayer url={url} opacity={opacity} noWrap />;
}

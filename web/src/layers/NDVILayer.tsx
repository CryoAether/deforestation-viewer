import React from "react";
import { TileLayer } from "react-leaflet";

interface NDVILayerProps {
  year: number;
  opacity?: number;
  bounds?: [[number, number], [number, number]] | null;
}

export const NDVILayer: React.FC<NDVILayerProps> = ({ year, opacity = 1.0 }) => {
  const url = `/tiles/ndvi/${year}/{z}/{x}/{y}.png`;
  return <TileLayer url={url} opacity={opacity} tileSize={256} maxZoom={18} />;
};

export default NDVILayer;
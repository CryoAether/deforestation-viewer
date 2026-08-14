import React from "react";
import { TileLayer } from "react-leaflet";

interface DeltaLayerProps {
  fromYear: number;
  toYear: number;
  bounds?: [[number, number], [number, number]] | null;
}

export const DeltaLayer: React.FC<DeltaLayerProps> = ({ fromYear, toYear }) => {
  const url = `/tiles/delta/${fromYear}/${toYear}/{z}/{x}/{y}.png`;
  return <TileLayer url={url} tileSize={256} maxZoom={18} />;
};

export default DeltaLayer;
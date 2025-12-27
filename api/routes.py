from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import rasterio
from pyproj import Transformer

from .config import COMP_DIR
from .delta import ensure_delta, ndvi_path
from .raster import robust_range

router = APIRouter(prefix="/api")


def bounds_wgs84(path: str):
    with rasterio.open(path) as ds:
        b = ds.bounds
        crs = ds.crs

    tfm = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    west, south = tfm.transform(b.left, b.bottom)
    east, north = tfm.transform(b.right, b.top)

    return {
        "bbox": [west, south, east, north],
        "bounds": [[south, west], [north, east]],  # Leaflet format
        "center": [(south + north) / 2, (west + east) / 2],
    }


def _years() -> List[int]:
    years: List[int] = []
    for p in list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")):
        try:
            years.append(int(p.stem.split("_")[-1]))
        except Exception:
            pass
    return sorted(set(years))


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/bounds/{year}")
def get_bounds(year: int):
    try:
        p = ndvi_path(year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return bounds_wgs84(str(p))


@router.get("/years")
def years():
    ys = _years()
    if not ys:
        raise HTTPException(status_code=404, detail=f"No composites found in {COMP_DIR}")
    return {"years": ys}


class DeltaReq(BaseModel):
    from_year: int
    to_year: int


@router.post("/delta")
def build_delta(req: DeltaReq):
    path = ensure_delta(req.from_year, req.to_year)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))
    return {"path": str(path), "vmin": vmin, "vmax": vmax}
from __future__ import annotations

import pathlib as pl
from functools import lru_cache

import numpy as np
import rioxarray as rxr

from .config import CHANGE_DIR, COMP_DIR, NODATA

def ndvi_path(year: int) -> pl.Path:
    p = COMP_DIR / f"ndvi_median_{year}.tif"
    if p.exists():
        return p
    p2 = COMP_DIR / f"ndvi_median_{year}.tiff"
    if p2.exists():
        return p2
    raise FileNotFoundError(f"No composite found for year {year} in {COMP_DIR}")

@lru_cache(maxsize=256)
def open_ndvi(year: int):
    return rxr.open_rasterio(str(ndvi_path(year))).squeeze()

def delta_path(y1: int, y2: int) -> pl.Path:
    return CHANGE_DIR / f"ndvi_delta_{y1}_{y2}.tif"

def ensure_delta(y1: int, y2: int) -> pl.Path:
    """Compute and cache ΔNDVI = NDVI(y2) - NDVI(y1)."""
    CHANGE_DIR.mkdir(parents=True, exist_ok=True)
    out = delta_path(y1, y2)
    if out.exists():
        return out

    ndvi1 = open_ndvi(y1)
    ndvi2 = open_ndvi(y2)

    if not (ndvi2.rio.crs == ndvi1.rio.crs and ndvi2.rio.transform() == ndvi1.rio.transform()):
        ndvi2 = ndvi2.rio.reproject_match(ndvi1)

    delta = (ndvi2 - ndvi1)
    delta = delta.rio.write_nodata(NODATA, inplace=False).fillna(NODATA)
    delta = delta.rio.write_crs(ndvi1.rio.crs, inplace=False)
    delta.rio.to_raster(out, driver="COG", compress="DEFLATE", dtype="float32")
    return out

from __future__ import annotations

import pathlib as pl

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from rio_tiler.io import COGReader

from .config import COMP_DIR, CHANGE_DIR, NODATA
from .delta import ensure_delta
from .color import render_png_singleband
from .raster import robust_range

router = APIRouter()

def _ndvi_file(year: int) -> pl.Path:
    p = COMP_DIR / f"ndvi_median_{year}.tif"
    if p.exists():
        return p
    p2 = COMP_DIR / f"ndvi_median_{year}.tiff"
    if p2.exists():
        return p2
    raise FileNotFoundError

@router.get("/tiles/ndvi/{year}/{z}/{x}/{y}.png")
def ndvi_tile(year: int, z: int, x: int, y: int, opacity: float = 1.0):
    try:
        path = _ndvi_file(year)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Missing composite for year={year}")

    with COGReader(path) as cog:
        img = cog.tile(x, y, z)
        # img.data shape: (bands, h, w). Expect single band.
        band = img.data[0]
    png = render_png_singleband(band, vmin=0.0, vmax=1.0, cmap_name="RdYlGn", nodata=NODATA)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

@router.get("/tiles/delta/{y1}/{y2}/{z}/{x}/{y}.png")
def delta_tile(y1: int, y2: int, z: int, x: int, y: int):
    path = ensure_delta(y1, y2)

    # robust symmetric range cached (fallback -0.3..0.3)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))

    with COGReader(path) as cog:
        img = cog.tile(x, y, z)
        band = img.data[0]
    png = render_png_singleband(band, vmin=vmin, vmax=vmax, cmap_name="coolwarm", nodata=NODATA)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

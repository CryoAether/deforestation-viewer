from __future__ import annotations

import pathlib as pl
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader

from PIL import Image
import io

from .config import COMP_DIR, NODATA
from .delta import ensure_delta
from .color import render_png_singleband
from .raster import robust_range

router = APIRouter()

# Cache a transparent 256x256 tile for out-of-bounds requests
_TRANSPARENT_256: bytes | None = None


def transparent_tile_png(size: int = 256) -> bytes:
    global _TRANSPARENT_256
    if _TRANSPARENT_256 is None:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        _TRANSPARENT_256 = buf.getvalue()
    return _TRANSPARENT_256


def _ndvi_file(year: int) -> pl.Path:
    p = COMP_DIR / f"ndvi_median_{year}.tif"
    if p.exists():
        return p
    p2 = COMP_DIR / f"ndvi_median_{year}.tiff"
    if p2.exists():
        return p2
    raise FileNotFoundError(f"Missing composite for year={year}")


@router.get("/tiles/ndvi/{year}/{z}/{x}/{y}.png")
def ndvi_tile(year: int, z: int, x: int, y: int):
    try:
        path = _ndvi_file(year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        with COGReader(path) as cog:
            img = cog.tile(x, y, z)
            band = img.data[0]
        band = band.astype("float32", copy=False)
        band[img.mask == 0] = np.nan  # (bands, h, w) -> single band
    except TileOutsideBounds:
        return Response(content=transparent_tile_png(), media_type="image/png")
    except Exception as e:
        # Keep errors visible but not a cryptic 500
        raise HTTPException(status_code=500, detail=f"Tile read failed: {e}")

    vmin, vmax = robust_range(str(path), default=(0.2, 0.85))
    png = render_png_singleband(band, vmin=vmin, vmax=vmax, cmap_name="RdYlGn", nodata=NODATA)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/tiles/delta/{y1}/{y2}/{z}/{x}/{y}.png")
def delta_tile(y1: int, y2: int, z: int, x: int, y: int):
    path = ensure_delta(y1, y2)

    # robust symmetric range cached (fallback -0.3..0.3)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))

    try:
        with COGReader(path) as cog:
            img = cog.tile(x, y, z)
            band = img.data[0]
        band = band.astype("float32", copy=False)
        band[img.mask == 0] = np.nan
    except TileOutsideBounds:
        return Response(content=transparent_tile_png(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tile read failed: {e}")

    png = render_png_singleband(band, vmin=vmin, vmax=vmax, cmap_name="coolwarm", nodata=NODATA)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
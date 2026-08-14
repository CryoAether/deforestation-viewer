from __future__ import annotations

from typing import List
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import rasterio
from pyproj import Transformer

from database.connection import get_db
from database.models import RegionOfInterest
from api.config import COMP_DIR
from api.delta import ensure_delta, ndvi_path
from api.raster import robust_range

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
        "bounds": [[south, west], [north, east]],
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
async def health():
    return {"ok": True}

@router.get("/aoi")
async def get_aoi_from_db(db: AsyncSession = Depends(get_db)):
    """Dynamically query PostGIS spatial geometries directly from PostgreSQL."""
    query = select(
        RegionOfInterest.id,
        RegionOfInterest.name,
        RegionOfInterest.description,
        func.ST_AsGeoJSON(RegionOfInterest.geom).label("geojson")
    )
    result = await db.execute(query)
    rows = result.all()
    
    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "id": row.id,
            "properties": {"name": row.name, "description": row.description},
            "geometry": json.loads(row.geojson)
        })
        
    return {"type": "FeatureCollection", "features": features}

@router.get("/bounds/{year}")
async def get_bounds(year: int):
    try:
        p = ndvi_path(year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return bounds_wgs84(str(p))

@router.get("/years")
async def years():
    ys = _years()
    if not ys:
        raise HTTPException(status_code=404, detail=f"No composites found in {COMP_DIR}")
    return {"years": ys}

class DeltaReq(BaseModel):
    from_year: int
    to_year: int

@router.post("/delta")
async def build_delta(req: DeltaReq):
    path = ensure_delta(req.from_year, req.to_year)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))
    return {"path": str(path), "vmin": vmin, "vmax": vmax}
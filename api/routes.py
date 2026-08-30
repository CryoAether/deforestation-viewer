from __future__ import annotations

import asyncio
from typing import List, Tuple, Dict, Any, Optional
import json

from fastapi import APIRouter, HTTPException, Depends
import httpx
import numpy as np
from pydantic import BaseModel
import rasterio
import rasterio.features
from skimage.transform import resize
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pyproj import Transformer
from shapely.geometry import shape

from database.connection import get_db
from database.models import RegionOfInterest
from src.fast_engine import get_fast_year_composite, fast_array_to_png
from .config import COMP_DIR
from .delta import ensure_delta, ndvi_path
from .raster import robust_range

router = APIRouter(prefix="/api")


# =========================
# Schemas
# =========================

class AnalyzeReq(BaseModel):
    town: str
    baseline_year: int = 2020
    target_year: int = 2024


class DeltaReq(BaseModel):
    from_year: int
    to_year: int


# =========================
# Geocoding Helper
# =========================

async def geocode_location(query: str) -> Tuple[str, float, float, Optional[Dict[str, Any]], Optional[List[float]]]:
    headers = {"User-Agent": "DeforestationViewer/2.0 (research; educational)"}
    timeout = httpx.Timeout(10.0, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "polygon_geojson": 1, "limit": 1}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    item = data[0]
                    bb = item.get("boundingbox")
                    raw_bbox = None
                    if bb and len(bb) == 4:
                        raw_bbox = [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]
                    return (
                        item.get("display_name", query),
                        float(item["lat"]),
                        float(item["lon"]),
                        item.get("geojson"),
                        raw_bbox
                    )
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get(
                "https://photon.komoot.io/api/",
                params={"q": query, "limit": 1}
            )
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                if features:
                    feat = features[0]
                    lon, lat = feat["geometry"]["coordinates"]
                    props = feat.get("properties", {})
                    name = props.get("name", query)
                    state = props.get("state", "")
                    country = props.get("country", "")
                    display = ", ".join(filter(None, [name, state, country]))
                    
                    raw_bbox = feat.get("properties", {}).get("extent")
                    if raw_bbox and len(raw_bbox) == 4:
                        raw_bbox = [raw_bbox[0], raw_bbox[3], raw_bbox[2], raw_bbox[1]]
                    return display, float(lat), float(lon), feat.get("geometry"), raw_bbox
    except Exception:
        raise HTTPException(
            status_code=504,
            detail="Geocoding service timed out. Please try again."
        )

    raise HTTPException(
        status_code=404,
        detail=f"Could not locate '{query}'. Try including a state or country."
    )


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


# =========================
# Routes
# =========================

@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/status")
async def status():
    return {"status": "ready", "ok": True}


@router.post("/analyze")
async def analyze_town(req: AnalyzeReq):
    display_name, lat, lon, geom_geojson, raw_bbox = await geocode_location(req.town)

    has_polygon = geom_geojson and geom_geojson.get("type") in ["Polygon", "MultiPolygon"]
    
    if has_polygon:
        try:
            poly_geom = shape(geom_geojson)
            p_minx, p_miny, p_maxx, p_maxy = poly_geom.bounds
            
            span_lon = max(0.04, (p_maxx - p_minx) * 1.20)
            span_lat = max(0.04, (p_maxy - p_miny) * 1.20)
            c_lon = (p_minx + p_maxx) / 2.0
            c_lat = (p_miny + p_maxy) / 2.0
            
            bbox = [
                c_lon - span_lon / 2.0,
                c_lat - span_lat / 2.0,
                c_lon + span_lon / 2.0,
                c_lat + span_lat / 2.0
            ]
        except Exception:
            has_polygon = False

    if not has_polygon and raw_bbox:
        span_lon = max(0.04, (raw_bbox[2] - raw_bbox[0]) * 1.15)
        span_lat = max(0.04, (raw_bbox[3] - raw_bbox[1]) * 1.15)
        c_lon = (raw_bbox[0] + raw_bbox[2]) / 2.0
        c_lat = (raw_bbox[1] + raw_bbox[3]) / 2.0
        bbox = [c_lon - span_lon / 2.0, c_lat - span_lat / 2.0, c_lon + span_lon / 2.0, c_lat + span_lat / 2.0]
    elif not has_polygon:
        delta_lat = 5.0 / 111.0
        delta_lon = 5.0 / (111.0 * np.cos(np.radians(lat)))
        bbox = [lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat]

    lat_dist = abs(bbox[3] - bbox[1]) * 111.0
    lon_dist = abs(bbox[2] - bbox[0]) * 111.0 * np.cos(np.radians(lat))
    area_km2 = max(1.0, lat_dist * lon_dist)

    h, w = 350, 350
    ndvi_2020_task = get_fast_year_composite(bbox, req.baseline_year, shape=(h, w))
    ndvi_2024_task = get_fast_year_composite(bbox, req.target_year, shape=(h, w))
    ndvi_baseline, ndvi_target = await asyncio.gather(ndvi_2020_task, ndvi_2024_task)

    if ndvi_baseline.shape != ndvi_target.shape:
        ndvi_baseline = resize(ndvi_baseline, ndvi_target.shape, order=1, preserve_range=True)

    valid_land = np.isfinite(ndvi_target) & (ndvi_target > 0.08)

    if has_polygon:
        try:
            inv_transform = rasterio.transform.from_bounds(bbox[0], bbox[3], bbox[2], bbox[1], w, h)
            inside_city = rasterio.features.rasterize(
                [(geom_geojson, 1)],
                out_shape=(h, w),
                transform=inv_transform,
                fill=0,
                dtype=np.uint8,
            ).astype(bool)
            
            if np.any(inside_city):
                valid_land = valid_land & inside_city
        except Exception:
            pass

    total_land_pixels = int(np.count_nonzero(valid_land))
    foliage_target = (ndvi_target >= 0.28) & valid_land
    foliage_baseline = (ndvi_baseline >= 0.28) & np.isfinite(ndvi_baseline) & (valid_land if has_polygon else True)

    green_now = int(np.count_nonzero(foliage_target))
    green_prev = int(np.count_nonzero(foliage_baseline))

    greenery_pct = (green_now / max(1, total_land_pixels)) * 100.0

    if green_prev > 50 and green_now > 50:
        canopy_shift = ((green_now - green_prev) / green_prev) * 100.0
    else:
        canopy_shift = 0.0

    return {
        "location_name": display_name,
        "bbox": bbox,
        "greenery_coverage_pct": round(float(greenery_pct), 1),
        "canopy_change_pct": round(float(canopy_shift), 1),
        "total_area_analyzed_km2": round(float(area_km2), 1),
        "images": {
            str(req.baseline_year): fast_array_to_png(ndvi_baseline, bbox, geom_geojson if has_polygon else None),
            str(req.target_year): fast_array_to_png(ndvi_target, bbox, geom_geojson if has_polygon else None),
        }
    }


@router.get("/aoi")
async def get_aoi_from_db(db: AsyncSession = Depends(get_db)):
    try:
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
                "properties": {
                    "name": row.name,
                    "description": row.description
                },
                "geometry": json.loads(row.geojson)
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


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


@router.post("/delta")
async def build_delta(req: DeltaReq):
    path = ensure_delta(req.from_year, req.to_year)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))
    return {"path": str(path), "vmin": vmin, "vmax": vmax}
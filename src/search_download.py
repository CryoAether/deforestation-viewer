# src/search_download.py
from __future__ import annotations

from datetime import date, timedelta
import json
import os
import pathlib as pl
from typing import Dict, List, Tuple

import numpy as np
import geopandas as gpd
import rioxarray  # registers .rio accessor
import rasterio

from pystac_client import Client
import planetary_computer as pc
import stackstac as st

import dask
from dask.diagnostics import ProgressBar
from tqdm.auto import tqdm

from ndvi import compute_ndvi_mixed, mask_clouds_mixed


# =========================
# Config
# =========================
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Use NaN as fill for float32 stackstac arrays to avoid dtype/fill conflicts
FILL_VALUE = np.nan

# How many best scenes (per year) to keep for compositing
BEST_K = int(os.getenv("BEST_K", "8"))

# Seasonal window controls
WINDOW_WEEKS = int(os.getenv("WINDOW_WEEKS", "8"))
WINDOW_START_MONTH = int(os.getenv("WINDOW_START_MONTH", "7"))
WINDOW_START_DAY = int(os.getenv("WINDOW_START_DAY", "1"))

# Day-by-day search step (1 = daily)
DAY_STEP = int(os.getenv("DAY_STEP", "1"))

# Candidate scene search per day (limit results pulled from STAC)
PER_DAY_LIMIT = int(os.getenv("PER_DAY_LIMIT", "50"))

# Scene-level cloud cap for initial STAC filtering (still useful, but not relied on)
MAX_CLOUD = int(os.getenv("MAX_CLOUD", "80"))

# Output
OUTDIR = pl.Path(os.getenv("OUTDIR", "data/composites"))
OUTDIR.mkdir(parents=True, exist_ok=True)

AOI_PATH = os.getenv("AOI_PATH", "data/aoi/roi.geojson")

# Dask
dask.config.set(scheduler="threads", num_workers=int(os.getenv("DASK_WORKERS", "6")))
ProgressBar().register()


# =========================
# Dataset registry
# =========================
DATASETS: Dict[str, dict] = {
    "S2": {
        "years": (2016, 2100),
        "collection": "sentinel-2-l2a",
        "assets": {"red": "B04", "nir": "B08", "qa": "SCL"},
        "mask": "s2",
        "scale": 1.0 / 10000.0,
        "offset": 0.0,
        "resolution": 10,
    },
    "L89": {
        "years": (2013, 2100),
        "collection": "landsat-c2-l2",
        "assets": {"red": "SR_B4", "nir": "SR_B5", "qa": "QA_PIXEL"},
        "mask": "landsat",
        "scale": 2.75e-05,
        "offset": -0.2,
        "resolution": 30,
    },
    "L57": {
        "years": (1985, 2012),
        "collection": "landsat-c2-l2",
        "assets": {"red": "SR_B3", "nir": "SR_B4", "qa": "QA_PIXEL"},
        "mask": "landsat",
        "scale": 2.75e-05,
        "offset": -0.2,
        "resolution": 30,
    },
}


def select_dataset(year: int) -> Tuple[str, dict]:
    for key, cfg in DATASETS.items():
        y0, y1 = cfg["years"]
        if y0 <= year <= y1:
            return key, cfg
    raise ValueError(f"No dataset configured for year {year}")


def seasonal_window(year: int, start_month: int, start_day: int, weeks: int) -> Tuple[date, date]:
    start = date(year, start_month, start_day)
    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    return start, end


def load_aoi(path: str = AOI_PATH) -> Tuple[gpd.GeoDataFrame, dict]:
    gdf = gpd.read_file(path).to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())


def _utm_epsg_for_aoi(aoi_gdf: gpd.GeoDataFrame) -> int:
    utm = aoi_gdf.estimate_utm_crs()
    epsg = utm.to_epsg() if utm else 4326
    return int(epsg)


def _aoi_bounds_in_epsg(aoi_gdf: gpd.GeoDataFrame, epsg: int) -> Tuple[float, float, float, float]:
    a = aoi_gdf.to_crs(epsg)
    minx, miny, maxx, maxy = a.total_bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def _do_search_day(
    client: Client,
    collection: str,
    aoi_geojson: dict,
    day: date,
    max_cloud: int,
) -> List:
    # Search one day at a time (ISO interval)
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()

    query = {"eo:cloud_cover": {"lt": max_cloud}} if max_cloud is not None else None

    search = client.search(
        collections=[collection],
        intersects=aoi_geojson["features"][0]["geometry"],
        datetime=f"{start}/{end}",
        query=query,
        limit=PER_DAY_LIMIT,
    )
    items = list(search.items())

    # Fallback: if none found under cloud cap, retry without cloud filter
    if not items and max_cloud is not None:
        search = client.search(
            collections=[collection],
            intersects=aoi_geojson["features"][0]["geometry"],
            datetime=f"{start}/{end}",
            limit=PER_DAY_LIMIT,
        )
        items = list(search.items())

    return [pc.sign(it) for it in items]


def _stack_single_item(
    item,
    aoi_gdf: gpd.GeoDataFrame,
    epsg: int,
    bounds: Tuple[float, float, float, float],
    cfg: dict,
):
    assets = [cfg["assets"]["red"], cfg["assets"]["nir"], cfg["assets"]["qa"]]
    arr = st.stack(
        [item],
        assets=assets,
        epsg=epsg,
        bounds=bounds,
        resolution=cfg["resolution"],
        chunksize=512,
        dtype="float32",
        fill_value=FILL_VALUE,  # NaN fill
        rescale=False,
    )
    arr = arr.chunk({"time": 1, "y": 512, "x": 512})
    if not arr.rio.crs:
        arr = arr.rio.write_crs(epsg)
    return arr  # dims: time, band, y, x


def _scene_clear_score(item, aoi_gdf: gpd.GeoDataFrame, epsg: int, bounds, cfg: dict) -> Tuple[float, float, float]:
    """
    Score a scene by clear fraction over AOI using QA mask.
    Returns: (score, clear_frac, mean_ndvi)
    Higher score is better.
    """
    arr = _stack_single_item(item, aoi_gdf, epsg, bounds, cfg)

    # Band labels are asset names in stackstac ("B04", "B08", "SCL" ...)
    red = arr.sel(band=cfg["assets"]["red"]).astype("float32")
    nir = arr.sel(band=cfg["assets"]["nir"]).astype("float32")
    qa = arr.sel(band=cfg["assets"]["qa"])

    # Compute NDVI then apply QA mask
    ndvi = compute_ndvi_mixed(red, nir, cfg)
    ndvi_m = mask_clouds_mixed(qa, ndvi, cfg)

    # Evaluate AOI clarity (how much survived masking)
    valid = np.isfinite(ndvi_m)
    clear_frac = float(valid.mean().compute())
    mean_ndvi = float(ndvi_m.where(valid).mean().compute())

    # Also include scene-level cloud cover as weak tie-breaker
    cloud = item.properties.get("eo:cloud_cover", None)
    try:
        cloud = float(cloud) if cloud is not None else 100.0
    except Exception:
        cloud = 100.0

    # Score: prioritize AOI clarity heavily, then penalize cloud a little
    score = clear_frac - 0.002 * cloud
    return score, clear_frac, mean_ndvi


def pick_best_scenes_for_year(
    year: int,
    aoi_gdf: gpd.GeoDataFrame,
    aoi_geojson: dict,
    cfg: dict,
) -> List:
    client = Client.open(CATALOG)

    start, end = seasonal_window(year, WINDOW_START_MONTH, WINDOW_START_DAY, WINDOW_WEEKS)
    epsg = _utm_epsg_for_aoi(aoi_gdf)
    bounds = _aoi_bounds_in_epsg(aoi_gdf, epsg)

    # Gather candidates day-by-day
    candidates = []
    d = start
    print(f"[{year}] Day-by-day candidate search: {start} → {end} (MAX_CLOUD={MAX_CLOUD})")
    while d <= end:
        items = _do_search_day(client, cfg["collection"], aoi_geojson, d, MAX_CLOUD)
        candidates.extend(items)
        d += timedelta(days=DAY_STEP)

    if not candidates:
        return []

    # Deduplicate by id
    seen = set()
    uniq = []
    for it in candidates:
        if it.id not in seen:
            seen.add(it.id)
            uniq.append(it)

    print(f"[{year}] Candidates: {len(uniq)} (unique)")

    # Score each scene by AOI-clear fraction
    scored = []
    for it in tqdm(uniq, desc=f"[{year}] Scoring scenes", leave=False):
        try:
            score, clear_frac, mean_ndvi = _scene_clear_score(it, aoi_gdf, epsg, bounds, cfg)
            scored.append((score, clear_frac, mean_ndvi, it))
        except Exception as e:
            # Skip broken scenes rather than killing the whole year
            print(f"[{year}] Skip {it.id}: scoring failed ({e})")

    if not scored:
        return []

    scored.sort(key=lambda t: t[0], reverse=True)
    best = scored[:BEST_K]

    print(f"[{year}] Best {len(best)} scenes (ranked by AOI clarity):")
    for i, (score, cf, mndvi, it) in enumerate(best, 1):
        cloud = it.properties.get("eo:cloud_cover", None)
        dt = getattr(it, "datetime", None)
        print(f"  {i:02d}. score={score:.3f} clear={cf:.3f} mean_ndvi={mndvi:.3f} cloud={cloud} date={dt} id={it.id}")

    return [t[3] for t in best]


def build_composite_from_scenes(
    items: List,
    aoi_gdf: gpd.GeoDataFrame,
    cfg: dict,
    out_tif: pl.Path,
    reducer: str,
):
    epsg = _utm_epsg_for_aoi(aoi_gdf)
    bounds = _aoi_bounds_in_epsg(aoi_gdf, epsg)

    assets = [cfg["assets"]["red"], cfg["assets"]["nir"], cfg["assets"]["qa"]]
    stack = st.stack(
        items,
        assets=assets,
        epsg=epsg,
        bounds=bounds,
        resolution=cfg["resolution"],
        chunksize=768,
        dtype="float32",
        fill_value=FILL_VALUE,   # NaN fill
        rescale=False,
    ).chunk({"time": 1, "y": 512, "x": 512})

    if not stack.rio.crs:
        stack = stack.rio.write_crs(epsg)

    red = stack.sel(band=cfg["assets"]["red"]).astype("float32")
    nir = stack.sel(band=cfg["assets"]["nir"]).astype("float32")
    qa = stack.sel(band=cfg["assets"]["qa"])

    ndvi = compute_ndvi_mixed(red, nir, cfg)
    ndvi_m = mask_clouds_mixed(qa, ndvi, cfg)

    reducer = (reducer or "median").lower()
    if reducer == "median":
        comp = ndvi_m.median(dim="time", skipna=True)
    elif reducer == "max":
        comp = ndvi_m.max(dim="time", skipna=True)
    elif reducer == "p95":
        comp = ndvi_m.quantile(0.95, dim="time", skipna=True).squeeze(drop=True)
    else:
        print(f"Unknown REDUCER={reducer}, using median.")
        comp = ndvi_m.median(dim="time", skipna=True)

    comp = comp.where(np.isfinite(comp))

    # Ensure CRS/transform before writing
    # Use stack’s transform for write (rioxarray needs one)
    # stackstac keeps georeferencing but this makes it explicit.
    comp.rio.write_crs(epsg, inplace=True)

    # Use rasterio to build transform from bounds + shape + resolution
    # This avoids “wrong transform” drift.
    res = cfg["resolution"]
    minx, miny, maxx, maxy = bounds
    height, width = int(comp.sizes["y"]), int(comp.sizes["x"])
    transform = rasterio.transform.from_origin(minx, maxy, res, res)
    comp.rio.write_transform(transform, inplace=True)

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    comp.rio.to_raster(
        out_tif,
        driver="COG",
        compress="DEFLATE",
        dtype="float32",
        nodata=None,  # keep NaN as nodata behavior
    )


def main():
    aoi_gdf, aoi_geojson = load_aoi(AOI_PATH)

    # Choose years. Default to just 2024 unless you change it.
    years = [int(os.getenv("YEAR", "2024"))]

    for y in years:
        ds_name, cfg = select_dataset(y)
        print(f"\n[{y}] Dataset: {ds_name} / {cfg['collection']}")

        best_items = pick_best_scenes_for_year(y, aoi_gdf, aoi_geojson, cfg)
        if not best_items:
            print(f"[{y}] No usable scenes found; skipping.")
            continue

        reducer = os.getenv("REDUCER", "median")
        out_tif = OUTDIR / f"ndvi_median_{y}.tif"

        print(f"[{y}] Building composite from best scenes → {out_tif} (REDUCER={reducer})")
        build_composite_from_scenes(best_items, aoi_gdf, cfg, out_tif, reducer=reducer)

        print(f"[{y}] Saved: {out_tif}")

    print("Done.")


if __name__ == "__main__":
    main()
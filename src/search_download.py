# src/search_download.py
from __future__ import annotations

from datetime import date, timedelta
import json
import os
import pathlib as pl
import sys
from typing import Dict, List, Tuple

import numpy as np
import geopandas as gpd
import rioxarray  
import rasterio

from pystac_client import Client
import planetary_computer as pc
import stackstac as st

# Handle imports when executing either as module or standalone script
try:
    from src.dask_engine import init_dask_cluster
    from src.ndvi import compute_ndvi_mixed, mask_clouds_mixed
except ImportError:
    sys.path.append(str(pl.Path(__file__).resolve().parent))
    from dask_engine import init_dask_cluster
    from ndvi import compute_ndvi_mixed, mask_clouds_mixed


# =========================
# Config
# =========================
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"

WINDOW_WEEKS = int(os.getenv("WINDOW_WEEKS", "16"))
WINDOW_START_MONTH = int(os.getenv("WINDOW_START_MONTH", "8"))
WINDOW_START_DAY = int(os.getenv("WINDOW_START_DAY", "1"))

MAX_CLOUD = int(os.getenv("MAX_CLOUD", "100"))
MAX_SCENES_TO_STACK = int(os.getenv("MAX_SCENES_TO_STACK", "70"))

OUTDIR = pl.Path(os.getenv("OUTDIR", "data/composites"))
OUTDIR.mkdir(parents=True, exist_ok=True)

AOI_PATH = os.getenv("AOI_PATH", "data/aoi/roi_barren.geojson")

DASK_WORKERS = int(os.getenv("DASK_WORKERS", "4"))
DASK_THREADS = int(os.getenv("DASK_THREADS", "2"))


# =========================
# Dataset registry
# =========================
# Uses Planetary Computer canonical STAC asset keys
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
        "years": (2013, 2015),
        "collection": "landsat-c2-l2",
        "assets": {"red": "red", "nir": "nir08", "qa": "qa_pixel"},
        "mask": "landsat",
        "scale": 2.75e-05,
        "offset": -0.2,
        "resolution": 30,
    },
    "L57": {
        "years": (1985, 2012),
        "collection": "landsat-c2-l2",
        "assets": {"red": "red", "nir": "nir08", "qa": "qa_pixel"},
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


def seasonal_window(year: int, start_month: int, start_day: int, weeks: int) -> Tuple[str, str]:
    start = date(year, start_month, start_day)
    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


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


def gather_scenes_for_year(
    year: int,
    aoi_geojson: dict,
    cfg: dict,
) -> List:
    client = Client.open(CATALOG)
    start, end = seasonal_window(year, WINDOW_START_MONTH, WINDOW_START_DAY, WINDOW_WEEKS)
    
    print(f"[{year}] Searching {cfg['collection']} from {start} to {end} (Max Cloud: {MAX_CLOUD}%)")
    
    query = {"eo:cloud_cover": {"lt": MAX_CLOUD}} if MAX_CLOUD < 100 else None
    
    search = client.search(
        collections=[cfg["collection"]],
        intersects=aoi_geojson["features"][0]["geometry"],
        datetime=f"{start}/{end}",
        query=query,
    )
    
    items = list(search.items())
    
    # De-duplicate items
    seen = set()
    uniq = []
    for it in items:
        if it.id not in seen:
            seen.add(it.id)
            uniq.append(it)
            
    # Landsat 7 SLC-off striping mitigation
    if cfg["collection"] == "landsat-c2-l2" and 2003 <= year <= 2012:
        l5_items = [it for it in uniq if "LT05" in it.id]
        if len(l5_items) >= 5: 
            uniq = l5_items
            print(f"[{year}] Prioritizing Landsat 5 to avoid SLC-off stripes. Dropped Landsat 7.")
            
    uniq.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
    final_items = uniq[:MAX_SCENES_TO_STACK]
    
    print(f"[{year}] Found {len(uniq)} scenes. Stacking top {len(final_items)}.")
    return [pc.sign(it) for it in final_items]


def build_composite_from_scenes(
    items: List,
    aoi_gdf: gpd.GeoDataFrame,
    cfg: dict,
    out_tif: pl.Path,
):
    epsg = _utm_epsg_for_aoi(aoi_gdf)
    bounds = _aoi_bounds_in_epsg(aoi_gdf, epsg)

    red_asset = cfg["assets"]["red"]
    nir_asset = cfg["assets"]["nir"]
    qa_asset = cfg["assets"]["qa"]
    assets = [red_asset, nir_asset, qa_asset]
    
    # Construct lazy 4D Dask array stack
    stack = st.stack(
        items,
        assets=assets,
        epsg=epsg,
        bounds=bounds,
        resolution=cfg["resolution"],
        chunksize=1024, 
        dtype="float32",
        fill_value=np.float32("nan"), 
        rescale=False,
    )

    if not stack.rio.crs:
        stack = stack.rio.write_crs(epsg)

    # 1. Select the spectral bands
    red = stack.sel(band=red_asset)
    nir = stack.sel(band=nir_asset)
    qa = stack.sel(band=qa_asset)

    # Strip metadata string coordinates that cause arithmetic conversion errors
    keep_coords = ["time", "y", "x", "spatial_ref"]
    red = red.drop_vars([c for c in red.coords if c not in keep_coords], errors="ignore").astype("float32")
    nir = nir.drop_vars([c for c in nir.coords if c not in keep_coords], errors="ignore").astype("float32")
    qa = qa.drop_vars([c for c in qa.coords if c not in keep_coords], errors="ignore")

    print(f"  -> Building Dask task graph for NDVI & QA masking across {len(items)} scenes...")
    ndvi = compute_ndvi_mixed(red, nir, cfg)
    ndvi_m = mask_clouds_mixed(qa, ndvi, cfg)

    print("  -> Dispatching parallel temporal median reduction to Dask cluster...")
    comp_lazy = ndvi_m.median(dim="time", skipna=True)
    comp_lazy = comp_lazy.where(np.isfinite(comp_lazy))

    # Execute computation graph
    comp = comp_lazy.compute()

    comp.rio.write_crs(epsg, inplace=True)
    res = cfg["resolution"]
    minx, miny, maxx, maxy = bounds
    transform = rasterio.transform.from_origin(minx, maxy, res, res)
    comp.rio.write_transform(transform, inplace=True)

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    print(f"  -> Writing Cloud-Optimized GeoTIFF (COG) to {out_tif.name}...")
    comp.rio.to_raster(
        out_tif,
        driver="COG",
        compress="DEFLATE",
        dtype="float32",
        nodata=None,
    )


def main():
    client = init_dask_cluster(n_workers=DASK_WORKERS, threads_per_worker=DASK_THREADS)

    try:
        aoi_gdf, aoi_geojson = load_aoi(AOI_PATH)

        start_year = int(os.getenv("START_YEAR", "2000"))
        end_year = int(os.getenv("END_YEAR", "2025"))
        years = range(start_year, end_year + 1)

        for y in years:
            try:
                ds_name, cfg = select_dataset(y)
                best_items = gather_scenes_for_year(y, aoi_geojson, cfg)
                
                if not best_items:
                    print(f"[{y}] No usable scenes found; skipping.\n")
                    continue

                out_tif = OUTDIR / f"ndvi_median_{y}.tif"
                build_composite_from_scenes(best_items, aoi_gdf, cfg, out_tif)
                print(f"[{y}] Success: {out_tif}\n")
                
            except Exception as e:
                print(f"[{y}] FAILED: {str(e)}\n")

        print("Pipeline Complete.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
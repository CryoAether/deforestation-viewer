# src/search_download.py
from datetime import date, timedelta
import json
import os
import pathlib as pl
import numpy as np
import geopandas as gpd
import rioxarray  # registers .rio accessor
from pystac_client import Client
import planetary_computer as pc
import stackstac as st
import dask
from dask.diagnostics import ProgressBar
from tqdm.auto import tqdm
from ndvi import compute_ndvi_mixed, mask_clouds_mixed

# ---- Dataset registry (year → collection/bands/mask) ----
DATASETS = {
    "S2": {
        "years": (2016, 2100),
        "collection": "sentinel-2-l2a",
        "assets": {"red": "B04", "nir": "B08", "qa": "SCL"},
        "mask": "s2",
        "scale": 1.0 / 10000.0,
        "offset": 0.0,
    },
    "L89": {
        "years": (2013, 2100),
        "collection": "landsat-c2-l2",
        "platform": ["LANDSAT_8", "LANDSAT_9"],
        "assets": {"red": "SR_B4", "nir": "SR_B5", "qa": "QA_PIXEL"},
        "mask": "landsat",
        "scale": 2.75e-05,
        "offset": -0.2,
    },
    "L57": {
        "years": (1985, 2012),
        "collection": "landsat-c2-l2",
        "platform": ["LANDSAT_5", "LANDSAT_7"],
        "assets": {"red": "SR_B3", "nir": "SR_B4", "qa": "QA_PIXEL"},
        "mask": "landsat",
        "scale": 2.75e-05,
        "offset": -0.2,
    },
}

def select_dataset(year: int):
    for key, cfg in DATASETS.items():
        y0, y1 = cfg["years"]
        if y0 <= year <= y1:
            return key, cfg
    raise ValueError(f"No dataset configured for year {year}")

dask.config.set(scheduler="threads", num_workers=6)
ProgressBar().register()

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"

# throttle: set MAX_SCENES=None to process all
_env = os.getenv("MAX_SCENES", "none").lower()  # Testing phase, low value for quick results
WINDOW_WEEKS = int(os.getenv("WINDOW_WEEKS", "8"))
WINDOW_START_MONTH = int(os.getenv("WINDOW_START_MONTH", "1"))  # 7 = July
WINDOW_START_DAY = int(os.getenv("WINDOW_START_DAY", "1"))
_env_norm = (_env or "").strip().lower()
MAX_SCENES = None if _env_norm in ("none", "") else int(_env_norm)

def resolve_landsat_assets(first_assets: set, want: str, ds_key: str) -> str:
    """
    Choose the actual asset key for Landsat based on what the item really has.
    `want` is 'red' | 'nir' | 'qa'. `ds_key` is 'L57' or 'L89'.
    """
    # Most-preferred → fallback
    if want == "red":
        candidates = ["SR_B3", "SR_B4", "red", "B3", "B4"]
    elif want == "nir":
        candidates = ["SR_B4", "SR_B5", "nir08", "nir", "B4", "B5"]
    elif want == "qa":
        candidates = ["QA_PIXEL", "qa_pixel", "cloud_qa", "pixel_qa"]
    else:
        raise ValueError(f"Unknown asset kind: {want}")

    for c in candidates:
        if c in first_assets:
            return c
    raise RuntimeError(f"No suitable asset for {want}. Item assets={sorted(first_assets)}")

def seasonal_window(year: int, start_month: int = 7, start_day: int = 1, weeks: int = 8):
    start = date(year, start_month, start_day)
    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    return (start, end)

def load_aoi(path="data/aoi/roi.geojson"):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())

def search_items(aoi_geojson, start, end, max_cloud=25, cfg=None):
    if cfg is None:
        raise ValueError("search_items requires cfg from select_dataset(year)")

    client = Client.open(CATALOG)

    # build query (keep cloud cap), but skip platform filter (too brittle on MPC)
    query = {}
    if max_cloud is not None:
        query["eo:cloud_cover"] = {"lt": max_cloud}

    def _do_search(q):
        return client.search(
            collections=[cfg["collection"]],
            intersects=aoi_geojson["features"][0]["geometry"],
            datetime=f"{start}/{end}",
            query=q if q else None,
        )

    # first attempt
    items = list(_do_search(query).items())

    # fallback: if none found, retry without cloud filter
    if not items and "eo:cloud_cover" in query:
        print(f"No items with cloud<{max_cloud}. Retrying with no cloud filter…")
        items = list(_do_search({}).items())

    # sign for MPC
    items = [pc.sign(it) for it in items]

    # --- Dedup best (lowest cloud) per tile/day ---
    by_key = {}
    for it in items:
        if cfg["mask"] == "s2":
            tile_id = it.properties.get("s2:mgrs_tile")
        else:
            p = it.properties.get("landsat:wrs_path")
            r = it.properties.get("landsat:wrs_row")

            def _pad3(x):
                try:
                    return f"{int(x):03d}"
                except Exception:
                    return str(x)

            tile_id = (
                f"P{_pad3(p)}R{_pad3(r)}" if (p is not None and r is not None) else "LTILE"
            )
        day = it.datetime.date()
        key = (tile_id, day)
        if key not in by_key or it.properties["eo:cloud_cover"] < by_key[key].properties["eo:cloud_cover"]:
            by_key[key] = it

    items = list(by_key.values())
    print(f"After best-per-day-per-tile filter: {len(items)} scenes")

    # --- Optional: date subsample per tile ---
    items.sort(key=lambda it: it.datetime)
    filtered, last_for_tile = [], {}
    day_gap = int(os.getenv("DAY_GAP", "10"))
    if day_gap <= 0:
        print("Subsample disabled (DAY_GAP<=0); keeping all best-per-day-per-tile scenes.")
        return items
    for it in items:
        if cfg["mask"] == "s2":
            tile_id = it.properties.get("s2:mgrs_tile")
        else:
            p = it.properties.get("landsat:wrs_path")
            r = it.properties.get("landsat:wrs_row")

            def _pad3(x):
                try:
                    return f"{int(x):03d}"
                except Exception:
                    return str(x)

            tile_id = (
                f"P{_pad3(p)}R{_pad3(r)}" if (p is not None and r is not None) else "LTILE"
            )

        d = it.datetime.date()
        if tile_id not in last_for_tile or (d - last_for_tile[tile_id]).days >= day_gap:
            filtered.append(it)
            last_for_tile[tile_id] = d

    print(f"After {day_gap}-day subsample: {len(filtered)} scenes")
    return filtered

def stack_for_year(items, aoi_gdf, cfg, resolution=30):
    # Decide bands by dataset
    bands = cfg.get("_resolved_assets", (cfg["assets"]["red"], cfg["assets"]["nir"], cfg["assets"]["qa"]))

    utm = aoi_gdf.estimate_utm_crs()
    target_epsg = utm.to_epsg() if utm else 4326

    aoi_in_target = aoi_gdf.to_crs(target_epsg)
    minx, miny, maxx, maxy = aoi_in_target.total_bounds

    stack = st.stack(
        items,
        assets=list(bands),
        epsg=target_epsg,
        bounds=(minx, miny, maxx, maxy),
        resolution=resolution,
        chunksize=768,
        dtype="float64", 
        fill_value=0,
        rescale=False,    # we’ll apply scale/offset explicitly
    )
    stack = stack.chunk({"time": 1, "y": 512, "x": 512})
    if not stack.rio.crs:
        try:
            stack = stack.rio.write_crs(target_epsg)
        except Exception as e:
            print(f"Warning: unable to write CRS ({target_epsg}): {e}")
    return stack  # dims: time, band, y, x

def main():
    aoi_gdf, aoi_geojson = load_aoi("data/aoi/roi.geojson")
    # save NDVI composites under data/composites/ (what your app expects)
    outdir = pl.Path("data/composites")
    outdir.mkdir(parents=True, exist_ok=True)
    years = list(range(1985, 2025))

    #years = [1995]  # : 2020, 2021, 2022, 2023, 2024
    for y in tqdm(years, desc="Years"):
        ds_name, cfg = select_dataset(y)
        print(f"[{y}] Using dataset {ds_name}: {cfg['collection']}")

        # Compute seasonal window first, then search
        start, end = seasonal_window(
            y,
            start_month=WINDOW_START_MONTH,
            start_day=WINDOW_START_DAY,
            weeks=WINDOW_WEEKS,
        )

        max_cloud = int(os.getenv("MAX_CLOUD", "80"))
        print(f"[{y}] Searching items {start} → {end} (cloud<{max_cloud}%) …")
        items = search_items(aoi_geojson, start, end, max_cloud=max_cloud, cfg=cfg)
        print(f" [{y}] Found {len(items)} scenes")
        if not items:
            print(f"No scenes for {y}; skipping.")
            continue

        if isinstance(MAX_SCENES, int) and MAX_SCENES > 0 and len(items) > MAX_SCENES:
            items = items[:MAX_SCENES]
            print(f"Throttling to first {MAX_SCENES} scenes for speed…")

        # --- Preflight: inspect first item and resolve real asset keys ---
        first = items[0]
        item_assets = set(first.assets.keys())

        # Resolve actual asset keys based on dataset
        if ds_name in ("L57", "L89"):  # Landsat
            red_key = resolve_landsat_assets(item_assets, "red", ds_name)
            nir_key = resolve_landsat_assets(item_assets, "nir", ds_name)
            qa_key  = resolve_landsat_assets(item_assets, "qa",  ds_name)
        else:  # Sentinel-2 (usually stable)
            red_key, nir_key, qa_key = cfg["assets"]["red"], cfg["assets"]["nir"], cfg["assets"]["qa"]

        # Build the stack using resolved asset keys
        print(f"[{y}] Building stack at 30m and clipping to AOI …")
        stack = stack_for_year(items, aoi_gdf, cfg | {"_resolved_assets": (red_key, nir_key, qa_key)}, resolution=30)
        print(f"[{y}] Stack ready: {tuple(stack.sizes.get(k) for k in ['time','y','x'])} (time, y, x)")

        if "band" not in stack.dims and "bands" not in stack.dims:
            print(f"[{y}] No 'band' dimension found; skipping year.")
            continue
        bdim = "band" if "band" in stack.dims else "bands"

        if stack.sizes.get(bdim, 0) == 0:
            print(f"[{y}] Stack has 0 bands — likely no valid imagery overlaps AOI. Skipping year.")
            continue

        asset_names = [red_key, nir_key, qa_key]
        if (
            (bdim not in stack.coords)
            or (stack.coords[bdim].dtype.kind not in ("U", "O"))
            or (stack.coords[bdim].size != 3)
        ):
            stack = stack.assign_coords({bdim: np.array(asset_names, dtype=object)})
            print(f"[{y}] Relabeled band coord -> {asset_names}")

        # Select dataset-appropriate bands (keep QA native)
        red = stack.sel({bdim: red_key}).astype("float32")
        nir = stack.sel({bdim: nir_key}).astype("float32")
        qa  = stack.sel({bdim: qa_key})

        # Treat sensor zeros as missing so they don't pollute NDVI
        red = red.where(red != 0)
        nir = nir.where(nir != 0)

        print(f"[{y}] Computing NDVI + cloud/snow/water mask …")
        ndvi_t = compute_ndvi_mixed(red, nir, cfg)           # applies per-dataset scale/offset safely
        ndvi_t = mask_clouds_mixed(qa, ndvi_t, cfg)          # S2 SCL vs Landsat QA_PIXEL handled here

        print(f"[{y}] Reducing to seasonal composite (max over time) …")
        ndvi_t = ndvi_t.chunk({"time": 1, "y": 1024, "x": 1024})
        ndvi_med = ndvi_t.max(dim="time", skipna=True)
        ndvi_med = ndvi_med.where(np.isfinite(ndvi_med))

        out_tif = outdir / f"ndvi_median_{y}.tif"
        crs = nir.rio.crs or stack.rio.crs or aoi_gdf.estimate_utm_crs()
        ndvi_med.rio.write_crs(crs, inplace=True)
        ndvi_med.rio.write_transform(nir.rio.transform(), inplace=True)

        print(f"[{y}] Writing COG → {out_tif} …")
        ndvi_med.rio.to_raster(out_tif, driver="COG", compress="DEFLATE", dtype="float32")
        print(f"Saved {out_tif}")

    print("Done.")

if __name__ == "__main__":
    main()
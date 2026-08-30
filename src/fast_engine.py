from __future__ import annotations
import asyncio
import io
import base64
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image
from pystac_client import Client
import planetary_computer as pc
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
import rasterio.features
import cv2
from pyproj import Transformer

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "100000000",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "CPL_VSIL_CURL_TIMEOUT": "10",
}

def read_band_window(url: str, min_lon: float, min_lat: float, max_lon: float, max_lat: float, target_shape=(350, 350)) -> np.ndarray:
    try:
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(url) as src:
                tfm = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                minx, miny = tfm.transform(min_lon, min_lat)
                maxx, maxy = tfm.transform(max_lon, max_lat)

                # Ensure min/max orientation
                left, right = min(minx, maxx), max(minx, maxx)
                bottom, top = min(miny, maxy), max(miny, maxy)

                # Check for overlap with dataset bounds
                if right <= src.bounds.left or left >= src.bounds.right or top <= src.bounds.bottom or bottom >= src.bounds.top:
                    return np.full(target_shape, np.nan, dtype=np.float32)

                window = from_bounds(left, bottom, right, top, src.transform)
                arr = src.read(
                    1,
                    window=window,
                    out_shape=target_shape,
                    resampling=Resampling.nearest,
                    fill_value=np.nan,
                    boundless=True
                )
                return arr.astype(np.float32)
    except Exception:
        return np.full(target_shape, np.nan, dtype=np.float32)

def process_single_scene(item_dict: dict, bbox: list[float], year: int, shape=(350, 350)) -> np.ndarray:
    min_lon, min_lat, max_lon, max_lat = bbox
    b4_url = item_dict["assets"]["B04"]["href"]
    b8_url = item_dict["assets"]["B08"]["href"]
    scl_url = item_dict["assets"]["SCL"]["href"]

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_red = ex.submit(read_band_window, b4_url, min_lon, min_lat, max_lon, max_lat, shape)
        f_nir = ex.submit(read_band_window, b8_url, min_lon, min_lat, max_lon, max_lat, shape)
        f_scl = ex.submit(read_band_window, scl_url, min_lon, min_lat, max_lon, max_lat, shape)

        red = f_red.result()
        nir = f_nir.result()
        scl = f_scl.result()

    if year >= 2022:
        red = np.clip(red - 1000.0, 0, None)
        nir = np.clip(nir - 1000.0, 0, None)

    red = red * 0.0001
    nir = nir * 0.0001

    ndvi = (nir - red) / (nir + red + 1e-6)

    is_water = np.isnan(scl) | (scl == 6) | (nir < 0.05)
    is_cloud = np.isin(scl, [0, 1, 9, 10, 11])
    
    ndvi[is_water | is_cloud | np.isnan(ndvi)] = np.nan
    return ndvi

async def get_fast_year_composite(bbox: list[float], year: int, shape=(350, 350)) -> np.ndarray:
    loop = asyncio.get_event_loop()

    def _search():
        client = Client.open(CATALOG)
        search = client.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=f"{year}-05-01/{year}-09-30",
            query={"eo:cloud_cover": {"lt": 35}},
        )
        items = list(search.items())
        seen = set()
        uniq = []
        for it in items:
            if it.id not in seen:
                seen.add(it.id)
                uniq.append(it)
                
        uniq.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
        return uniq[:5]

    items = await loop.run_in_executor(None, _search)
    if not items:
        return np.full(shape, np.nan, dtype=np.float32)

    signed_items = await loop.run_in_executor(
        None, lambda: [pc.sign(it).to_dict() for it in items]
    )

    def _run_scenes():
        with ThreadPoolExecutor(max_workers=min(12, len(signed_items) * 3)) as pool:
            futures = [
                pool.submit(process_single_scene, item, bbox, year, shape)
                for item in signed_items
            ]
            arrays = [f.result() for f in futures]
            
        stacked = np.stack(arrays, axis=0)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            return np.nanmax(stacked, axis=0)

    return await loop.run_in_executor(None, _run_scenes)

def fast_array_to_png(arr: np.ndarray, bbox: list[float] | None = None, geom_geojson: dict | None = None) -> str:
    h, w = arr.shape
    
    # 1. Base palette
    rgba = np.full((h, w, 4), [238, 235, 227, 255], dtype=np.uint8)
    
    # Transparent water/nodata
    water_mask = np.isnan(arr) | (arr < 0.08)
    rgba[water_mask] = [0, 0, 0, 0]
    
    # Vegetation color gradient
    veg_mask = np.isfinite(arr) & (arr >= 0.28)
    if np.any(veg_mask):
        norm = np.clip((arr[veg_mask] - 0.28) / (0.75 - 0.28), 0.0, 1.0)
        r = (104 - (104 - 25) * norm).astype(np.uint8)
        g = (187 - (187 - 78) * norm).astype(np.uint8)
        b = (89 - (89 - 40) * norm).astype(np.uint8)
        rgba[veg_mask, 0] = r
        rgba[veg_mask, 1] = g
        rgba[veg_mask, 2] = b
        rgba[veg_mask, 3] = 255

    # 2. Polygon Masking & Vibrant Outline
    if geom_geojson and bbox and geom_geojson.get("type") in ["Polygon", "MultiPolygon"]:
        try:
            min_lon, min_lat, max_lon, max_lat = bbox
            inv_transform = rasterio.transform.from_bounds(min_lon, max_lat, max_lon, min_lat, w, h)

            inside_mask = rasterio.features.rasterize(
                [(geom_geojson, 1)],
                out_shape=(h, w),
                transform=inv_transform,
                fill=0,
                dtype=np.uint8,
            ).astype(bool)

            inside_count = np.count_nonzero(inside_mask)
            if 0.02 * (h * w) < inside_count < 0.98 * (h * w):
                outside = ~inside_mask
                rgba[outside, :3] = (rgba[outside, :3] * 0.5 + 238 * 0.5).astype(np.uint8)

                contours, _ = cv2.findContours(inside_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(rgba, contours, -1, (0, 180, 216, 255), 3)
                cv2.drawContours(rgba, contours, -1, (255, 255, 255, 255), 1)
        except Exception:
            pass

    img = Image.fromarray(rgba)
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
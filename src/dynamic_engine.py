from __future__ import annotations
import io
import base64
import warnings
import numpy as np
from PIL import Image
from pystac_client import Client
import planetary_computer as pc
import stackstac as st
from pyproj import Transformer

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"

def get_utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) / 6) + 1
    return 32600 + zone if lat >= 0 else 32700 + zone

def array_to_base64_png(arr: np.ndarray) -> str:
    """Fixed continuous remote sensing colormap."""
    h, w = arr.shape
    rgba = np.full((h, w, 4), [238, 235, 227, 255], dtype=np.uint8)
    
    # 1. Mask water / invalid / ocean pixels (NaN or values below land threshold)
    water_mask = np.isnan(arr) | (arr < 0.08)
    rgba[water_mask] = [0, 0, 0, 0]
    
    # 2. Vegetation foliage mask (NDVI >= 0.28)
    veg_mask = np.isfinite(arr) & (arr >= 0.28)
    
    if np.any(veg_mask):
        norm = np.clip((arr[veg_mask] - 0.28) / (0.75 - 0.28), 0.0, 1.0)
        
        # Smooth interpolation: Grass Green (104, 187, 89) to Deep Forest Green (25, 78, 40)
        r = (104 - (104 - 25) * norm).astype(np.uint8)
        g = (187 - (187 - 78) * norm).astype(np.uint8)
        b = (89 - (89 - 40) * norm).astype(np.uint8)
        
        rgba[veg_mask, 0] = r
        rgba[veg_mask, 1] = g
        rgba[veg_mask, 2] = b
        rgba[veg_mask, 3] = 255
    
    img = Image.fromarray(rgba)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

def compute_dynamic_year_ndvi(bbox: list[float], year: int) -> np.ndarray:
    min_lon, min_lat, max_lon, max_lat = bbox
    epsg = get_utm_epsg((min_lon + max_lon) / 2, (min_lat + max_lat) / 2)
    
    tfm = Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    minx, miny = tfm.transform(min_lon, min_lat)
    maxx, maxy = tfm.transform(max_lon, max_lat)
    bounds = (minx, miny, maxx, maxy)

    client = Client.open(CATALOG)
    
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{year}-06-01/{year}-08-31",
        query={"eo:cloud_cover": {"lt": 20}},
    )
    items = list(search.items())
    
    seen = set()
    uniq = []
    for it in items:
        if it.id not in seen:
            seen.add(it.id)
            uniq.append(it)
            
    uniq.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
    selected_items = [pc.sign(it) for it in uniq[:12]]

    if not selected_items:
        return np.full((128, 128), np.nan)

    stack = st.stack(
        selected_items,
        assets=["B04", "B08", "SCL"],
        epsg=epsg,
        bounds=bounds,
        resolution=80,
        dtype="float32",
        fill_value=np.float32("nan"),
        rescale=False,
    )

    red = stack.sel(band="B04").astype("float32")
    nir = stack.sel(band="B08").astype("float32")
    scl = stack.sel(band="SCL")

    keep = ["time", "y", "x", "spatial_ref"]
    red = red.drop_vars([c for c in red.coords if c not in keep], errors="ignore")
    nir = nir.drop_vars([c for c in nir.coords if c not in keep], errors="ignore")
    scl = scl.drop_vars([c for c in scl.coords if c not in keep], errors="ignore")

    # Correct for ESA Processing Baseline >= 04.00 (January 2022 onwards)
    if year >= 2022:
        red = (red - 1000.0).clip(min=0)
        nir = (nir - 1000.0).clip(min=0)

    # Convert surface reflectance DN to float
    red_scaled = red * 0.0001
    nir_scaled = nir * 0.0001

    # Compute NDVI
    ndvi = (nir_scaled - red_scaled) / (nir_scaled + red_scaled + 1e-6)

    # 1. Comprehensive QA & Water Mask:
    # 0: No Data, 1: Saturated, 6: Water, 9: Cloud High, 10: Cirrus, 11: Snow
    is_bad = scl.isin([0, 1, 6, 9, 10, 11])
    
    # 2. Spectral Water Cutoff: True land foliage requires NIR reflectance > 0.06
    is_water_radiometry = nir_scaled < 0.06
    
    ndvi_clean = ndvi.where(~is_bad & ~is_water_radiometry & np.isfinite(ndvi))

    # Maximum Value Composite across scenes
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        comp = ndvi_clean.max(dim="time", skipna=True).compute()

    return comp.values
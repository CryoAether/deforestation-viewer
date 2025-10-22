#src/ndvi.py
import numpy as np

# Bitmask and classification values for cloud, water, and snow masking
_L8_BAD = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7) # Landsat QA_PIXEL flags
SCL_BAD = np.array([3, 6, 7, 8, 9, 10, 11], dtype=np.uint8)    # Sentinel-2 bad SCL classes

# Computes NDVI from red and NIR bands (scaled reflectance 0–1).
def compute_ndvi(red, nir):
    red = red.astype("float32") / 10000.0
    nir = nir.astype("float32") / 10000.0
    return (nir - red) / (nir + red + 1e-6)

# Computes NDVI using dataset-specific scale and offset (Landsat/Sentinel mixed).
def compute_ndvi_mixed(red, nir, cfg):
    scale = cfg["scale"]; offset = cfg["offset"]
    redf = red * scale + offset
    nirf = nir * scale + offset
    ndvi = (nirf - redf) / (nirf + redf + 1e-6)
    return ndvi.astype("float32")

# Masks out invalid pixels (cloud, water, snow, etc.) for Sentinel-2 using the SCL band.
def mask_clouds(scl, arr):
    scl_i = scl.round().astype("int16")  # ensure categorical ints
    return arr.where(~np.isin(scl_i, list(SCL_BAD)))

# Applies cloud/water/snow masking for both Landsat and Sentinel datasets.
def mask_clouds_mixed(qa, arr, cfg):
    if cfg["mask"] == "s2":
        qa_i = qa.round().astype("uint8")
        bad = np.isin(qa_i, SCL_BAD)
        return arr.where(~bad)
    else:
        qa_u = qa.astype("uint16")
        bad = (qa_u & _L8_BAD) != 0
        return arr.where(~bad)
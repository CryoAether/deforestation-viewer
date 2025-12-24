# src/ndvi.py
import numpy as np

EXCLUDE_WATER = True

SCL_BAD = np.array(
    [0, 1, 2, 3, 7, 8, 9, 10, 11] + ([6] if EXCLUDE_WATER else []),
    dtype=np.uint8,
)

# Landsat Collection 2 L2 QA_PIXEL bits (USGS):
# 0 Fill, 1 Dilated Cloud, 2 Cirrus, 3 Cloud, 4 Cloud Shadow, 5 Snow, 7 Water
EXCLUDE_LANDSAT_WATER = True
_LANDSAT_BAD = (
    (1 << 0) |  # fill
    (1 << 1) |  # dilated cloud
    (1 << 2) |  # cirrus
    (1 << 3) |  # cloud
    (1 << 4) |  # cloud shadow
    (1 << 5)    # snow
    | ((1 << 7) if EXCLUDE_LANDSAT_WATER else 0)  # water (optional)
)

def compute_ndvi_mixed(red, nir, cfg):
    """Compute NDVI using dataset-specific reflectance scale/offset."""
    scale = float(cfg["scale"])
    offset = float(cfg["offset"])
    redf = red * scale + offset
    nirf = nir * scale + offset
    ndvi = (nirf - redf) / (nirf + redf + 1e-6)
    return ndvi.astype("float32")

def mask_clouds_mixed(qa, arr, cfg):
    """Mask clouds/snow/shadow/water using dataset-appropriate QA."""
    if cfg["mask"] == "s2":
        qa_i = qa.round().astype("uint8")
        bad = np.isin(qa_i, SCL_BAD)
        return arr.where(~bad)
    else:
        qa_u = qa.astype("uint16")
        bad = (qa_u & _LANDSAT_BAD) != 0
        return arr.where(~bad)
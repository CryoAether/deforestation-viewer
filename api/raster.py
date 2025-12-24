from __future__ import annotations

import pathlib as pl
from functools import lru_cache
from typing import Tuple

import numpy as np
import rasterio

from .config import NODATA

def _sample_array(path: pl.Path, max_size: int = 512) -> np.ndarray:
    """Read a downsampled array for quick robust stats."""
    with rasterio.open(path) as ds:
        # read first band only
        out_h = min(max_size, ds.height)
        out_w = min(max_size, ds.width)
        data = ds.read(
            1,
            out_shape=(out_h, out_w),
            masked=True,
            resampling=rasterio.enums.Resampling.bilinear,
        )
        arr = np.asarray(data)
        # convert masked -> nan
        if np.ma.isMaskedArray(data):
            arr = data.filled(np.nan)
        nodata = ds.nodata
        if nodata is None:
            nodata = NODATA
        arr = np.where(arr == nodata, np.nan, arr)
        return arr

@lru_cache(maxsize=256)
def robust_range(path_str: str, default: Tuple[float, float]) -> Tuple[float, float]:
    path = pl.Path(path_str)
    arr = _sample_array(path)
    vals = arr[np.isfinite(arr)]
    if vals.size == 0:
        return default
    p2, p98 = np.percentile(vals, [2, 98])
    mx = float(max(abs(p2), abs(p98), 0.05))
    return (-mx, mx)

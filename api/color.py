from __future__ import annotations

from io import BytesIO

import numpy as np

import matplotlib
matplotlib.use("Agg")  # server-safe
import matplotlib.cm as cm
from PIL import Image


def render_png_singleband(
    band: np.ndarray,
    vmin: float,
    vmax: float,
    cmap_name: str,
    nodata: float | None = None,
) -> bytes:
    """Render a single-band tile to RGBA PNG bytes.

    - NaN and nodata -> transparent
    - values outside [vmin, vmax] -> clipped
    """
    arr = band.astype("float32", copy=False)

    mask = ~np.isfinite(arr)
    if nodata is not None:
        mask |= (arr == nodata)

    # guard invalid ranges
    if not np.isfinite(vmin):
        vmin = 0.0
    if not np.isfinite(vmax):
        vmax = vmin + 1.0
    if vmax <= vmin:
        vmax = vmin + 1e-6

    norm = (arr - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)

    # ensure masked pixels don't get a color after clipping
    norm = np.where(mask, 0.0, norm)

    # fixed-size LUT for speed
    cmap = cm.get_cmap(cmap_name, 256)
    rgba = (cmap(norm) * 255.0).astype("uint8")  # H,W,4
    rgba[mask] = (0, 0, 0, 0)

    img = Image.fromarray(rgba, mode="RGBA")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=6)
    return buf.getvalue()
from __future__ import annotations

from io import BytesIO
from typing import Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")  # server-safe
import matplotlib.cm as cm
import matplotlib.colors as colors
from PIL import Image

def render_png_singleband(
    band: np.ndarray,
    vmin: float,
    vmax: float,
    cmap_name: str,
    nodata: float | None = None,
) -> bytes:
    """Render a single-band tile to RGBA PNG bytes."""
    arr = band.astype("float32", copy=False)

    # mask
    mask = ~np.isfinite(arr)
    if nodata is not None:
        mask |= (arr == nodata)

    # normalize
    if vmax <= vmin:
        vmax = vmin + 1e-6
    norm = (arr - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)

    cmap = cm.get_cmap(cmap_name)
    rgba = (cmap(norm) * 255.0).astype("uint8")  # H,W,4
    rgba[mask] = (0, 0, 0, 0)  # transparent where masked

    img = Image.fromarray(rgba, mode="RGBA")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

from __future__ import annotations

import pathlib as pl
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import COMP_DIR
from .delta import ensure_delta
from .raster import robust_range

router = APIRouter(prefix="/api")

def _years() -> List[int]:
    years = []
    for p in list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")):
        try:
            years.append(int(p.stem.split("_")[-1]))
        except Exception:
            pass
    return sorted(set(years))

@router.get("/health")
def health():
    return {"ok": True}

@router.get("/years")
def years():
    ys = _years()
    if not ys:
        raise HTTPException(status_code=404, detail=f"No composites found in {COMP_DIR}")
    return {"years": ys}

class DeltaReq(BaseModel):
    from_year: int
    to_year: int

@router.post("/delta")
def build_delta(req: DeltaReq):
    path = ensure_delta(req.from_year, req.to_year)
    vmin, vmax = robust_range(str(path), default=(-0.3, 0.3))
    return {"path": str(path), "vmin": vmin, "vmax": vmax}

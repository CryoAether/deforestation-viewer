import pathlib as pl
from composite import yearly_ndvi_composite

def main():
    interim = pl.Path("data/interim")
    composites = pl.Path("data/composites"); composites.mkdir(parents=True, exist_ok=True)

    for nc in sorted(interim.glob("s2_stack_*.nc")):
        year = nc.stem.split("_")[-1]
        out_tif = composites / f"ndvi_median_{year}.tif"
        yearly_ndvi_composite(str(nc), str(out_tif))
        print("Wrote", out_tif)

if __name__ == "__main__":
    main()
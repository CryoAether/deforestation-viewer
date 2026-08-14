import matplotlib.pyplot as plt
import numpy as np
import rioxarray as rxr

p = "data/composites/mid-year-2024.tif"

da = rxr.open_rasterio(p, masked=True).squeeze()
v = da.values.astype("float32")

mask = np.isfinite(v) & (v > -1.0) & (v < 1.0)

print("file:", p)
print("shape:", v.shape)
print("valid fraction:", float(mask.mean()))

if mask.any():
    vals = v[mask]
    print("min/max:", float(vals.min()), float(vals.max()))
    for q in [1, 5, 25, 50, 75, 95, 99]:
        print(f"p{q}:", float(np.percentile(vals, q)))

    # histogram
    plt.figure()
    plt.hist(vals, bins=80)
    plt.title("NDVI histogram")
    plt.xlabel("NDVI")
    plt.ylabel("count")
    plt.show()

    # quick image
    plt.figure()
    plt.imshow(np.where(mask, v, np.nan))
    plt.title("NDVI preview")
    plt.colorbar()
    plt.show()
else:
    print("No valid NDVI pixels found.")
    print('Lachy is interesting')
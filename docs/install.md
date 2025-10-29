# Installation and Setup

This guide walks through setting up the Deforestation Viewer environment from scratch.

---

## 1. Clone the Repository

```bash
git clone https://github.com/CryoAether/deforestation-viewer.git
cd deforestation-viewer
```

---

## 2. Create the Conda Environment

It’s recommended to isolate dependencies in a Conda environment.

```bash
conda create -n deforest python=3.11
conda activate deforest
```

---

## 3. Install Dependencies

All required packages are listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

> **Tip:** Installation may take a few minutes, especially for geospatial libraries like `rioxarray` and `geopandas`.

---

## 4. Set Up Microsoft Planetary Computer (MPC)

The pipeline retrieves satellite data directly from the MPC API.  
You don’t need an API key for public collections, but you must agree to the [Terms of Use](https://planetarycomputer.microsoft.com/terms).

If you experience network rate-limiting, sign up for a free [Planetary Computer account](https://planetarycomputer.microsoft.com/account) and authenticate once in your session:

```python
import planetary_computer as pc
pc.sign_in()
```

---

## 5. Verify Installation

Run the following test to confirm all libraries are working:

```bash
python -c "import stackstac, planetary_computer, geopandas; print('✅ Environment ready')"
```

If no errors appear, you’re ready to proceed.

---

Next: [Create a Custom AOI →](create_aoi.md)
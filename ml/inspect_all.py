import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent / "data"))

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 60)

for path in sorted(DATA_DIR.glob("*.parquet")):
    print("=" * 70)
    print(f"FILE: {path.name}")
    print("=" * 70)
    
    # Try GeoParquet first, fall back to plain pandas
    try:
        df = gpd.read_parquet(path)
        is_geo = True
    except Exception:
        df = pd.read_parquet(path)
        is_geo = False
    
    print(f"Type: {'GeoDataFrame' if is_geo else 'DataFrame'}")
    print(f"Rows: {len(df):,}  |  Columns: {len(df.columns)}")
    
    if is_geo:
        try:
            print(f"Geometry: {df.geom_type.value_counts().to_dict()}  |  CRS: EPSG:{df.crs.to_epsg()}")
        except Exception:
            pass
    
    # Schema + missing values in one compact table
    print("\nSchema:")
    summary = pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "missing_pct": (df.isna().sum() / len(df) * 100).round(1),
        "sample_value": [str(df[c].dropna().iloc[0])[:60] if df[c].notna().any() else "" for c in df.columns]
    })
    print(summary.to_string())
    
    print()
import pandas as pd
import os

# File paths
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores.csv')
VERTICAL_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores_vertical.csv')

# Read the wide-format z-score CSV
try:
    df = pd.read_csv(OUTPUT_CSV)
except Exception as e:
    print(f"Failed to read z-score CSV: {e}")
    exit(1)

# Stat columns to melt
ZSCORE_COLS = ['S%', 'SV%', 'PDO', 'CF%', 'xGF', 'xGA', 'aGF', 'aGA', 'axDiff', 'SCF%', 'HDF%', 'HDC%', 'HDCO%']

# Assemble vertical format
rows = []
for _, row in df.iterrows():
    team = row['Team']
    for stat in ZSCORE_COLS:
        value = row[stat]
        zscore = row[f'z{stat}']
        rows.append({'team': team, 'stat': stat, 'value': value, 'zscore': zscore})
vertical_df = pd.DataFrame(rows)

# Save to new CSV
try:
    vertical_df.to_csv(VERTICAL_CSV, index=False)
    print(f"Vertical z-score CSV written to {VERTICAL_CSV}")
except Exception as e:
    print(f"Failed to write vertical CSV: {e}")
    exit(1)

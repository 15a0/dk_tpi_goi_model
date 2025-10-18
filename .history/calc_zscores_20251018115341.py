import os
import sys
import pandas as pd
from scipy.stats import zscore
import numpy as np

# Constants
XLS_PATH = os.path.join(os.path.dirname(__file__), 'Analytics_20251018.xlsx')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores_vertical.csv')
TAB_NAME = 'Worksheet'
ZSCORE_COLS = [ 'CF%', 'xGF', 'xGA',   'SCF%', 'HDF%', 'HDC%', 'HDCO%']

# Read Excel and check worksheet
try:
    xl = pd.ExcelFile(XLS_PATH)
    if TAB_NAME not in xl.sheet_names:
        print(f"Tab '{TAB_NAME}' not found. Exiting.")
        sys.exit(1)
    df = xl.parse(TAB_NAME, header=1)  # Data starts at row 2 (header=1)
except Exception as e:
    print(f"Failed to read Excel file: {e}")
    sys.exit(1)

# Fix blank column name between Rk and S%
headers = list(df.columns)
if headers[1] == '' and headers[0] == 'Rk' and headers[2] == 'S%':
    headers[1] = 'Team'
    df.columns = headers

# Only keep needed columns
keep_cols = ['Team'] + ZSCORE_COLS
missing = [col for col in keep_cols if col not in df.columns]
if missing:
    print(f"Missing columns: {missing}. Exiting.")
    sys.exit(1)
df = df[keep_cols].reset_index(drop=True)
#######################################################################
# Calculate z-scores for all columns at once and store in new columns
for stat in ZSCORE_COLS:
    df[f'{stat}_zscore'] = zscore(df[stat], nan_policy='omit')

# Assemble vertical output using precomputed z-scores
rows = []
for idx, row in df.iterrows():
    team = row['Team']
    for stat in ZSCORE_COLS:
        value = row[stat]
        z = row[f'{stat}_zscore']
        if stat == 'xGA':
            z = -z
        rows.append({'team': team, 'stat': stat, 'value': value, 'zscore': z})
vertical_df = pd.DataFrame(rows)

# Sample 10 random rows and compare zscore to horizontal lookup
sample = vertical_df.sample(n=10, random_state=42)
all_match = True
for _, vrow in sample.iterrows():
    team = vrow['team']
    stat = vrow['stat']
    z_vert = vrow['zscore']
    # Lookup in horizontal df
    hrow = df[df['Team'] == team].iloc[0]
    hz = hrow[f'{stat}_zscore']
    if stat == 'xGA':
        hz = -hz
    match = np.isclose(z_vert, hz, atol=1e-8)
    print(f"Sample: Team={team}, Stat={stat}, Vertical={z_vert}, Horizontal={hz}, Match={match}")
    if not match:
        all_match = False
        break
if not all_match:
    print("ERROR: Vertical zscore misalignment detected. Exiting without writing CSV.")
    sys.exit(1)
else:
    try:
        vertical_df.to_csv(OUTPUT_CSV, index=False)
        print(f"Vertical z-score CSV written to {OUTPUT_CSV}")
    except Exception as e:
        print(f"Failed to write CSV: {e}")
        sys.exit(1)

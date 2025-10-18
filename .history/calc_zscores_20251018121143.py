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
#


# Calculate z-scores for all columns at once and store in new columns
for stat in ZSCORE_COLS:
    df[f'{stat}_zscore'] = zscore(df[stat], nan_policy='omit')

# Interactive cycle for each stat
for stat in ZSCORE_COLS:
    stat_col = stat
    z_col = f'{stat}_zscore'
    # Reverse sign for xGA zscore
    z = df[z_col] if stat != 'xGA' else -df[z_col]
    df_stat = pd.DataFrame({
        'team': df['Team'],
        'stat': stat,
        'value': df[stat_col],
        'zscore': z
    })
    df_stat = df_stat.sort_values(by='value', ascending=False).reset_index(drop=True)
    rank_col = f'z{stat}_Rank'
    df_stat[rank_col] = range(1, len(df_stat) + 1)
    print(f"\n===== {stat} =====")
    print(df_stat)
    while True:
        resp = input(f"Approve {stat}? (Y to continue, Q to quit): ").strip().lower()
        if resp == 'y':
            break
        elif resp == 'q':
            print("Exiting by user request.")
            sys.exit(0)
        else:
            print("Please enter Y or Q.")

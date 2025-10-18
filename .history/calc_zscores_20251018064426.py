import os
import sys
import pandas as pd
from scipy.stats import zscore

# Constants
XLS_PATH = os.path.join(os.path.dirname(__file__), 'Analytics_20251018.xls.xlsx')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores.csv')
TAB_NAME = 'worksheet'
ZSCORE_COLS = ['S%', 'SV%', 'PDO', 'CF%', 'xGF', 'xGA', 'aGF', 'aGA', 'axDiff', 'SCF%', 'HDF%', 'HDC%', 'HDCO%']

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
df = df[keep_cols]

# Calculate z-scores
for col in ZSCORE_COLS:
    df[f'z{col}'] = zscore(df[col], nan_policy='omit')

# Save to CSV
try:
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Z-scores written to {OUTPUT_CSV}")
except Exception as e:
    print(f"Failed to write CSV: {e}")
    sys.exit(1)

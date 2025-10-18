import os
import sys
import pandas as pd
from scipy.stats import zscore
import numpy as np
import yaml

# Constants
XLS_PATH = os.path.join(os.path.dirname(__file__), 'Analytics_20251018.xlsx')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores_vertical.csv')
TAB_NAME = 'Worksheet'
# Load zscore config
with open(os.path.join(os.path.dirname(__file__), 'zscore_config.yaml'), 'r') as f:
    zscore_cfg = yaml.safe_load(f)
ZSCORE_STATS = zscore_cfg['zscore_stats']

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
keep_cols = ['Team'] + [stat_cfg['name'] for stat_cfg in ZSCORE_STATS]
missing = [col for col in keep_cols if col not in df.columns]
if missing:
    print(f"Missing columns: {missing}. Exiting.")
    sys.exit(1)
df = df[keep_cols].reset_index(drop=True)
#


# Calculate z-scores for all columns at once and store in new columns
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    df[f'{stat}_zscore'] = zscore(df[stat], nan_policy='omit')

# Interactive cycle for each stat
all_dfs = []
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    z_col = f'{stat}_zscore'
    reverse_sign = stat_cfg.get('reverse_sign', False)
    sort_order = stat_cfg.get('sort_order', 'desc')
    z = df[z_col]
    if reverse_sign:
        z = -z
    df_stat = pd.DataFrame({
        'team': df['Team'],
        'stat': stat,
        'value': df[stat],
        'zscore': z
    })
    ascending = True if sort_order == 'asc' else False
    df_stat = df_stat.sort_values(by='value', ascending=ascending).reset_index(drop=True)
    df_stat['zStat_rank'] = range(1, len(df_stat) + 1)
    print(f"\n===== {stat} =====")
    print(df_stat)
    all_dfs.append(df_stat)
    while True:
        resp = input(f"Approve {stat}? (Y to continue, Q to quit): ").strip().lower()
        if resp == 'y':
            break
        elif resp == 'q':
            print("Exiting by user request.")
            sys.exit(0)
        else:
            print("Please enter Y or Q.")

# Combine all stat DataFrames
combined_df = pd.concat(all_dfs, ignore_index=True)
combined_df = combined_df.sort_values(by='zscore', ascending=False).reset_index(drop=True)
combined_df['zOvlIdx'] = range(1, len(combined_df) + 1)

print("\n===== Combined DataFrame (sorted by zscore DESC, with zOvlIdx) =====")
print(combined_df)
combined_df.to_csv('zOverall.csv', index=False)
print("Combined DataFrame written to zOverall.csv")


# Create single zscore metric for each team

# Sum scores for all teams:
# CF%, xGF, xGA * 1
# SCF%, HDF% *.5

### Use  Bayesian shrinkage with assumptions (n_games = 5, n_prior = 25/30) for  HDC% and HDCO%

# Build weights dict from YAML config
weights = {stat_cfg['name']: stat_cfg.get('weight', 1) for stat_cfg in ZSCORE_STATS}

# Pivot the combined_df to have stats as columns for each team
team_df = combined_df.pivot_table(index='team', columns='stat', values='zscore', aggfunc='first').reset_index()

# Apply Bayesian shrinkage for HDC% and HDCO%
n_games = 5  # Assumption based on early-season sample

# For HDC%
n_prior_hdc = 25
team_df['HDC%_shrunk'] = (team_df['HDC%'] * n_games + 0 * n_prior_hdc) / (n_games + n_prior_hdc)

# For HDCO%
n_prior_hdco = 30
team_df['HDCO%_shrunk'] = (team_df['HDCO%'] * n_games + 0 * n_prior_hdco) / (n_games + n_prior_hdco)

# Calculate total z-score for each team
team_df['total_z'] = (
    team_df['CF%'] * weights['CF%'] +
    team_df['xGF'] * weights['xGF'] +
    team_df['xGA'] * weights['xGA'] +
    team_df['SCF%'] * weights['SCF%'] +
    team_df['HDF%'] * weights['HDF%'] +
    team_df['HDC%_shrunk'] * weights['HDC%'] +
    team_df['HDCO%_shrunk'] * weights['HDCO%']
)

# Sort by total_z descending
team_df = team_df.sort_values(by='total_z', ascending=False).reset_index(drop=True)

print("\n===== Team Total Z-Scores (with smoothed HDC% and HDCO%) =====")
print(team_df)

# Optionally save to CSV
team_df.to_csv('team_total_zscores.csv', index=False)
print("Team total z-scores written to team_total_zscores.csv")
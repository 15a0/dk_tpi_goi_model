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

## ANALYTICS ##
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
# Only keep columns that exist in the main Excel sheet (exclude penalty stats)
main_stat_names = [stat_cfg['name'] for stat_cfg in ZSCORE_STATS if stat_cfg['name'] in df.columns]
keep_cols = ['Team'] + main_stat_names
missing = [col for col in keep_cols if col not in df.columns]
if missing:
    print(f"Missing columns: {missing}. Exiting.")
    sys.exit(1)
df = df[keep_cols].reset_index(drop=True)
#


# Calculate z-scores for all columns at once and store in new columns
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    if stat not in df.columns:
        continue
    df[f'{stat}_zscore'] = zscore(df[stat], nan_policy='omit')

# Interactive cycle for each stat
all_dfs = []
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    if stat not in df.columns:
        continue
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
    # print(f"\n===== {stat} =====")
    # print(df_stat)
    all_dfs.append(df_stat)
    # while True:
    #     resp = input(f"Approve {stat}? (Y to continue, Q to quit): ").strip().lower()
    #     if resp == 'y':
    #         break
    #     elif resp == 'q':
    #         print("Exiting by user request.")
    #         sys.exit(0)
    #     else:
    #         print("Please enter Y or Q.")



### ADD NEW PENALTY DF HERE ####
import pandas as pd
import yaml
import os
import sys

# Read Penalties tab into penalties_df
penalties_xlsx = os.path.join(os.path.dirname(__file__), 'Penalties_20251018.xlsx')
penalties_tab = 'Penalties'
try:
    penalties_xl = pd.ExcelFile(penalties_xlsx)
    if penalties_tab not in penalties_xl.sheet_names:
        print(f"Tab '{penalties_tab}' not found in Penalties_20251018.xlsx. Exiting.")
        sys.exit(1)
    penalties_df = penalties_xl.parse(penalties_tab)
except Exception as e:
    print(f"Failed to read penalties Excel file: {e}")
    sys.exit(1)

# Load team mappings from YAML
with open(os.path.join(os.path.dirname(__file__), 'zscore_config.yaml'), 'r') as f:
    zscore_cfg = yaml.safe_load(f)
team_mappings = zscore_cfg.get('team_mappings') or {}

# Normalize and strip team names before mapping
import unicodedata

def normalize_team(s):
    if pd.isnull(s):
        return s
    return unicodedata.normalize('NFC', str(s)).strip()

# Normalize mapping keys as well
norm_team_mappings = {normalize_team(k): v for k, v in team_mappings.items()}

penalties_df['Team'] = penalties_df['Team'].apply(normalize_team)
penalties_df['Team'] = penalties_df['Team'].replace(norm_team_mappings)

# Reduce to four columns
cols = ['Team', 'Pen Drawn/60', 'Pen Taken/60', 'Net Pen/60']
penalties_df = penalties_df[cols]

# Print and exit
print("\n===== Penalties DataFrame =====")
print(penalties_df)

### ADD penalty df logic here ###

# For each penalty stat in ZSCORE_STATS, if present in penalties_df, create and print a per-stat DataFrame
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    if stat not in penalties_df.columns:
        continue
    z_col = f'{stat}_zscore'
    reverse_sign = stat_cfg.get('reverse_sign', False)
    sort_order = stat_cfg.get('sort_order', 'desc')
    # Calculate zscore for this stat
    penalties_df[z_col] = zscore(penalties_df[stat], nan_policy='omit')
    z = penalties_df[z_col]
    if reverse_sign:
        z = -z
    df_stat = pd.DataFrame({
        'team': penalties_df['Team'],
        'stat': stat,
        'value': penalties_df[stat],
        'zscore': z
    })
    ascending = True if sort_order == 'asc' else False
    df_stat = df_stat.sort_values(by='value', ascending=ascending).reset_index(drop=True)
    df_stat['zStat_rank'] = range(1, len(df_stat) + 1)
    print(f"\n===== {stat} (Penalties) =====")
    print(df_stat)
    # Optionally: append to all_dfs if you want to include these in combined_df



#  sys.exit(0)


#######################################################

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
# zCF%, zxGF, zxGA * 1
# zSCF%, zHDF% *.5



### Use  Bayesian shrinkage with assumptions (n_games = 5, n_prior = 25/30) for  zHDC% and zHDCO%




###############################################################################################

# Create single zscore metric for each team (zTotal)
team_list = df['Team'].unique()
ztotal_rows = []
for team in team_list:
    zsum = 0
    for stat_cfg in ZSCORE_STATS:
        stat = stat_cfg['name']
        weight = stat_cfg.get('weight', 1)
        if weight is None:
            continue  # skip if weight is not set
        # Find the zscore for this team/stat
        z = combined_df[(combined_df['team'] == team) & (combined_df['stat'] == stat)]['zscore']
        if not z.empty:
            zsum += z.iloc[0] * weight
    ztotal_rows.append({'team': team, 'zTotal': zsum})
ztotal_df = pd.DataFrame(ztotal_rows)
ztotal_df = ztotal_df.sort_values(by='zTotal', ascending=False).reset_index(drop=True)
print("\n===== Team zTotal Scores =====")
print(ztotal_df)



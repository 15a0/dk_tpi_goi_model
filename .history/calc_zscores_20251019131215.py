import os
import sys
import pandas as pd
from scipy.stats import zscore
import numpy as np
import yaml
import unidecode

# ===============================
# NHL Team Z-Score Calculation Pipeline
#
# This script processes two data sources:
#   1. Main stats Excel file (Analytics_20251018.xlsx)
#   2. Penalties Excel file (Penalties_20251018.xlsx)
#
# It uses a YAML config (zscore_config.yaml) to control which stats to process, their sort order, and weighting.
#
# The output consists of:
#   - zOverall.csv: Combined per-stat z-scores for all teams and stats
#   - team_total_zscores.csv: Single composite z-score per team, weighted sum of all stats (including penalties)
# ===============================

# Constants
XLS_PATH = os.path.join(os.path.dirname(__file__), 'Analytics_20251018.xlsx')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'Analytics_20251018_zscores_vertical.csv')
TAB_NAME = 'Worksheet'
# Load zscore config
# --- Load config (YAML) ---
with open(os.path.join(os.path.dirname(__file__), 'zscore_config.yaml'), 'r') as f:
    zscore_cfg = yaml.safe_load(f)
ZSCORE_STATS = zscore_cfg['zscore_stats']

# --- Load main stats Excel file ---
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
# --- Filter columns to only those present in the main Excel sheet (exclude penalty stats) ---
main_stat_names = [stat_cfg['name'] for stat_cfg in ZSCORE_STATS if stat_cfg['name'] in df.columns]
keep_cols = ['Team'] + main_stat_names
missing = [col for col in keep_cols if col not in df.columns]
if missing:
    print(f"Missing columns: {missing}. Exiting.")
    sys.exit(1)
df = df[keep_cols].reset_index(drop=True)
#

# Define canonical team names from main DataFrame
canonical_teams = set(df['Team'])


# --- Calculate z-scores for each stat in the main DataFrame ---
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    if stat not in df.columns:
        continue
    df[f'{stat}_zscore'] = zscore(df[stat], nan_policy='omit')

# --- For each main stat, create a per-stat DataFrame (team, stat, value, zscore, rank) ---
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
    # (prints for review are commented out)
    all_dfs.append(df_stat)
    # (interactive approval loop commented out)



### ADD NEW PENALTY DF HERE ####
import pandas as pd
import yaml
import os
import sys

# --- Load and process Penalties Excel file ---
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
# --- Load team mappings from YAML and normalize team names in penalties_df ---
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

# Reduce penalties_df to only the relevant columns
cols = ['Team', 'Pen Drawn/60', 'Pen Taken/60', 'Net Pen/60']
penalties_df = penalties_df[cols]

# Print penalties DataFrame for reference (not used in final output)
# print("\n===== Penalties DataFrame =====")
# print(penalties_df)

### ADD penalty df logic here ###

# --- For each penalty stat, create a per-stat DataFrame and append to all_dfs ---
for stat_cfg in ZSCORE_STATS:
    stat = stat_cfg['name']
    if stat not in penalties_df.columns:
        continue
    z_col = f'{stat}_zscore'
    reverse_sign = stat_cfg.get('reverse_sign', False)
    sort_order = stat_cfg.get('sort_order', 'desc')
    # Calculate zscore for this stat in penalties_df
    penalties_df[z_col] = zscore(penalties_df[stat], nan_policy='omit')
    z = penalties_df[z_col]
    if reverse_sign:
        z = -z
        # Clean and normalize Team names with unidecode
    penalties_df['Team'] = penalties_df['Team'].apply(lambda s: unidecode(str(s)).strip() if pd.notnull(s) else s)
    # Check for non-canonical teams
    unknown_teams = set(penalties_df['Team']) - canonical_teams
    if unknown_teams:
        print(f"Unknown team names in Penalties_20251018.xlsx after cleaning: {unknown_teams}")
        import sys; sys.exit(0)
    df_stat = pd.DataFrame({
        'team': penalties_df['Team'],
        'stat': stat,
        'value': penalties_df[stat],
        'zscore': z
    })
    ascending = True if sort_order == 'asc' else False
    df_stat = df_stat.sort_values(by='value', ascending=ascending).reset_index(drop=True)
    df_stat['zStat_rank'] = range(1, len(df_stat) + 1)
    # (prints for review are commented out)
    all_dfs.append(df_stat)



#  sys.exit(0)


#######################################################

# --- Load and process FOW% from FOW_20251018.xlsx ---
fow_xlsx = os.path.join(os.path.dirname(__file__), 'FOW_20251018.xlsx')
try:
    fow_xl = pd.ExcelFile(fow_xlsx)
    if len(fow_xl.sheet_names) != 1:
        print(f"Expected exactly one tab in FOW_20251018.xlsx, found: {fow_xl.sheet_names}. Exiting.")
        sys.exit(1)
    fow_tab = fow_xl.sheet_names[0]
    fow_df = fow_xl.parse(fow_tab)
except Exception as e:
    print(f"Failed to read FOW% Excel file: {e}")
    sys.exit(1)

from unidecode import unidecode

# Clean and normalize Team names with unidecode
fow_df['Team'] = fow_df['Team'].apply(lambda s: unidecode(str(s)).strip() if pd.notnull(s) else s)

# Reduce to only Team and FOW%
fow_df = fow_df[['Team', 'FOW%']]

# Check for non-canonical teams
unknown_teams = set(fow_df['Team']) - canonical_teams
if unknown_teams:
    print(f"Unknown team names in FOW_20251018.xlsx after cleaning: {unknown_teams}")
    import sys; sys.exit(0)

# Calculate zscore for FOW% and append to all_dfs
from scipy.stats import zscore as _zscore
fow_df['FOW%_zscore'] = _zscore(fow_df['FOW%'], nan_policy='omit')
z = fow_df['FOW%_zscore']
df_stat = pd.DataFrame({
    'team': fow_df['Team'],
    'stat': 'FOW%',
    'value': fow_df['FOW%'],
    'zscore': z
})
df_stat = df_stat.sort_values(by='value', ascending=False).reset_index(drop=True)
df_stat['zStat_rank'] = range(1, len(df_stat) + 1)
# print("\n===== FOW% (zscore) =====")
# print(df_stat)
print(f"Appending DataFrame for stat FOW%: unique teams: {df_stat['team'].unique()}")
all_dfs.append(df_stat)
# sys.exit(0)

#######################################################

# --- Load and process PP% and PK% from PP_20251018.xlsx ---
pp_xlsx = os.path.join(os.path.dirname(__file__), 'PP_20251018.xlsx')
try:
    pp_xl = pd.ExcelFile(pp_xlsx)
    if len(pp_xl.sheet_names) != 1:
        print(f"Expected exactly one tab in PP_20251018.xlsx, found: {pp_xl.sheet_names}. Exiting.")
        sys.exit(1)
    pp_tab = pp_xl.sheet_names[0]
    pp_df = pp_xl.parse(pp_tab, header=1)  # Data starts at row 2 (header=1)
except Exception as e:
    print(f"Failed to read PP% Excel file: {e}")
    sys.exit(1)

# Fix blank or misnamed team column (match main stats logic)
headers = list(pp_df.columns)
if len(headers) > 2 and headers[1] == '' and headers[0] == 'Rk' and headers[2] == 'S%':
    headers[1] = 'Team'
    pp_df.columns = headers
elif 'Team' not in headers:
    # Try to find a column that looks like team names and rename
    for i, col in enumerate(headers):
        if i > 0 and all(isinstance(x, str) and len(x) > 3 for x in pp_df[col].head(5)):
            headers[i] = 'Team'
            pp_df.columns = headers
            break

# Extract only Team, PP%, PK%
pp_pk_cols = ['Team', 'PP%', 'PK%']
missing = [col for col in pp_pk_cols if col not in pp_df.columns]
if missing:
    print(f"Missing columns in PP file: {missing}. Exiting.")
    sys.exit(1)
pp_df = pp_df[pp_pk_cols].reset_index(drop=True)

# Exclude League Average row
pp_df = pp_df[pp_df['Team'] != 'League Average'].reset_index(drop=True)

# Clean and normalize Team names with unidecode for PP/PK
pp_df['Team'] = pp_df['Team'].apply(lambda s: unidecode(str(s)).strip() if pd.notnull(s) else s)
# Check for non-canonical teams
unknown_teams = set(pp_df['Team']) - canonical_teams
if unknown_teams:
    print(f"Unknown team names in PP_20251018.xlsx after cleaning: {unknown_teams}")
    import sys; sys.exit(0)

# Calculate z-score for PP%
from scipy.stats import zscore as _zscore
pp_df['PP%_zscore'] = _zscore(pp_df['PP%'], nan_policy='omit')
df_pp = pd.DataFrame({
    'team': pp_df['Team'],
    'stat': 'PP%',
    'value': pp_df['PP%'],
    'zscore': pp_df['PP%_zscore']
})
df_pp = df_pp.sort_values(by='value', ascending=False).reset_index(drop=True)
df_pp['zStat_rank'] = range(1, len(df_pp) + 1)

# Calculate z-score for PK%
pp_df['PK%_zscore'] = _zscore(pp_df['PK%'], nan_policy='omit')
df_pk = pd.DataFrame({
    'team': pp_df['Team'],
    'stat': 'PK%',
    'value': pp_df['PK%'],
    'zscore': pp_df['PK%_zscore']
})
df_pk = df_pk.sort_values(by='value', ascending=False).reset_index(drop=True)
df_pk['zStat_rank'] = range(1, len(df_pk) + 1)

print(f"Appending DataFrame for stat PP%: unique teams: {df_pp['team'].unique()}")
all_dfs.append(df_pp)
print(f"Appending DataFrame for stat PK%: unique teams: {df_pk['team'].unique()}")
all_dfs.append(df_pk)
# sys.exit(0)

#######################################################

# --- Combine all per-stat DataFrames (main and penalties) into one big DataFrame ---
combined_df = pd.concat(all_dfs, ignore_index=True)
combined_df = combined_df.sort_values(by='zscore', ascending=False).reset_index(drop=True)
combined_df['zOvlIdx'] = range(1, len(combined_df) + 1)

print(f"\nUnique team names in combined_df before writing zOverall.csv: {combined_df['team'].unique()}")
print("\n===== Combined DataFrame (sorted by zscore DESC, with zOvlIdx) =====")
print(combined_df)
combined_df.to_csv('zOverall.csv', index=False)
print("Combined DataFrame written to zOverall.csv")

# --- Calculate a single composite z-score per team (zTotal), using weights from config ---
team_list = df['Team'].unique()
ztotal_rows = []
for team in team_list:
    zsum = 0
    for stat_cfg in ZSCORE_STATS:
        stat = stat_cfg['name']
        weight = stat_cfg.get('weight', 1)
        if weight is None:
            continue  # skip if weight is not set
        # Find the zscore for this team/stat in combined_df
        z = combined_df[(combined_df['team'] == team) & (combined_df['stat'] == stat)]['zscore']
        if not z.empty:
            zsum += z.iloc[0] * weight
    ztotal_rows.append({'team': team, 'zTotal': zsum})
ztotal_df = pd.DataFrame(ztotal_rows)
ztotal_df = ztotal_df.sort_values(by='zTotal', ascending=False).reset_index(drop=True)
print("\n===== Team zTotal Scores =====")
print(ztotal_df)
ztotal_df.to_csv('team_total_zscores.csv', index=False)
print("Team zTotal scores written to team_total_zscores.csv")



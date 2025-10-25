import os
import sys
import pandas as pd
from scipy.stats import zscore
import numpy as np
import yaml
import fnmatch
from unidecode import unidecode as ud
from datetime import datetime

# ================================
# GOI v2.1 MODEL GUARDRAILS
# ================================
GOI_VERSION = "v2.1"
EARLY_SEASON_GAMES = 10
SH_CAP_EARLY = 0.095   # 9.5%
SV_CAP_EARLY = 0.900   # .900
PP_CAP_EARLY = 0.40    # Reduce reliance by 40%

HOT_GOALIE_SV_THRESHOLD = 0.925
HOT_GOALIE_PENALTY = -0.7

LINE_MOVE_THRESHOLD = 0.15  # 15 cents
MIN_DOG_Z_FOR_SHARP_MOVE = 2.1

def apply_goi_guardrails(df, config, games_played_dict, opp_goalie_last3_sv, market_lines):
    """
    Applies GOI v2.1 guardrails to z-scores for matchup modeling.
    
    Args:
        df: zOverall DataFrame
        config: YAML config
        games_played_dict: {team: games_played}
        opp_goalie_last3_sv: {team: opp_goalie_sv_last3}
        market_lines: {team: {'ml': float, 'close_move': float}}

    Returns:
        df with new 'goi_z' column
    """
    print(f"\n--- Applying GOI {GOI_VERSION} Guardrails ---")
    
    df = df.copy()
    df['goi_z'] = df['zscore'].copy()

    # 1. Early-Season Volatility Caps
    for team, gp in games_played_dict.items():
        if gp >= EARLY_SEASON_GAMES:
            continue

        mask = df['team'] == team
        sh_mask = df['stat'].str.contains('sh%|shoot', case=False, na=False)
        sv_mask = df['stat'].str.contains('sv%|save', case=False, na=False)
        pp_mask = df['stat'].str.contains('pp%', case=False, na=False)

        # Cap shooting % regression
        df.loc[mask & sh_mask, 'goi_z'] = np.clip(
            df.loc[mask & sh_mask, 'goi_z'],
            -np.inf, zscore([SH_CAP_EARLY] * 32)[0]
        )

        # Cap save % weight
        df.loc[mask & sv_mask, 'goi_z'] = np.clip(
            df.loc[mask & sv_mask, 'goi_z'],
            zscore([SV_CAP_EARLY] * 32)[0], np.inf
        )

        # Reduce PP% reliance
        df.loc[mask & pp_mask, 'goi_z'] *= (1 - PP_CAP_EARLY)

        if (mask & (sh_mask | sv_mask | pp_mask)).any():
            print(f"  -> Early-season cap applied to {team} (GP: {gp})")

    # 2. Hot Goalie Alert
    for team, sv in opp_goalie_last3_sv.items():
        if sv > HOT_GOALIE_SV_THRESHOLD:
            high_shot_mask = (
                (df['team'] == team) &
                (df['stat'].str.contains('sog|shots|cf', case=False, na=False))
            )
            if high_shot_mask.any():
                df.loc[high_shot_mask, 'goi_z'] += HOT_GOALIE_PENALTY
                print(f"  -> Hot Goalie Alert: {team} vs SV%={sv:.3f} → -0.7 GOI")

    # 3. Market Drift Cross-Check
    for team, line_data in market_lines.items():
        move = line_data.get('close_move', 0)
        ml = line_data.get('ml', 0)
        is_dog = ml > 0

        if is_dog and move > LINE_MOVE_THRESHOLD:
            dog_mask = df['team'] == team
            current_max = df.loc[dog_mask, 'goi_z'].max()
            if current_max < MIN_DOG_Z_FOR_SHARP_MOVE:
                df.loc[dog_mask, 'goi_z'] = np.nan  # Fade entirely
                print(f"  -> Sharp money fade: {team} +{ml} moved {move:+.0f}¢ → requires {MIN_DOG_Z_FOR_SHARP_MOVE}σ")

    return df

# ================================
# ORIGINAL FUNCTIONS (unchanged except for integration points)
# ================================

def get_and_verify_file_paths(config):
    today_str = datetime.now().strftime('%Y%m%d')
    verified_files = []
    all_files_found = True

    print("--- Verifying Input Files ---")

    for provider in config.get('providers', []):
        provider_name = provider.get('name')
        for file_info in provider.get('files', []):
            filename_template = file_info.get('filename_template')
            if not filename_template:
                print(f"WARNING: Missing 'filename_template' in config for a file under '{provider_name}'. Skipping.")
                continue

            expected_filename = f"{today_str}_{filename_template}"
            file_path = os.path.join(os.path.dirname(__file__), expected_filename)

            print(f"Checking for '{expected_filename}'...", end=' ')
            if os.path.exists(file_path):
                print("Found.")
                verified_files.append({
                    'provider_name': provider_name,
                    'file_path': file_path,
                    'file_info': file_info
                })
            else:
                print("NOT FOUND.")
                all_files_found = False

    if not all_files_found:
        return None
        
    return verified_files

def validate_teams(df, canonical_teams, team_name_mappings):
    teams_from_file = df['Team']
    working_teams = teams_from_file.copy()

    for i, team_name in working_teams.items():
        original_name = str(team_name)
        for rule in team_name_mappings:
            if fnmatch.fnmatch(original_name, rule['pattern']):
                working_teams.at[i] = rule['replacement']
                print(f"    - Mapped '{original_name}' to '{rule['replacement']}' based on pattern '{rule['pattern']}'.")
                break

    cleaned_teams = working_teams.apply(lambda s: ud(str(s)).strip() if pd.notnull(s) else s)
    df['Team'] = cleaned_teams

    final_unknown = set(cleaned_teams) - canonical_teams
    if final_unknown:
        print(f"  -> VALIDATION FAILED: Uncorrectable team names found: {final_unknown}")
        return False

    if len(set(cleaned_teams)) != 32:
        print(f"  -> VALIDATION FAILED: Expected 32 unique teams, found {len(set(cleaned_teams))}.")
        return False

    print("  -> Team validation PASSED.")
    return True

def process_stats_batch(df, stats_config):
    all_stat_dfs = []
    stat_names_to_process = [stat['name'] for stat in stats_config]
    print(f"  -> Batch processing stats: {stat_names_to_process}")

    for stat_name in stat_names_to_process:
        if stat_name in df.columns:
            df[f'{stat_name}_zscore'] = zscore(df[stat_name], nan_policy='omit')

    for stat_cfg in stats_config:
        stat_name = stat_cfg['name']
        zscore_col = f'{stat_name}_zscore'
        if zscore_col not in df.columns:
            print(f"  -> WARNING: Stat '{stat_name}' not found. Skipping.")
            continue

        stat_df = df[['Team', stat_name, zscore_col]].copy()
        
        if stat_cfg.get('reverse_sign', False):
            stat_df[zscore_col] = stat_df[zscore_col] * -1
            print(f"    - Reversed sign for '{stat_name}'.")

        stat_df['rank'] = stat_df[zscore_col].rank(method='min', ascending=False)
        stat_df.rename(columns={
            'Team': 'team',
            stat_name: 'value',
            zscore_col: 'zscore'
        }, inplace=True)
        stat_df['stat'] = stat_name
        final_stat_df = stat_df[['team', 'stat', 'value', 'zscore', 'rank']]
        all_stat_dfs.append(final_stat_df)
        print(f"    - Processed '{stat_name}'.")

    print(f"  -> Batch complete: {len(all_stat_dfs)} DataFrames.")
    return all_stat_dfs

def create_tpi_rankings(z_overall_df, config):
    print("\n--- Creating TPI Rankings ---")
    bucket_rows = z_overall_df[z_overall_df['stat'].str.contains('_avg', na=False)].copy()
    tpi_df = bucket_rows.pivot_table(index='team', columns='stat', values='zscore', aggfunc='first').reset_index()
    tpi_df.rename(columns={
        'offensive_creation_avg': 'offensive_creation',
        'defensive_resistance_avg': 'defensive_resistance',
        'pace_drivers_avg': 'pace_drivers'
    }, inplace=True)

    bucket_weights = config.get('bucket_weights', {
        'offensive_creation': 0.4, 'defensive_resistance': 0.3, 'pace_drivers': 0.3
    })

    tpi_df['TPI'] = (
        tpi_df['offensive_creation'] * bucket_weights.get('offensive_creation', 0.4) +
        tpi_df['defensive_resistance'] * bucket_weights.get('defensive_resistance', 0.3) +
        tpi_df['pace_drivers'] * bucket_weights.get('pace_drivers', 0.3)
    )

    tpi_df = tpi_df.sort_values(by='TPI', ascending=False).reset_index(drop=True)
    tpi_df['Rank'] = tpi_df.index + 1
    tpi_df['Date'] = datetime.now().strftime('%Y%m%d')
    tpi_df = tpi_df[['Rank', 'team', 'TPI', 'offensive_creation', 'defensive_resistance', 'pace_drivers', 'Date']]

    for col in ['TPI', 'offensive_creation', 'defensive_resistance', 'pace_drivers']:
        tpi_df[col] = tpi_df[col].round(4)

    print(f"  -> TPI Rankings: {len(tpi_df)} teams.")
    return tpi_df

def calculate_bucket_zscores(z_overall_df, config):
    print("\n--- Calculating Bucket-Level Z-Scores ---")
    bucket_weights = config.get('bucket_weights', {
        'offensive_creation': 0.4, 'defensive_resistance': 0.3, 'pace_drivers': 0.3
    })

    stat_to_bucket = {}
    for provider in config.get('providers', []):
        for file_info in provider.get('files', []):
            for stat in file_info.get('stats', []):
                stat_to_bucket[stat['name']] = stat.get('bucket', 'unknown')

    z_overall_df['bucket'] = z_overall_df['stat'].map(stat_to_bucket)
    bucket_dfs = []

    for bucket_name in ['offensive_creation', 'defensive_resistance', 'pace_drivers']:
        bucket_data = z_overall_df[z_overall_df['bucket'] == bucket_name].copy()
        if len(bucket_data) == 0:
            continue

        bucket_stats = bucket_data['stat'].unique()
        stat_weights = {}
        for provider in config.get('providers', []):
            for file_info in provider.get('files', []):
                for stat in file_info.get('stats', []):
                    if stat['name'] in bucket_stats:
                        stat_weights[stat['name']] = stat.get('weight', 1.0)

        bucket_data['stat_weight'] = bucket_data['stat'].map(stat_weights)
        bucket_data['weighted_zscore'] = bucket_data['zscore'] * bucket_data['stat_weight']
        bucket_avg = bucket_data.groupby('team').agg({
            'weighted_zscore': 'sum', 'stat_weight': 'sum'
        }).reset_index()
        bucket_avg['zscore'] = bucket_avg['weighted_zscore'] / bucket_avg['stat_weight']
        bucket_avg['rank'] = bucket_avg['zscore'].rank(method='min', ascending=False)
        bucket_avg['stat'] = f"{bucket_name}_avg"
        bucket_avg['value'] = bucket_avg['zscore']
        bucket_avg['bucket'] = bucket_name
        bucket_avg = bucket_avg[['team', 'stat', 'value', 'zscore', 'rank', 'bucket']]
        bucket_dfs.append(bucket_avg)
        print(f"  -> {bucket_name}: {len(bucket_avg)} teams.")

    bucket_combined = pd.concat(bucket_dfs, ignore_index=True)
    return bucket_combined

def process_hockey_reference_file(file_info, file_path, canonical_teams, team_name_mappings):
    print(f"\nProcessing hockey-reference: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=file_info['header_row'])
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return None

    if len(df.columns) > 1:
        df.rename(columns={df.columns[1]: 'Team'}, inplace=True)
        print(f"  -> Renamed col[1] → 'Team'.")

    rows_to_exclude = file_info.get('rows_to_exclude', [])
    if rows_to_exclude and 'Team' in df.columns:
        df = df[~df['Team'].isin(rows_to_exclude)].reset_index(drop=True)

    if 'Team' not in df.columns or not validate_teams(df, canonical_teams, team_name_mappings):
        return None

    stats_for_this_file = file_info.get('stats', [])
    stat_names = [s['name'] for s in stats_for_this_file]
    required_cols = ['Team'] + stat_names
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"  -> Missing cols: {missing}")
        return None

    reduced_df = df[required_cols].copy()
    return process_stats_batch(reduced_df, stats_for_this_file)

def process_nhl_com_file(file_info, file_path, canonical_teams, team_name_mappings):
    print(f"\nProcessing nhl.com: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=file_info.get('header_row', 0))
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return None

    if 'Team' not in df.columns or not validate_teams(df, canonical_teams, team_name_mappings):
        return None

    stats_for_this_file = file_info.get('stats', [])
    stat_names = [s['name'] for s in stats_for_this_file]
    required_cols = ['Team'] + stat_names
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"  -> Missing cols: {missing}")
        return None

    reduced_df = df[required_cols].copy()
    return process_stats_batch(reduced_df, stats_for_this_file)

def perform_sanity_checks(df):
    print("\n--- Sanity Checks ---")
    team_counts = df.groupby('team')['stat'].count()
    stat_counts = df.groupby('stat')['team'].count()

    print("\n1. Stats per Team:")
    print(team_counts)
    print("\n2. Teams per Stat:")
    print(stat_counts)

    if team_counts.nunique() == 1:
        print(f"  -> PASSED: All teams have {team_counts.iloc[0]} stats.")
    else:
        print("  -> WARNING: Inconsistent stats per team!")

    if (stat_counts == 32).all():
        print(f"  -> PASSED: All {len(stat_counts)} stats have 32 teams.")
    else:
        print("  -> WARNING: Some stats missing teams!")

# ================================
# MAIN + GOI INTEGRATION
# ================================
def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config_v2.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: config_v2.yaml not found at {config_path}")
        sys.exit(1)

    file_list = get_and_verify_file_paths(config)
    if not file_list:
        print("\nMissing files. Exiting.")
        sys.exit(1)

    canonical_teams = set(config.get('canonical_teams', []))
    team_name_mappings = config.get('team_name_mappings', [])
    if not canonical_teams:
        print("ERROR: 'canonical_teams' missing in config.")
        sys.exit(1)

    all_final_dfs = []
    for file_to_process in file_list:
        provider_name = file_to_process['provider_name']
        file_path = file_to_process['file_path']
        file_info = file_to_process['file_info']

        if provider_name == "hockey-reference.com":
            dfs = process_hockey_reference_file(file_info, file_path, canonical_teams, team_name_mappings)
        elif provider_name == "nhl.com":
            dfs = process_nhl_com_file(file_info, file_path, canonical_teams, team_name_mappings)
        else:
            continue

        if dfs:
            all_final_dfs.extend(dfs)

    if not all_final_dfs:
        print("\nNo data processed.")
        sys.exit(0)

    # Combine all stats
    z_overall_df = pd.concat(all_final_dfs, ignore_index=True)
    bucket_df = calculate_bucket_zscores(z_overall_df, config)
    bucket_aligned = bucket_df[['team', 'stat', 'value', 'zscore', 'rank']].copy()
    z_overall_df = pd.concat([z_overall_df, bucket_aligned], ignore_index=True)
    z_overall_df = z_overall_df.sort_values(by='zscore', ascending=False).reset_index(drop=True)
    z_overall_df['zOverallRank'] = z_overall_df.index + 1
    z_overall_df['Date'] = datetime.now().strftime('%Y%m%d')
    z_overall_df = z_overall_df[['zOverallRank', 'Date', 'team', 'stat', 'value', 'zscore', 'rank']]

    perform_sanity_checks(z_overall_df)
    z_overall_output_path = os.path.join(os.path.dirname(__file__), 'zOverall.csv')
    z_overall_df.to_csv(z_overall_output_path, index=False)
    print(f"\n→ zOverall.csv created: {len(z_overall_df)} rows")

    # === GOI GUARDRAILS INPUTS (YOU PROVIDE THESE) ===
    # Example structure — replace with your data loader
    games_played_dict = {team: 6 for team in z_overall_df['team'].unique()}  # ← UPDATE
    opp_goalie_last3_sv = {"Columbus Blue Jackets": 0.957}  # ← UPDATE
    market_lines = {
        "Columbus Blue Jackets": {"ml": 145, "close_move": 0.25},
        "Washington Capitals": {"ml": -190, "close_move": -0.25}
    }  # ← UPDATE

    # Apply GOI v2.1
    z_overall_df = apply_goi_guardrails(
        z_overall_df, config, games_played_dict, opp_goalie_last3_sv, market_lines
    )

    # Save GOI-enhanced version
    goi_output_path = os.path.join(os.path.dirname(__file__), 'zOverall_GOI_v2.1.csv')
    z_overall_df.to_csv(goi_output_path, index=False)
    print(f"→ zOverall_GOI_v2.1.csv created with guardrails applied")

    # TPI & Rankings (unchanged)
    try:
        tpi_rankings = create_tpi_rankings(z_overall_df, config)
        tpi_rankings_output_path = os.path.join(os.path.dirname(__file__), 'tpi_rankings.csv')
        tpi_rankings.to_csv(tpi_rankings_output_path, index=False)
        print(f"→ tpi_rankings.csv created")
    except Exception as e:
        print(f"ERROR in TPI: {e}")

    print(f"\nGOI {GOI_VERSION} Pipeline Complete.")

if __name__ == "__main__":
    main()
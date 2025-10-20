import os
import sys
import pandas as pd
from scipy.stats import zscore
import numpy as np
import yaml
import fnmatch
from unidecode import unidecode as ud
from datetime import datetime

def get_and_verify_file_paths(config):
    """
    Builds and verifies the full paths for all required data files.

    Args:
        config (dict): The loaded configuration dictionary.

    Returns:
        list: A list of file metadata objects if all files are found, otherwise None.
    """
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
    """
    Validates the list of teams from a file against the canonical list.

    Args:
        teams_from_file (pd.Series): The 'Team' column from the DataFrame.
        canonical_teams (set): The set of canonical team names from the config.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    # Create a copy to work with
    working_teams = teams_from_file.copy()

    # 1. Apply pattern-based mapping rules first to the raw names
    for i, team_name in working_teams.items():
        original_name = str(team_name)
        for rule in team_name_mappings:
            if fnmatch.fnmatch(original_name, rule['pattern']):
                working_teams.at[i] = rule['replacement']
                print(f"    - Mapped '{original_name}' to '{rule['replacement']}' based on pattern '{rule['pattern']}'.")
                break # Rule applied, move to the next team name

    # 2. Apply unidecode and strip whitespace as the final cleaning step
    cleaned_teams = working_teams.apply(lambda s: ud(str(s)).strip() if pd.notnull(s) else s)
    df['Team'] = cleaned_teams # Update the DataFrame in place

    # 3. Perform the final validation
    final_unknown = set(cleaned_teams) - canonical_teams
    if final_unknown:
        print(f"  -> VALIDATION FAILED: Uncorrectable team names found: {final_unknown}")
        return False

    if len(set(cleaned_teams)) != 32:
        print(f"  -> VALIDATION FAILED: Expected 32 unique teams after correction, but found {len(set(cleaned_teams))}.")
        return False

    print("  -> Team validation PASSED after applying mapping rules.")
    return True

def process_stats_batch(df, stats_config):
    """
    Takes a clean, wide DataFrame and processes a batch of stats from it.

    Args:
        df (pd.DataFrame): The clean DataFrame with a 'Team' column and stat columns.
        stats_config (list): The list of stat configuration dictionaries from the YAML.

    Returns:
        list: A list of standardized, single-stat, vertical DataFrames.
    """
    all_stat_dfs = []
    
    stat_names_to_process = [stat['name'] for stat in stats_config]
    print(f"  -> Batch processing stats: {stat_names_to_process}")

    # Efficiently calculate z-scores for all relevant columns at once
    for stat_name in stat_names_to_process:
        if stat_name in df.columns:
            df[f'{stat_name}_zscore'] = zscore(df[stat_name], nan_policy='omit')

    # Now, loop through the config again to create the vertical DataFrames
    for stat_cfg in stats_config:
        stat_name = stat_cfg['name']
        zscore_col = f'{stat_name}_zscore'

        if zscore_col not in df.columns:
            print(f"  -> WARNING: Stat '{stat_name}' not found in DataFrame. Skipping.")
            continue

        # Create a temporary DataFrame for this stat
        stat_df = df[['Team', stat_name, zscore_col]].copy()
        
        # Handle sign reversal for stats where lower is better (e.g., Goals Against)
        if stat_cfg.get('reverse_sign', False):
            stat_df[zscore_col] = stat_df[zscore_col] * -1
            print(f"    - Reversed sign for '{stat_name}'.")

        # Determine sort order for ranking
        ascending = stat_cfg.get('sort_order', 'desc') == 'asc'
        
        # Calculate rank based on the (potentially reversed) z-score
        stat_df['rank'] = stat_df[zscore_col].rank(method='min', ascending=not ascending)
        
        # Rename columns to the final standardized vertical format
        stat_df.rename(columns={
            'Team': 'team',
            stat_name: 'value',
            zscore_col: 'zscore'
        }, inplace=True)
        
        # Add the stat name as a new column
        stat_df['stat'] = stat_name
        
        # Reorder columns to match the final output format
        final_stat_df = stat_df[['team', 'stat', 'value', 'zscore', 'rank']]
        
        print(f"    - Processed vertical DataFrame for '{stat_name}'.")
        all_stat_dfs.append(final_stat_df)

    print(f"  -> Batch processing complete. Generated {len(all_stat_dfs)} stat DataFrames.")
    return all_stat_dfs

def process_hockey_reference_file(file_info, file_path, canonical_teams, team_name_mappings):
    """
    Loads and standardizes a file from hockey-reference.com.
    """
    print(f"\nProcessing hockey-reference file: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=file_info['header_row'])
    except Exception as e:
        print(f"  -> ERROR: Failed to read Excel file: {e}")
        return None

    if len(df.columns) > 1:
        df.rename(columns={df.columns[1]: 'Team'}, inplace=True)
        print(f"  -> Renamed second column to 'Team'.")

    rows_to_exclude = file_info.get('rows_to_exclude', [])
    if rows_to_exclude and 'Team' in df.columns:
        original_rows = len(df)
        df = df[~df['Team'].isin(rows_to_exclude)].reset_index(drop=True)
        if len(df) < original_rows:
            print(f"  -> Removed {original_rows - len(df)} rows based on 'rows_to_exclude' config.")

    if 'Team' not in df.columns:
        print("  -> VALIDATION FAILED: 'Team' column not found.")
        return None
    
    if not validate_teams(df, canonical_teams, team_name_mappings):
        return None

    # Reduce the DataFrame to only the 'Team' column and the stats needed for this file
    stats_for_this_file = file_info.get('stats', [])
    stat_names = [stat['name'] for stat in stats_for_this_file]
    required_cols = ['Team'] + stat_names
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"  -> ERROR: The following required stat columns are missing from the file: {missing_cols}")
        print(f"     Available columns are: {list(df.columns)}")
        return None

    reduced_df = df[required_cols].copy()
    print("  -> Reduced DataFrame to required columns. Head:")
    print(reduced_df.head())

    # Pass the clean, reduced DataFrame to the generic batch processor
    return process_stats_batch(reduced_df, stats_for_this_file)

def process_nhl_com_file(file_info, file_path, canonical_teams, team_name_mappings):
    """
    Loads and standardizes a file from nhl.com.
    """
    print(f"\nProcessing nhl.com file: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=file_info.get('header_row', 0))
    except Exception as e:
        print(f"  -> ERROR: Failed to read Excel file: {e}")
        return None

    # These files are clean, but team names need validation
    if 'Team' not in df.columns:
        print("  -> VALIDATION FAILED: 'Team' column not found.")
        return None
    
    if not validate_teams(df, canonical_teams, team_name_mappings):
        return None

    # Reduce the DataFrame to only the 'Team' column and the stats needed for this file
    stats_for_this_file = file_info.get('stats', [])
    stat_names = [stat['name'] for stat in stats_for_this_file]
    required_cols = ['Team'] + stat_names
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"  -> ERROR: The following required stat columns are missing from the file: {missing_cols}")
        print(f"     Available columns are: {list(df.columns)}")
        return None

    reduced_df = df[required_cols].copy()
    print("  -> Reduced DataFrame to required columns. Head:")
    print(reduced_df.head())

    # Pass the clean, reduced DataFrame to the generic batch processor
    return process_stats_batch(reduced_df, stats_for_this_file)

def perform_sanity_checks(df):
    """
    Performs and prints data integrity checks on the final DataFrame.
    """
    print("\n--- Performing Sanity Checks ---")

    # 1. Count stats per team
    team_counts = df.groupby('team')['stat'].count()
    print("\n1. Stats per Team (should all be the same):")
    print(team_counts)

    # 2. Count teams per stat
    stat_counts = df.groupby('stat')['team'].count()
    print("\n2. Teams per Stat (should all be 32):")
    print(stat_counts)

    # Check for inconsistencies
    if team_counts.nunique() != 1:
        print("\n  -> WARNING: Inconsistent number of stats across teams!")
    else:
        print(f"\n  -> PASSED: All {len(team_counts)} teams have {team_counts.iloc[0]} stats.")

    if (stat_counts != 32).any():
        print("\n  -> WARNING: Some stats do not have 32 teams!")
    else:
        print(f"\n  -> PASSED: All {len(stat_counts)} stats have 32 teams.")

    print("\n--- Sanity Checks Complete ---")

def main():
    """
    Main function to orchestrate the z-score calculation pipeline.
    """
    config_path = os.path.join(os.path.dirname(__file__), 'config_v2.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at {config_path}")
        sys.exit(1)

    # Get and verify the list of files to process.
    file_list = get_and_verify_file_paths(config)
    if not file_list:
        print("\nOne or more required data files are missing. Exiting.")
        sys.exit(1)
    else:
        print("\nAll required data files found. Proceeding...")

    # Load canonical teams and mappings for validation
    canonical_teams = set(config.get('canonical_teams', []))
    team_name_mappings = config.get('team_name_mappings', [])
    if not canonical_teams:
        print("ERROR: 'canonical_teams' list not found or empty in config. Exiting.")
        sys.exit(1)

    all_final_dfs = []

    # --- Main Processing Loop ---
    for file_to_process in file_list:
        provider_name = file_to_process['provider_name']
        file_path = file_to_process['file_path']
        file_info = file_to_process['file_info']

        list_of_stat_dfs = None
        if provider_name == "hockey-reference.com":
            list_of_stat_dfs = process_hockey_reference_file(file_info, file_path, canonical_teams, team_name_mappings)
        elif provider_name == "nhl.com":
            list_of_stat_dfs = process_nhl_com_file(file_info, file_path, canonical_teams, team_name_mappings)
        else:
            print(f"\nWARNING: No processor found for provider '{provider_name}'.")

        if list_of_stat_dfs:
            all_final_dfs.extend(list_of_stat_dfs)

    print(f"\n\nPipeline complete. Total vertical DataFrames created: {len(all_final_dfs)}")

    # --- Final Output Generation ---
    if not all_final_dfs:
        print("\nNo data was processed. Exiting without creating output files.")
        sys.exit(0)

    # 1. Create the zOverall.csv file
    try:
        z_overall_df = pd.concat(all_final_dfs, ignore_index=True)

        # Perform sanity checks on the final combined data
        perform_sanity_checks(z_overall_df)
        z_overall_output_path = os.path.join(os.path.dirname(__file__), 'zOverall.csv')
        z_overall_df.to_csv(z_overall_output_path, index=False)
        print(f"\nSuccessfully created '{os.path.basename(z_overall_output_path)}' with {len(z_overall_df)} rows.")
    except Exception as e:
        print(f"\nERROR: Failed to create zOverall.csv: {e}")
        return # Stop processing if we can't create the main file

    # 2. Create the team_total_zscores.csv file
    try:
        stat_weight_map = {}
        for provider in config.get('providers', []):
            for file_info in provider.get('files', []):
                for stat in file_info.get('stats', []):
                    stat_weight_map[stat['name']] = stat.get('weight', 1.0)

        z_overall_df['weighted_zscore'] = z_overall_df.apply(
            lambda row: row['zscore'] * stat_weight_map.get(row['stat'], 1.0), axis=1
        )

        team_totals = z_overall_df.groupby('team')['weighted_zscore'].sum().reset_index()
        team_totals.rename(columns={'weighted_zscore': 'zTotal'}, inplace=True)
        team_totals = team_totals.sort_values(by='zTotal', ascending=False).reset_index(drop=True)

        team_totals_output_path = os.path.join(os.path.dirname(__file__), 'team_total_zscores.csv')
        team_totals.to_csv(team_totals_output_path, index=False)
        print(f"Successfully created '{os.path.basename(team_totals_output_path)}' with {len(team_totals)} teams.")
    except Exception as e:
        print(f"\nERROR: Failed to create team_total_zscores.csv: {e}")

if __name__ == "__main__":
    main()

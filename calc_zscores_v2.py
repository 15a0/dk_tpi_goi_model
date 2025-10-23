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

        # Calculate rank based on the (potentially reversed) z-score.
        # We ALWAYS rank in descending order of z-score, because a higher z-score is always better.
        stat_df['rank'] = stat_df[zscore_col].rank(method='min', ascending=False)
        
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

def create_tpi_rankings(z_overall_df, config):
    """
    Creates a TPI (Team DFS Power Index) rankings file with bucket breakdowns.
    
    Args:
        z_overall_df (pd.DataFrame): The combined DataFrame with all stats and bucket averages.
        config (dict): The configuration dictionary containing bucket_weights.
    
    Returns:
        pd.DataFrame: A DataFrame with TPI rankings and bucket scores.
    """
    print("\n--- Creating TPI Rankings ---")
    
    # Extract only bucket average rows
    bucket_rows = z_overall_df[z_overall_df['stat'].str.contains('_avg', na=False)].copy()
    
    # Pivot to get one row per team with columns for each bucket
    tpi_df = bucket_rows.pivot_table(
        index='team',
        columns='stat',
        values='zscore',
        aggfunc='first'
    ).reset_index()
    
    # Rename columns for clarity
    tpi_df.rename(columns={
        'offensive_creation_avg': 'offensive_creation',
        'defensive_resistance_avg': 'defensive_resistance',
        'pace_drivers_avg': 'pace_drivers'
    }, inplace=True)
    
    # Get bucket weights from config
    bucket_weights = config.get('bucket_weights', {
        'offensive_creation': 0.4,
        'defensive_resistance': 0.3,
        'pace_drivers': 0.3
    })
    
    # Calculate TPI as weighted sum of bucket averages
    tpi_df['TPI'] = (
        tpi_df['offensive_creation'] * bucket_weights.get('offensive_creation', 0.4) +
        tpi_df['defensive_resistance'] * bucket_weights.get('defensive_resistance', 0.3) +
        tpi_df['pace_drivers'] * bucket_weights.get('pace_drivers', 0.3)
    )
    
    # Sort by TPI descending and add rank
    tpi_df = tpi_df.sort_values(by='TPI', ascending=False).reset_index(drop=True)
    tpi_df['Rank'] = tpi_df.index + 1
    
    # Add date
    tpi_df['Date'] = datetime.now().strftime('%Y%m%d')
    
    # Reorder columns for readability
    tpi_df = tpi_df[[
        'Rank', 'team', 'TPI',
        'offensive_creation', 'defensive_resistance', 'pace_drivers',
        'Date'
    ]]
    
    # Round z-scores to 4 decimal places for readability
    for col in ['TPI', 'offensive_creation', 'defensive_resistance', 'pace_drivers']:
        tpi_df[col] = tpi_df[col].round(4)
    
    print(f"  -> TPI Rankings created for {len(tpi_df)} teams.")
    return tpi_df

def calculate_bucket_zscores(z_overall_df, config):
    """
    Calculates weighted average z-scores per bucket per team.
    
    Args:
        z_overall_df (pd.DataFrame): The combined DataFrame with all individual stat z-scores.
        config (dict): The configuration dictionary containing bucket_weights.
    
    Returns:
        pd.DataFrame: A DataFrame with bucket-level z-scores and ranks.
    """
    print("\n--- Calculating Bucket-Level Z-Scores ---")
    
    bucket_weights = config.get('bucket_weights', {
        'offensive_creation': 0.4,
        'defensive_resistance': 0.3,
        'pace_drivers': 0.3
    })
    
    # Build a stat-to-bucket mapping from config
    stat_to_bucket = {}
    for provider in config.get('providers', []):
        for file_info in provider.get('files', []):
            for stat in file_info.get('stats', []):
                stat_name = stat['name']
                bucket = stat.get('bucket', 'unknown')
                stat_to_bucket[stat_name] = bucket
    
    # Add bucket column to z_overall_df
    z_overall_df['bucket'] = z_overall_df['stat'].map(stat_to_bucket)
    
    bucket_dfs = []
    
    for bucket_name in ['offensive_creation', 'defensive_resistance', 'pace_drivers']:
        # Filter to this bucket's stats
        bucket_data = z_overall_df[z_overall_df['bucket'] == bucket_name].copy()
        
        if len(bucket_data) == 0:
            print(f"  -> WARNING: No stats found for bucket '{bucket_name}'. Skipping.")
            continue
        
        # Calculate weighted average z-score per team
        # Get weights for stats in this bucket
        bucket_stats = bucket_data['stat'].unique()
        stat_weights = {}
        for provider in config.get('providers', []):
            for file_info in provider.get('files', []):
                for stat in file_info.get('stats', []):
                    if stat['name'] in bucket_stats:
                        stat_weights[stat['name']] = stat.get('weight', 1.0)
        
        # Add weight column
        bucket_data['stat_weight'] = bucket_data['stat'].map(stat_weights)
        
        # Calculate weighted z-score
        bucket_data['weighted_zscore'] = bucket_data['zscore'] * bucket_data['stat_weight']
        
        # Group by team and calculate weighted average
        bucket_avg = bucket_data.groupby('team').agg({
            'weighted_zscore': 'sum',
            'stat_weight': 'sum'
        }).reset_index()
        
        # Normalize by total weight
        bucket_avg['zscore'] = bucket_avg['weighted_zscore'] / bucket_avg['stat_weight']
        
        # Calculate rank within bucket
        bucket_avg['rank'] = bucket_avg['zscore'].rank(method='min', ascending=False)
        
        # Create output row
        bucket_avg['stat'] = f"{bucket_name}_avg"
        bucket_avg['value'] = bucket_avg['zscore']  # For consistency
        bucket_avg['bucket'] = bucket_name
        
        # Select and reorder columns to match z_overall_df format
        bucket_avg = bucket_avg[['team', 'stat', 'value', 'zscore', 'rank', 'bucket']]
        
        print(f"  -> Calculated {bucket_name}: {len(bucket_avg)} teams.")
        bucket_dfs.append(bucket_avg)
    
    # Combine all bucket DataFrames
    bucket_combined = pd.concat(bucket_dfs, ignore_index=True)
    print(f"  -> Bucket calculation complete. Generated {len(bucket_combined)} bucket rows.")
    
    return bucket_combined

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

        # Calculate bucket-level z-scores
        bucket_df = calculate_bucket_zscores(z_overall_df, config)
        
        # Append bucket rows to z_overall_df
        # Ensure columns match before concatenating
        bucket_df_aligned = bucket_df[['team', 'stat', 'value', 'zscore', 'rank']].copy()
        z_overall_df = pd.concat([z_overall_df, bucket_df_aligned], ignore_index=True)

        # Sort, add rank, and add date as requested
        z_overall_df = z_overall_df.sort_values(by='zscore', ascending=False).reset_index(drop=True)
        z_overall_df['zOverallRank'] = z_overall_df.index + 1
        z_overall_df['Date'] = datetime.now().strftime('%Y%m%d')

        # Reorder columns
        z_overall_df = z_overall_df[['zOverallRank', 'Date', 'team', 'stat', 'value', 'zscore', 'rank']]

        # Perform sanity checks on the final combined data
        perform_sanity_checks(z_overall_df)
        z_overall_output_path = os.path.join(os.path.dirname(__file__), 'zOverall.csv')
        z_overall_df.to_csv(z_overall_output_path, index=False)
        print(f"\nSuccessfully created '{os.path.basename(z_overall_output_path)}' with {len(z_overall_df)} rows.")
    except Exception as e:
        print(f"\nERROR: Failed to create zOverall.csv: {e}")
        return # Stop processing if we can't create the main file

    # 2. Create the team_total_zscores.csv file (TPI - Team DFS Power Index)
    try:
        # Use ONLY bucket averages for TPI calculation
        bucket_rows = z_overall_df[z_overall_df['stat'].str.contains('_avg', na=False)].copy()
        
        # Get bucket weights from config
        bucket_weights = config.get('bucket_weights', {
            'offensive_creation': 0.4,
            'defensive_resistance': 0.3,
            'pace_drivers': 0.3
        })
        
        # Map stat names to bucket names and apply weights
        def get_bucket_weight(stat_name):
            if 'offensive_creation' in stat_name:
                return bucket_weights.get('offensive_creation', 0.4)
            elif 'defensive_resistance' in stat_name:
                return bucket_weights.get('defensive_resistance', 0.3)
            elif 'pace_drivers' in stat_name:
                return bucket_weights.get('pace_drivers', 0.3)
            return 1.0
        
        bucket_rows['bucket_weight'] = bucket_rows['stat'].apply(get_bucket_weight)
        bucket_rows['weighted_zscore'] = bucket_rows['zscore'] * bucket_rows['bucket_weight']
        
        # Calculate TPI as weighted sum of bucket averages
        team_totals = bucket_rows.groupby('team')['weighted_zscore'].sum().reset_index()
        team_totals.rename(columns={'weighted_zscore': 'zTotal'}, inplace=True)
        team_totals = team_totals.sort_values(by='zTotal', ascending=False).reset_index(drop=True)

        # Add Rank and Date columns
        team_totals['Rank'] = team_totals.index + 1
        team_totals['Date'] = datetime.now().strftime('%Y%m%d')

        # Reorder columns to have Rank first
        team_totals = team_totals[['Rank', 'team', 'zTotal', 'Date']]

        team_totals_output_path = os.path.join(os.path.dirname(__file__), 'team_total_zscores.csv')
        team_totals.to_csv(team_totals_output_path, index=False)
        print(f"Successfully created '{os.path.basename(team_totals_output_path)}' with {len(team_totals)} teams (TPI = Team DFS Power Index).")
    except Exception as e:
        print(f"\nERROR: Failed to create team_total_zscores.csv: {e}")

    # 3. Create the tpi_rankings.csv file (detailed TPI with bucket breakdowns)
    try:
        tpi_rankings = create_tpi_rankings(z_overall_df, config)
        tpi_rankings_output_path = os.path.join(os.path.dirname(__file__), 'tpi_rankings.csv')
        tpi_rankings.to_csv(tpi_rankings_output_path, index=False)
        print(f"Successfully created '{os.path.basename(tpi_rankings_output_path)}' with {len(tpi_rankings)} teams.")
    except Exception as e:
        print(f"\nERROR: Failed to create tpi_rankings.csv: {e}")

if __name__ == "__main__":
    main()

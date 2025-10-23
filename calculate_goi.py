import os
import pandas as pd
from datetime import datetime

def create_team_mapping():
    """
    Creates a mapping from full team names to abbreviations.
    """
    team_mapping = {
        'Anaheim Ducks': 'ANA',
        'Boston Bruins': 'BOS',
        'Buffalo Sabres': 'BUF',
        'Calgary Flames': 'CGY',
        'Carolina Hurricanes': 'CAR',
        'Chicago Blackhawks': 'CHI',
        'Colorado Avalanche': 'COL',
        'Columbus Blue Jackets': 'CBJ',
        'Dallas Stars': 'DAL',
        'Detroit Red Wings': 'DET',
        'Edmonton Oilers': 'EDM',
        'Florida Panthers': 'FLA',
        'Los Angeles Kings': 'LA',
        'Minnesota Wild': 'MIN',
        'Montreal Canadiens': 'MTL',
        'Nashville Predators': 'NSH',
        'New Jersey Devils': 'NJ',
        'New York Islanders': 'NYI',
        'New York Rangers': 'NYR',
        'Ottawa Senators': 'OTT',
        'Philadelphia Flyers': 'PHI',
        'Pittsburgh Penguins': 'PIT',
        'San Jose Sharks': 'SJ',
        'Seattle Kraken': 'SEA',
        'St. Louis Blues': 'STL',
        'Tampa Bay Lightning': 'TB',
        'Toronto Maple Leafs': 'TOR',
        'Utah Mammoth': 'UTA',
        'Vancouver Canucks': 'VAN',
        'Vegas Golden Knights': 'VGK',
        'Washington Capitals': 'WSH',
        'Winnipeg Jets': 'WPG'
    }
    return team_mapping

def calculate_goi(tpi_rankings, schedule):
    """
    Calculates Game Opportunity Index (GOI) for each game.
    
    Args:
        tpi_rankings (pd.DataFrame): DataFrame with TPI scores per team
        schedule (pd.DataFrame): DataFrame with game schedule
    
    Returns:
        pd.DataFrame: DataFrame with GOI calculations per game
    """
    print("\n--- Calculating Game Opportunity Index (GOI) ---")
    
    # Create a dictionary for quick TPI lookups
    tpi_dict = {}
    for idx, row in tpi_rankings.iterrows():
        tpi_dict[row['team']] = {
            'offensive_creation': row['offensive_creation'],
            'defensive_resistance': row['defensive_resistance'],
            'pace_drivers': row['pace_drivers']
        }
    
    goi_results = []
    
    for idx, game in schedule.iterrows():
        home_team = game['Home']
        away_team = game['Visitor']
        game_date = game['Date']
        
        # Skip if teams not in TPI data
        if home_team not in tpi_dict or away_team not in tpi_dict:
            print(f"  -> WARNING: Skipping game {game_date} - {away_team} @ {home_team} (team not found in TPI data)")
            continue
        
        # Get TPI components
        home_tpi = tpi_dict[home_team]
        away_tpi = tpi_dict[away_team]
        
        # Calculate offensive opportunities
        # Home offensive opportunity = Away's defensive resistance vs Home's offensive creation
        home_goi_offense = away_tpi['defensive_resistance'] - home_tpi['defensive_resistance']
        # Away offensive opportunity = Home's defensive resistance vs Away's offensive creation
        away_goi_offense = home_tpi['defensive_resistance'] - away_tpi['defensive_resistance']
        
        # Calculate pace opportunity (average of both teams' pace drivers)
        game_pace = (home_tpi['pace_drivers'] + away_tpi['pace_drivers']) / 2
        
        # Calculate total GOI per team (0.6 offense, 0.4 pace)
        home_goi = 0.6 * home_goi_offense + 0.4 * game_pace
        away_goi = 0.6 * away_goi_offense + 0.4 * game_pace
        
        # Total opportunity = sum of both teams' GOI
        total_opportunity = home_goi + away_goi
        
        goi_results.append({
            'Date': game_date,
            'Home': home_team,
            'Away': away_team,
            'Home_GOI': round(home_goi, 4),
            'Away_GOI': round(away_goi, 4),
            'Game_Pace': round(game_pace, 4),
            'Total_Opportunity': round(total_opportunity, 4)
        })
    
    goi_df = pd.DataFrame(goi_results)
    print(f"  -> Calculated GOI for {len(goi_df)} games.")
    return goi_df

def main():
    """
    Main function to orchestrate GOI calculation.
    """
    print("--- GOI (Game Opportunity Index) Calculator ---")
    
    # Load TPI rankings
    tpi_path = os.path.join(os.path.dirname(__file__), 'tpi_rankings.csv')
    try:
        tpi_rankings = pd.read_csv(tpi_path)
        print(f"\nLoaded TPI rankings: {len(tpi_rankings)} teams")
    except FileNotFoundError:
        print(f"ERROR: TPI rankings file not found at {tpi_path}")
        return
    
    # Load schedule
    schedule_path = os.path.join(os.path.dirname(__file__), 'schedule.csv')
    try:
        schedule = pd.read_csv(schedule_path)
        print(f"Loaded schedule: {len(schedule)} games")
    except FileNotFoundError:
        print(f"ERROR: Schedule file not found at {schedule_path}")
        return
    
    # Calculate GOI
    goi_df = calculate_goi(tpi_rankings, schedule)
    
    # Save GOI rankings
    goi_output_path = os.path.join(os.path.dirname(__file__), 'goi_rankings.csv')
    goi_df.to_csv(goi_output_path, index=False)
    print(f"\nSuccessfully created 'goi_rankings.csv' with {len(goi_df)} games.")
    
    # Display top 10 highest opportunity games
    print("\n--- Top 10 Highest Opportunity Games ---")
    top_10 = goi_df.nlargest(10, 'Total_Opportunity')[['Date', 'Away', 'Home', 'Away_GOI', 'Home_GOI', 'Total_Opportunity']]
    print(top_10.to_string(index=False))

if __name__ == "__main__":
    main()

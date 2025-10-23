import pandas as pd
import argparse
import datetime

def main():
    parser = argparse.ArgumentParser(description="Analyze GOI for specific DFS slate")
    parser.add_argument('--date', type=str, default=datetime.date.today().strftime('%Y-%m-%d'),
                        help="Date for the slate (YYYY-MM-DD). Defaults to today.")
    parser.add_argument('--games', type=str, default=None,
                        help="Comma-separated list of games as 'Home vs Away' (e.g., 'Dallas Stars vs Los Angeles Kings,Colorado Avalanche vs Carolina Hurricanes'). If omitted, uses all games on date.")
    args = parser.parse_args()

    # Load data
    goi_df = pd.read_csv('goi_rankings.csv')
    schedule_df = pd.read_csv('schedule.csv')

    # Filter by date first
    slate_df = goi_df[goi_df['Date'] == args.date].copy()

    if args.games:
        # Parse user games (normalize names)
        selected_games = [g.strip() for g in args.games.split(',')]
        filtered_rows = []
        for game in selected_games:
            # Handle both 'Home vs Away' and 'Away @ Home' formats
            if ' vs ' in game:
                parts = game.split(' vs ')
                home, away = parts[1].strip(), parts[0].strip()
            elif ' @ ' in game:
                parts = game.split(' @ ')
                away, home = parts[0].strip(), parts[1].strip()
            else:
                print(f"WARNING: Game '{game}' format not recognized. Use 'Away @ Home' or 'Home vs Away'.")
                continue
            
            # Find matching row (case-insensitive, partial match for flexibility)
            match = slate_df[(slate_df['Home'].str.contains(home, case=False, na=False, regex=False)) & 
                             (slate_df['Away'].str.contains(away, case=False, na=False, regex=False))]
            if not match.empty:
                filtered_rows.append(match.iloc[0])
            else:
                # Try reverse (in case user swapped order)
                match = slate_df[(slate_df['Away'].str.contains(home, case=False, na=False, regex=False)) & 
                                 (slate_df['Home'].str.contains(away, case=False, na=False, regex=False))]
                if not match.empty:
                    filtered_rows.append(match.iloc[0])
                else:
                    print(f"WARNING: Game '{game}' not found in GOI for {args.date}. Try format: 'Away @ Home' (e.g., 'Los Angeles Kings @ Dallas Stars')")
        
        if filtered_rows:
            slate_df = pd.DataFrame(filtered_rows)
        else:
            print(f"No games matched. Exiting.")
            return
    else:
        # Use all on date
        today_schedule = schedule_df[schedule_df['Date'] == args.date]
        if len(today_schedule) == 0:
            print(f"No games found on {args.date} in schedule.")
            return
        print(f"Found {len(today_schedule)} games on {args.date}. Analyzing all...\n")

    if slate_df.empty:
        print(f"No games found for {args.date}. Run calculate_goi.py with fresh data?")
        return

    # Sort by Total_Opportunity descending (best games first)
    slate_df = slate_df.sort_values('Total_Opportunity', ascending=False).reset_index(drop=True)

    # Add DFS-specific columns
    slate_df['Slate_Rank'] = slate_df.index + 1
    
    def get_stack_priority(row):
        if row['Away_GOI'] > 0.5:
            return f"HIGH: Stack {row['Away']}"
        elif row['Home_GOI'] > 0.5:
            return f"HIGH: Stack {row['Home']}"
        elif row['Game_Pace'] > 0.3:
            return "MEDIUM: Target PP/one-offs"
        else:
            return "LOW: Fade or value only"
    
    def get_dfs_insight(row):
        away_team = row['Away']
        home_team = row['Home']
        away_goi = row['Away_GOI']
        home_goi = row['Home_GOI']
        pace = row['Game_Pace']
        
        # Determine offensive edge
        if away_goi > 0.4:
            edge = f"{away_team} offense smash vs {home_team} defense"
        elif home_goi > 0.4:
            edge = f"{home_team} offense smash vs {away_team} defense"
        else:
            edge = "Balanced matchup"
        
        # Pace assessment
        pace_desc = "High pace (more events)" if pace > 0.3 else "Low pace (fewer events)"
        
        return f"{edge}. {pace_desc}. For limited LUs, prioritize stacks in HIGH games."
    
    slate_df['Stack_Priority'] = slate_df.apply(get_stack_priority, axis=1)
    slate_df['DFS_Insight'] = slate_df.apply(get_dfs_insight, axis=1)

    # Display
    print(f"\n{'='*150}")
    print(f"DFS SLATE ANALYSIS: {args.date} ({len(slate_df)} Games)")
    print(f"{'='*150}\n")
    
    display_cols = ['Slate_Rank', 'Away', 'Home', 'Away_GOI', 'Home_GOI', 'Game_Pace', 'Total_Opportunity', 'Stack_Priority']
    print(slate_df[display_cols].to_string(index=False))
    
    print(f"\n{'='*150}")
    print("DFS INSIGHTS:")
    print(f"{'='*150}\n")
    for idx, row in slate_df.iterrows():
        print(f"{int(row['Slate_Rank'])}. {row['Away']} @ {row['Home']}")
        print(f"   {row['Stack_Priority']}")
        print(f"   {row['DFS_Insight']}\n")

    # Save to CSV for records
    output_file = f'slate_analysis_{args.date}.csv'
    slate_df.to_csv(output_file, index=False)
    print(f"Saved detailed analysis to {output_file}")

if __name__ == "__main__":
    main()

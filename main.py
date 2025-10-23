import os
import subprocess
import sys
from datetime import datetime

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """Print formatted header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_menu(options):
    """Print menu options"""
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    print()

def run_script(script_name, description, args=""):
    """Run a Python script and handle errors"""
    print_header(f"Running: {description}")
    try:
        cmd = f"python {script_name} {args}".strip()
        print(f"Command: {cmd}\n")
        result = subprocess.run(cmd, shell=True, cwd=os.path.dirname(__file__))
        if result.returncode == 0:
            print(f"\n✅ {description} completed successfully!")
            return True
        else:
            print(f"\n❌ {description} failed with exit code {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def step_1_calculate_tpi():
    """Step 1: Calculate TPI from fresh stats"""
    print_header("STEP 1: Calculate Team DFS Power Index (TPI)")
    print("This step:")
    print("  • Loads fresh NHL stats from Excel files (20251023_nhl_*.xlsx)")
    print("  • Calculates z-scores for all 13 stats")
    print("  • Groups stats into 3 buckets: offensive_creation, defensive_resistance, pace_drivers")
    print("  • Outputs: zOverall.csv, team_total_zscores.csv, tpi_rankings.csv")
    print()
    
    confirm = input("Run TPI calculation? (y/n): ").strip().lower()
    if confirm == 'y':
        return run_script("calc_zscores_v2.py", "TPI Calculation")
    return False

def step_2_calculate_goi():
    """Step 2: Calculate GOI for all games"""
    print_header("STEP 2: Calculate Game Opportunity Index (GOI)")
    print("This step:")
    print("  • Loads tpi_rankings.csv (from Step 1)")
    print("  • Reads schedule.csv (all 1312 games)")
    print("  • Calculates GOI for each matchup using formula:")
    print("    - Offensive opportunity = opponent defense vs your offense")
    print("    - Pace = average of both teams' pace drivers")
    print("    - GOI = 0.6 × offense + 0.4 × pace")
    print("  • Outputs: goi_rankings.csv (all games ranked by Total_Opportunity)")
    print()
    
    confirm = input("Run GOI calculation? (y/n): ").strip().lower()
    if confirm == 'y':
        return run_script("calculate_goi.py", "GOI Calculation")
    return False

def step_3_analyze_slate():
    """Step 3: Analyze specific slate - interactive game selection"""
    print_header("STEP 3: Analyze DFS Slate")
    print("This step:")
    print("  • Loads goi_rankings.csv (from Step 2)")
    print("  • Shows all games for TODAY or TOMORROW")
    print("  • You select specific games interactively")
    print("  • Ranks by Total_Opportunity (best games first)")
    print("  • Adds DFS insights: Stack Priority, Matchup Rationale")
    print("  • Outputs: slate_analysis_[DATE].csv + console display")
    print()
    
    # Step 1: Choose date
    print("Which date?")
    print("  1. Today (2025-10-23)")
    print("  2. Tomorrow (2025-10-24)")
    print("  3. Back to main menu")
    print()
    
    date_choice = input("Select (1-3): ").strip()
    
    if date_choice == '1':
        target_date = "2025-10-23"
    elif date_choice == '2':
        target_date = "2025-10-24"
    elif date_choice == '3':
        return False
    else:
        print("Invalid choice.")
        return False
    
    # Step 2: Load games for that date
    print_header(f"Games on {target_date}")
    try:
        import pandas as pd
        goi_df = pd.read_csv('goi_rankings.csv')
        date_games = goi_df[goi_df['Date'] == target_date].sort_values('Total_Opportunity', ascending=False).reset_index(drop=True)
        
        if date_games.empty:
            print(f"No games found for {target_date}.")
            input("Press Enter to continue...")
            return False
        
        print(f"Found {len(date_games)} games on {target_date}\n")
        print("Select games by entering their numbers (comma-separated, e.g., 1,3,5)")
        print("Or type 'all' for all games, or 'done' to cancel.\n")
        
        # Display games
        for idx, row in date_games.iterrows():
            rank = idx + 1
            print(f"  {rank:2d}. {row['Away']:25s} @ {row['Home']:25s} | GOI: {row['Total_Opportunity']:7.4f}")
        
        print()
        user_input = input("Enter game numbers (1,3,5) or 'all' or 'done': ").strip().lower()
        
        if user_input == 'done' or user_input == '':
            print("Cancelled. Returning to menu.")
            return False
        
        if user_input == 'all':
            selected_games = date_games
        else:
            # Parse comma-separated numbers
            try:
                game_numbers = [int(x.strip()) - 1 for x in user_input.split(',')]
                selected_games = date_games.iloc[game_numbers]
            except (ValueError, IndexError):
                print("Invalid input. Returning to menu.")
                return False
        
        # Step 3: Build game string for analyze_slate.py
        games_str = ','.join([f"{row['Away']} @ {row['Home']}" for _, row in selected_games.iterrows()])
        
        # Step 4: Run analyze_slate.py with selected games
        print_header(f"Analyzing {len(selected_games)} games for {target_date}")
        return run_script("analyze_slate.py", f"Slate Analysis ({len(selected_games)} games)", f"--date {target_date} --games \"{games_str}\"")
    
    except Exception as e:
        print(f"Error: {e}")
        return False

def step_4_view_outputs():
    """Step 4: View output files"""
    print_header("STEP 4: View Output Files")
    print("Available outputs:")
    print()
    
    files = {
        "zOverall.csv": "All 288 stats (6 individual + 3 bucket averages per team)",
        "team_total_zscores.csv": "32 teams with TPI (Team DFS Power Index)",
        "tpi_rankings.csv": "32 teams with bucket breakdowns (offensive_creation, defensive_resistance, pace_drivers)",
        "goi_rankings.csv": "All 1312 games ranked by Total_Opportunity",
        "slate_analysis_*.csv": "Custom slate analysis (generated after Step 3)"
    }
    
    for i, (filename, description) in enumerate(files.items(), 1):
        print(f"  {i}. {filename}")
        print(f"     └─ {description}")
        print()
    
    print("Files are saved in: c:\\Users\\jhenk\\Documents\\GitProjects\\NHL2025DFS\\")
    print()
    input("Press Enter to return to menu...")
    return False

def main_menu():
    """Main orchestrator menu"""
    while True:
        clear_screen()
        print_header("NHL 2025 DFS MODEL - ORCHESTRATOR")
        print("Pipeline Overview:")
        print("  Step 1: Calculate TPI (Team DFS Power Index) from fresh stats")
        print("  Step 2: Calculate GOI (Game Opportunity Index) for all games")
        print("  Step 3: Analyze specific DFS slate (date or custom games)")
        print("  Step 4: View output files")
        print()
        print("Choose an action:")
        print()
        
        options = [
            "Step 1: Calculate TPI (Fresh Stats)",
            "Step 2: Calculate GOI (All Games)",
            "Step 3: Analyze DFS Slate",
            "Step 4: View Output Files",
            "Run Full Pipeline (Steps 1-2)",
            "Exit"
        ]
        
        print_menu(options)
        
        choice = input("Select (1-6): ").strip()
        
        if choice == '1':
            step_1_calculate_tpi()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            step_2_calculate_goi()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            step_3_analyze_slate()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            step_4_view_outputs()
        
        elif choice == '5':
            print_header("Running Full Pipeline")
            print("This will run Steps 1 and 2 sequentially...\n")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                success_1 = step_1_calculate_tpi()
                if success_1:
                    input("\nStep 1 complete. Press Enter to run Step 2...")
                    success_2 = step_2_calculate_goi()
                    if success_2:
                        print("\n✅ Full pipeline completed successfully!")
                        print("Next: Use Step 3 to analyze your DFS slate.")
                    else:
                        print("\n⚠️ Step 2 failed. Check the output above.")
                else:
                    print("\n⚠️ Step 1 failed. Check the output above.")
            input("\nPress Enter to continue...")
        
        elif choice == '6':
            print("\nExiting. Goodbye!")
            sys.exit(0)
        
        else:
            print("Invalid choice. Please try again.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

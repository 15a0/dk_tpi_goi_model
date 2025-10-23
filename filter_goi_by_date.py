import pandas as pd

# Load GOI rankings
goi_df = pd.read_csv('goi_rankings.csv')

# Filter to Oct 24, 2025
target_date = '2025-10-24'
oct24_games = goi_df[goi_df['Date'] == target_date].sort_values('Total_Opportunity', ascending=False)

print(f"\n--- OCT 24, 2025 SLATE (Tomorrow) ---")
print(f"Total games: {len(oct24_games)}\n")

if len(oct24_games) > 0:
    display_cols = ['Date', 'Away', 'Home', 'Away_GOI', 'Home_GOI', 'Total_Opportunity']
    print(oct24_games[display_cols].head(15).to_string(index=False))
else:
    print("No games found for Oct 24, 2025")
    print("\nAvailable dates in GOI data:")
    print(goi_df['Date'].unique()[:20])

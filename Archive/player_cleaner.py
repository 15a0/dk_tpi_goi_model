import pandas as pd
import os
import shutil
from datetime import datetime

ARCHIVE_FOLDER = "Archive"
CLEANED_FILE = "cleaned_players.csv"
EXCEL_FILE = "NHL2025.xlsx"
SHEET_NAME = "tblRawData"

def archive_existing_cleaned_file():
    if not os.path.exists(CLEANED_FILE):
        return  # Nothing to archive

    try:
        df_existing = pd.read_csv(CLEANED_FILE)
        if df_existing.empty:
            print("Existing cleaned file is empty. Skipping archive.")
            return

        raw_date = df_existing.iloc[0, 0]
        parsed_date = pd.to_datetime(raw_date, errors='coerce')

        if pd.isna(parsed_date):
            print(f"Could not parse date from first row: {raw_date}")
            return

        date_str = parsed_date.strftime("%Y%m%d")
        archive_name = f"{date_str}_cleaned_players.csv"
        archive_path = os.path.join(ARCHIVE_FOLDER, archive_name)

        os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
        shutil.move(CLEANED_FILE, archive_path)
        print(f"Archived existing cleaned file to: {archive_path}")

    except Exception as e:
        print(f"Error archiving existing cleaned file: {e}")

def clean_text_column(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)  # collapse multiple spaces
        .str.replace("\u00A0", " ")            # non-breaking space
        .str.replace("\u200B", "")             # zero-width space
        .str.normalize("NFKC")                 # Unicode normalization
    )

def clean_player_data():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

    # Clean relevant columns
    for col in ["Player", "Team"]:
        if col in df.columns:
            df[col] = clean_text_column(df[col])
        else:
            print(f"Warning: Column '{col}' not found in Excel sheet.")

    # Optional: sort and deduplicate
    df = df.sort_values("Player").drop_duplicates()

    # Save to clean CSV
    df.to_csv(CLEANED_FILE, index=False)
    print(f"Saved cleaned data to: {CLEANED_FILE}")

if __name__ == "__main__":
    archive_existing_cleaned_file()
    clean_player_data()

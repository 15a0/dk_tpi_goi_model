import pandas as pd

df = pd.read_excel("NHL2025.xlsx", sheet_name="tblRawData")

# Clean the Player column
df["Player"] = (
    df["Player"]
    .astype(str)
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)  # collapse multiple spaces
    .str.replace("\u00A0", " ")            # non-breaking space
    .str.replace("\u200B", "")             # zero-width space
    .str.normalize("NFKC")                 # Unicode normalization
)

# Optional: sort and deduplicate
df = df.sort_values("Player").drop_duplicates()

# Save to clean CSV
df.to_csv("cleaned_players.csv", index=False)

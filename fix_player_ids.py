import requests
import pandas as pd
import json
import os
from typing import Dict, Any, List, Tuple
import re

def fetch_sleeper_players() -> Dict[str, Any]:
    """Fetch all NFL players from Sleeper API"""
    print("Fetching players from Sleeper API...")
    url = "https://api.sleeper.app/v1/players/nfl"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()

def load_dynasty_rankings() -> pd.DataFrame:
    """Load the dynasty rankings CSV file"""
    print("Loading dynasty rankings...")
    if not os.path.exists("data/dynasty_rankings.csv"):
        raise FileNotFoundError("dynasty_rankings.csv not found in data directory")
    
    return pd.read_csv("data/dynasty_rankings.csv")

def normalize_name(name: str) -> str:
    """Normalize player name for better matching"""
    # Convert to lowercase
    name = name.lower()
    # Remove suffixes like "Jr.", "Sr.", "III", etc.
    name = re.sub(r'\s+(jr\.?|sr\.?|i{1,3}|iv)$', '', name)
    # Remove special characters and extra spaces
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def create_player_lookup(sleeper_players: Dict[str, Any]) -> Dict[Tuple[str, str], str]:
    """Create a lookup dictionary for players by normalized name and position"""
    print("Creating player lookup dictionary...")
    player_lookup = {}
    
    for player_id, player_data in sleeper_players.items():
        if not player_data.get("full_name") or not player_data.get("position"):
            continue
        
        name = player_data.get("full_name", "")
        if not name:
            name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip()
        
        position = player_data.get("position", "")
        team = player_data.get("team", "")
        
        # Create a normalized key for lookup
        normalized_name = normalize_name(name)
        key = (normalized_name, position)
        
        # Store the player ID with the key
        player_lookup[key] = player_id
        
        # Also try with just last name for cases where first names might differ
        last_name = player_data.get("last_name", "")
        if last_name:
            normalized_last_name = normalize_name(last_name)
            key_last_name = (normalized_last_name, position)
            # Only add if not already present to avoid overwriting full name matches
            if key_last_name not in player_lookup:
                player_lookup[key_last_name] = player_id
    
    return player_lookup

def fix_player_ids(rankings_df: pd.DataFrame, player_lookup: Dict[Tuple[str, str], str]) -> pd.DataFrame:
    """Fix player IDs in the rankings dataframe"""
    print("Fixing player IDs...")
    
    # Create a copy of the dataframe to avoid modifying the original
    fixed_df = rankings_df.copy()
    
    # Add a column to track if the player ID was updated
    fixed_df["id_updated"] = False
    
    # Track matches and misses
    matches = 0
    misses = 0
    
    # Iterate through each row in the rankings
    for idx, row in fixed_df.iterrows():
        name = row["name"]
        position = row["position"]
        
        # Normalize the name
        normalized_name = normalize_name(name)
        
        # Try to find a match in the lookup dictionary
        key = (normalized_name, position)
        
        if key in player_lookup:
            # Update the player ID
            fixed_df.at[idx, "player_id"] = player_lookup[key]
            fixed_df.at[idx, "id_updated"] = True
            matches += 1
        else:
            # Try with just the last name
            last_name = name.split()[-1]
            normalized_last_name = normalize_name(last_name)
            key_last_name = (normalized_last_name, position)
            
            if key_last_name in player_lookup:
                # Update the player ID
                fixed_df.at[idx, "player_id"] = player_lookup[key_last_name]
                fixed_df.at[idx, "id_updated"] = True
                matches += 1
            else:
                misses += 1
                print(f"No match found for: {name} ({position})")
    
    print(f"Total players: {len(fixed_df)}")
    print(f"Matches found: {matches}")
    print(f"Misses: {misses}")
    
    return fixed_df

def save_fixed_rankings(fixed_df: pd.DataFrame) -> None:
    """Save the fixed rankings to a new CSV file"""
    print("Saving fixed rankings...")
    
    # Remove the id_updated column before saving
    fixed_df = fixed_df.drop(columns=["id_updated"])
    
    # Save to a new file
    fixed_df.to_csv("data/dynasty_rankings_fixed.csv", index=False)
    print("Fixed rankings saved to data/dynasty_rankings_fixed.csv")
    
    # Also create a backup of the original file
    rankings_df = pd.read_csv("data/dynasty_rankings.csv")
    rankings_df.to_csv("data/dynasty_rankings_original.csv", index=False)
    print("Original rankings backed up to data/dynasty_rankings_original.csv")
    
    # Replace the original file with the fixed one
    fixed_df.to_csv("data/dynasty_rankings.csv", index=False)
    print("Original rankings file updated with fixed player IDs")

def main():
    try:
        # Fetch players from Sleeper API
        sleeper_players = fetch_sleeper_players()
        
        # Load dynasty rankings
        rankings_df = load_dynasty_rankings()
        
        # Create player lookup dictionary
        player_lookup = create_player_lookup(sleeper_players)
        
        # Fix player IDs
        fixed_df = fix_player_ids(rankings_df, player_lookup)
        
        # Save fixed rankings
        save_fixed_rankings(fixed_df)
        
        print("\nPlayer ID fixing completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()

import requests
import pandas as pd
import json
import os
from typing import Dict, Any

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

def compare_player_ids(sleeper_players: Dict[str, Any], rankings_df: pd.DataFrame) -> None:
    """Compare player IDs between Sleeper API and dynasty rankings"""
    print("\nComparing player IDs...\n")
    
    # Convert all player_ids in rankings to strings for consistent comparison
    rankings_df["player_id"] = rankings_df["player_id"].astype(str)
    
    # Get all player IDs from rankings
    ranking_player_ids = set(rankings_df["player_id"].tolist())
    
    # Get all player IDs from Sleeper API
    sleeper_player_ids = set(sleeper_players.keys())
    
    # Find player IDs in rankings that are not in Sleeper API
    missing_from_sleeper = ranking_player_ids - sleeper_player_ids
    
    # Find player IDs in Sleeper API that match our rankings
    matching_ids = ranking_player_ids.intersection(sleeper_player_ids)
    
    # Print results
    print(f"Total players in dynasty rankings: {len(ranking_player_ids)}")
    print(f"Total players in Sleeper API: {len(sleeper_player_ids)}")
    print(f"Number of matching player IDs: {len(matching_ids)}")
    print(f"Number of player IDs in rankings not found in Sleeper API: {len(missing_from_sleeper)}")
    
    # Print details of missing players
    if missing_from_sleeper:
        print("\nPlayers in rankings not found in Sleeper API:")
        for player_id in missing_from_sleeper:
            if player_id == 'nan' or player_id == '':
                continue
            player_row = rankings_df[rankings_df["player_id"] == player_id].iloc[0]
            print(f"  ID: {player_id}, Name: {player_row['name']}, Position: {player_row['position']}, Team: {player_row['team']}")
    
    # Save a sample of Sleeper player data for reference
    print("\nSaving sample of Sleeper player data for reference...")
    sample_size = min(10, len(sleeper_player_ids))
    sample_players = {player_id: sleeper_players[player_id] for player_id in list(sleeper_player_ids)[:sample_size]}
    
    with open("data/sleeper_players_sample.json", "w") as f:
        json.dump(sample_players, f, indent=2)
    
    print(f"Sample saved to data/sleeper_players_sample.json")
    
    # Save all Sleeper player IDs for reference
    with open("data/sleeper_player_ids.json", "w") as f:
        json.dump(list(sleeper_player_ids), f)
    
    print(f"All Sleeper player IDs saved to data/sleeper_player_ids.json")

def main():
    try:
        # Fetch players from Sleeper API
        sleeper_players = fetch_sleeper_players()
        
        # Load dynasty rankings
        rankings_df = load_dynasty_rankings()
        
        # Compare player IDs
        compare_player_ids(sleeper_players, rankings_df)
        
        print("\nComparison completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()

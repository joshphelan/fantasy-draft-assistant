import pandas as pd
import requests
import os
import json
import time
from typing import Dict, List, Any, Optional

def download_csv(url, filename):
    """
    Download a CSV file from a URL and save it locally.
    
    Args:
        url (str): URL to download from
        filename (str): Local filename to save to
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Downloading {filename} from {url}...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        print(f"Successfully downloaded {filename}")
        return True
    except Exception as e:
        print(f"Error downloading {filename}: {str(e)}")
        return False

def fetch_player_rankings():
    """
    Fetch player rankings from DynastyProcess values-players.csv.
    
    Returns:
        pd.DataFrame: DataFrame with player rankings
    """
    print("Fetching player rankings...")
    url = "https://github.com/dynastyprocess/data/raw/master/files/values-players.csv"
    local_file = "data/values-players.csv"
    
    if download_csv(url, local_file):
        try:
            df = pd.read_csv(local_file)
            # Extract relevant columns
            result = df[["player", "pos", "team", "value_1qb"]]
            result.columns = ["name", "position", "team", "rank_value"]
            
            # Normalize rank values to be 1-based
            result["rank_value"] = result["rank_value"].rank(ascending=False)
            
            print(f"Found {len(result)} players from DynastyProcess rankings")
            return result
        except Exception as e:
            print(f"Error processing rankings: {str(e)}")
    
    return pd.DataFrame()

def fetch_player_ids():
    """
    Fetch player IDs from DynastyProcess db_playerids.csv.
    
    Returns:
        pd.DataFrame: DataFrame with player IDs
    """
    print("Fetching player IDs...")
    url = "https://github.com/dynastyprocess/data/raw/master/files/db_playerids.csv"
    local_file = "data/db_playerids.csv"
    
    if download_csv(url, local_file):
        try:
            df = pd.read_csv(local_file)
            # Extract relevant columns
            if "sleeper_id" in df.columns:
                result = df[["name", "position", "team", "sleeper_id"]]
                result.columns = ["name", "position", "team", "player_id"]
                print(f"Found {len(result)} players with Sleeper IDs")
                return result
            else:
                print("Column 'sleeper_id' not found in the CSV file")
        except Exception as e:
            print(f"Error processing player IDs: {str(e)}")
    
    return pd.DataFrame()

def fetch_sleeper_players():
    """
    Fetch all NFL players from Sleeper API.
    
    Returns:
        dict: Dictionary of player data keyed by player_id
    """
    print("Fetching players from Sleeper API...")
    try:
        response = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=15)
        response.raise_for_status()
        players = response.json()
        print(f"Found {len(players)} players from Sleeper API")
        return players
    except Exception as e:
        print(f"Error fetching Sleeper players: {str(e)}")
        return {}

def merge_rankings_with_ids(rankings_df, ids_df, sleeper_players):
    """
    Merge rankings with player IDs and add metadata from Sleeper.
    
    Args:
        rankings_df (pd.DataFrame): DataFrame with player rankings
        ids_df (pd.DataFrame): DataFrame with player IDs
        sleeper_players (dict): Dictionary of Sleeper player data
        
    Returns:
        pd.DataFrame: Merged DataFrame with IDs and metadata
    """
    print("Merging rankings with player IDs...")
    
    # Normalize player names for better matching
    rankings_df["name_normalized"] = rankings_df["name"].str.lower().str.replace(r'[^\w\s]', '', regex=True)
    if not ids_df.empty:
        ids_df["name_normalized"] = ids_df["name"].str.lower().str.replace(r'[^\w\s]', '', regex=True)
    
    # Merge dataframes on normalized name and position
    if not ids_df.empty:
        merged_df = pd.merge(
            rankings_df,
            ids_df[["name_normalized", "position", "player_id"]],
            on=["name_normalized", "position"],
            how="left"
        )
    else:
        merged_df = rankings_df.copy()
        merged_df["player_id"] = None
    
    # Add bye week and status from Sleeper data
    merged_df["bye"] = 0
    merged_df["status"] = "Active"
    
    # Update metadata from Sleeper
    def update_metadata(row):
        player_id = row["player_id"]
        if pd.notna(player_id) and player_id in sleeper_players:
            player_data = sleeper_players[player_id]
            row["bye"] = player_data.get("bye_week", 0)
            row["status"] = player_data.get("status", "Active")
            # Update team if available
            if player_data.get("team"):
                row["team"] = player_data.get("team")
        return row
    
    if sleeper_players:
        merged_df = merged_df.apply(update_metadata, axis=1)
    
    # Drop the normalized name column
    merged_df = merged_df.drop(columns=["name_normalized"])
    
    # Reorder columns
    columns = ["player_id", "name", "position", "team", "rank_value", "bye", "status"]
    merged_df = merged_df[columns]
    
    print(f"Created merged rankings with {len(merged_df)} players")
    print(f"Players with Sleeper IDs: {merged_df['player_id'].notna().sum()}")
    
    return merged_df

def create_config(league_id, user_id=None):
    """
    Create or update the config.json file.
    
    Args:
        league_id (str): The Sleeper league ID
        user_id (str, optional): The Sleeper user ID
    """
    config_path = "config.json"
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {
            "roster_settings": {
                "QB": 1,
                "RB": 2,
                "WR": 3,
                "TE": 1,
                "FLEX": 2
            }
        }
    
    config["league_id"] = league_id
    if user_id:
        config["user_id"] = user_id
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Config saved to {config_path}")

def create_fallback_rankings():
    """
    Create a fallback rankings list with top players.
    
    Returns:
        pd.DataFrame: DataFrame with basic player rankings
    """
    print("Creating fallback rankings with top players...")
    
    # Top 150 players with approximate dynasty rankings
    players = [
        {"name": "Christian McCaffrey", "position": "RB", "team": "SF", "rank_value": 1},
        {"name": "CeeDee Lamb", "position": "WR", "team": "DAL", "rank_value": 2},
        {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN", "rank_value": 3},
        {"name": "Bijan Robinson", "position": "RB", "team": "ATL", "rank_value": 4},
        {"name": "Justin Jefferson", "position": "WR", "team": "MIN", "rank_value": 5},
        {"name": "Breece Hall", "position": "RB", "team": "NYJ", "rank_value": 6},
        {"name": "Saquon Barkley", "position": "RB", "team": "PHI", "rank_value": 7},
        {"name": "Amon-Ra St. Brown", "position": "WR", "team": "DET", "rank_value": 8},
        {"name": "Garrett Wilson", "position": "WR", "team": "NYJ", "rank_value": 9},
        {"name": "Puka Nacua", "position": "WR", "team": "LAR", "rank_value": 10},
        {"name": "Drake London", "position": "WR", "team": "ATL", "rank_value": 11},
        {"name": "Jahmyr Gibbs", "position": "RB", "team": "DET", "rank_value": 12},
        {"name": "Jonathan Taylor", "position": "RB", "team": "IND", "rank_value": 13},
        {"name": "Josh Allen", "position": "QB", "team": "BUF", "rank_value": 14},
        {"name": "Patrick Mahomes", "position": "QB", "team": "KC", "rank_value": 15},
        {"name": "Travis Kelce", "position": "TE", "team": "KC", "rank_value": 16},
        {"name": "A.J. Brown", "position": "WR", "team": "PHI", "rank_value": 17},
        {"name": "Davante Adams", "position": "WR", "team": "LV", "rank_value": 18},
        {"name": "Tyreek Hill", "position": "WR", "team": "MIA", "rank_value": 19},
        {"name": "Stefon Diggs", "position": "WR", "team": "BUF", "rank_value": 20},
        {"name": "Cooper Kupp", "position": "WR", "team": "LAR", "rank_value": 21},
        {"name": "DeVonta Smith", "position": "WR", "team": "PHI", "rank_value": 22},
        {"name": "Jaylen Waddle", "position": "WR", "team": "MIA", "rank_value": 23},
        {"name": "Tee Higgins", "position": "WR", "team": "CIN", "rank_value": 24},
        {"name": "Chris Olave", "position": "WR", "team": "NO", "rank_value": 25},
        {"name": "DK Metcalf", "position": "WR", "team": "SEA", "rank_value": 26},
        {"name": "Deebo Samuel", "position": "WR", "team": "SF", "rank_value": 27},
        {"name": "Mike Evans", "position": "WR", "team": "TB", "rank_value": 28},
        {"name": "Keenan Allen", "position": "WR", "team": "CHI", "rank_value": 29},
        {"name": "Amari Cooper", "position": "WR", "team": "CLE", "rank_value": 30},
        {"name": "DeAndre Hopkins", "position": "WR", "team": "TEN", "rank_value": 31},
        {"name": "Terry McLaurin", "position": "WR", "team": "WAS", "rank_value": 32},
        {"name": "DJ Moore", "position": "WR", "team": "CHI", "rank_value": 33},
        {"name": "Christian Watson", "position": "WR", "team": "GB", "rank_value": 34},
        {"name": "George Pickens", "position": "WR", "team": "PIT", "rank_value": 35},
        {"name": "Jaxon Smith-Njigba", "position": "WR", "team": "SEA", "rank_value": 36},
        {"name": "Jordan Addison", "position": "WR", "team": "MIN", "rank_value": 37},
        {"name": "Zay Flowers", "position": "WR", "team": "BAL", "rank_value": 38},
        {"name": "Quentin Johnston", "position": "WR", "team": "LAC", "rank_value": 39},
        {"name": "Marvin Harrison Jr.", "position": "WR", "team": "ARI", "rank_value": 40},
        {"name": "Lamar Jackson", "position": "QB", "team": "BAL", "rank_value": 41},
        {"name": "Joe Burrow", "position": "QB", "team": "CIN", "rank_value": 42},
        {"name": "Jalen Hurts", "position": "QB", "team": "PHI", "rank_value": 43},
        {"name": "Justin Herbert", "position": "QB", "team": "LAC", "rank_value": 44},
        {"name": "Trevor Lawrence", "position": "QB", "team": "JAX", "rank_value": 45},
        {"name": "Anthony Richardson", "position": "QB", "team": "IND", "rank_value": 46},
        {"name": "C.J. Stroud", "position": "QB", "team": "HOU", "rank_value": 47},
        {"name": "Caleb Williams", "position": "QB", "team": "CHI", "rank_value": 48},
        {"name": "Kyler Murray", "position": "QB", "team": "ARI", "rank_value": 49},
        {"name": "Dak Prescott", "position": "QB", "team": "DAL", "rank_value": 50},
        {"name": "Sam Howell", "position": "QB", "team": "WAS", "rank_value": 51},
        {"name": "Jayden Daniels", "position": "QB", "team": "WAS", "rank_value": 52},
        {"name": "Tua Tagovailoa", "position": "QB", "team": "MIA", "rank_value": 53},
        {"name": "Deshaun Watson", "position": "QB", "team": "CLE", "rank_value": 54},
        {"name": "Bryce Young", "position": "QB", "team": "CAR", "rank_value": 55},
        {"name": "Jordan Love", "position": "QB", "team": "GB", "rank_value": 56},
        {"name": "Aaron Rodgers", "position": "QB", "team": "NYJ", "rank_value": 57},
        {"name": "Geno Smith", "position": "QB", "team": "SEA", "rank_value": 58},
        {"name": "Kirk Cousins", "position": "QB", "team": "ATL", "rank_value": 59},
        {"name": "Brock Purdy", "position": "QB", "team": "SF", "rank_value": 60},
        {"name": "Kenneth Walker III", "position": "RB", "team": "SEA", "rank_value": 61},
        {"name": "Travis Etienne", "position": "RB", "team": "JAX", "rank_value": 62},
        {"name": "Derrick Henry", "position": "RB", "team": "BAL", "rank_value": 63},
        {"name": "Tony Pollard", "position": "RB", "team": "TEN", "rank_value": 64},
        {"name": "Rhamondre Stevenson", "position": "RB", "team": "NE", "rank_value": 65},
        {"name": "Najee Harris", "position": "RB", "team": "PIT", "rank_value": 66},
        {"name": "Josh Jacobs", "position": "RB", "team": "GB", "rank_value": 67},
        {"name": "James Cook", "position": "RB", "team": "BUF", "rank_value": 68},
        {"name": "Rachaad White", "position": "RB", "team": "TB", "rank_value": 69},
        {"name": "Javonte Williams", "position": "RB", "team": "DEN", "rank_value": 70},
        {"name": "Isiah Pacheco", "position": "RB", "team": "KC", "rank_value": 71},
        {"name": "J.K. Dobbins", "position": "RB", "team": "LAC", "rank_value": 72},
        {"name": "David Montgomery", "position": "RB", "team": "DET", "rank_value": 73},
        {"name": "Aaron Jones", "position": "RB", "team": "MIN", "rank_value": 74},
        {"name": "Alvin Kamara", "position": "RB", "team": "NO", "rank_value": 75},
        {"name": "De'Von Achane", "position": "RB", "team": "MIA", "rank_value": 76},
        {"name": "Zach Charbonnet", "position": "RB", "team": "SEA", "rank_value": 77},
        {"name": "Brian Robinson Jr.", "position": "RB", "team": "WAS", "rank_value": 78},
        {"name": "Jaylen Warren", "position": "RB", "team": "PIT", "rank_value": 79},
        {"name": "Dameon Pierce", "position": "RB", "team": "HOU", "rank_value": 80},
        {"name": "Tyjae Spears", "position": "RB", "team": "TEN", "rank_value": 81},
        {"name": "Zamir White", "position": "RB", "team": "LV", "rank_value": 82},
        {"name": "Tank Bigsby", "position": "RB", "team": "JAX", "rank_value": 83},
        {"name": "Chuba Hubbard", "position": "RB", "team": "CAR", "rank_value": 84},
        {"name": "Devin Singletary", "position": "RB", "team": "NYG", "rank_value": 85},
        {"name": "Ezekiel Elliott", "position": "RB", "team": "DAL", "rank_value": 86},
        {"name": "Zack Moss", "position": "RB", "team": "CIN", "rank_value": 87},
        {"name": "Samaje Perine", "position": "RB", "team": "KC", "rank_value": 88},
        {"name": "Jaleel McLaughlin", "position": "RB", "team": "DEN", "rank_value": 89},
        {"name": "Roschon Johnson", "position": "RB", "team": "CHI", "rank_value": 90},
        {"name": "Mark Andrews", "position": "TE", "team": "BAL", "rank_value": 91},
        {"name": "Sam LaPorta", "position": "TE", "team": "DET", "rank_value": 92},
        {"name": "Kyle Pitts", "position": "TE", "team": "ATL", "rank_value": 93},
        {"name": "Dallas Goedert", "position": "TE", "team": "PHI", "rank_value": 94},
        {"name": "T.J. Hockenson", "position": "TE", "team": "MIN", "rank_value": 95},
        {"name": "George Kittle", "position": "TE", "team": "SF", "rank_value": 96},
        {"name": "Dalton Kincaid", "position": "TE", "team": "BUF", "rank_value": 97},
        {"name": "Evan Engram", "position": "TE", "team": "JAX", "rank_value": 98},
        {"name": "David Njoku", "position": "TE", "team": "CLE", "rank_value": 99},
        {"name": "Pat Freiermuth", "position": "TE", "team": "PIT", "rank_value": 100},
        {"name": "Cole Kmet", "position": "TE", "team": "CHI", "rank_value": 101},
        {"name": "Dalton Schultz", "position": "TE", "team": "HOU", "rank_value": 102},
        {"name": "Jake Ferguson", "position": "TE", "team": "DAL", "rank_value": 103},
        {"name": "Trey McBride", "position": "TE", "team": "ARI", "rank_value": 104},
        {"name": "Chigoziem Okonkwo", "position": "TE", "team": "TEN", "rank_value": 105},
        {"name": "Luke Musgrave", "position": "TE", "team": "GB", "rank_value": 106},
        {"name": "Michael Mayer", "position": "TE", "team": "LV", "rank_value": 107},
        {"name": "Tyler Conklin", "position": "TE", "team": "NYJ", "rank_value": 108},
        {"name": "Juwan Johnson", "position": "TE", "team": "NO", "rank_value": 109},
        {"name": "Gerald Everett", "position": "TE", "team": "CHI", "rank_value": 110},
        {"name": "Brandin Cooks", "position": "WR", "team": "DAL", "rank_value": 111},
        {"name": "Michael Pittman Jr.", "position": "WR", "team": "IND", "rank_value": 112},
        {"name": "Calvin Ridley", "position": "WR", "team": "TEN", "rank_value": 113},
        {"name": "Christian Kirk", "position": "WR", "team": "JAX", "rank_value": 114},
        {"name": "Diontae Johnson", "position": "WR", "team": "CAR", "rank_value": 115},
        {"name": "Courtland Sutton", "position": "WR", "team": "DEN", "rank_value": 116},
        {"name": "Jerry Jeudy", "position": "WR", "team": "CLE", "rank_value": 117},
        {"name": "Rashee Rice", "position": "WR", "team": "KC", "rank_value": 118},
        {"name": "Jakobi Meyers", "position": "WR", "team": "LV", "rank_value": 119},
        {"name": "Marquise Brown", "position": "WR", "team": "KC", "rank_value": 120},
        {"name": "Gabe Davis", "position": "WR", "team": "JAX", "rank_value": 121},
        {"name": "Elijah Moore", "position": "WR", "team": "CLE", "rank_value": 122},
        {"name": "Jameson Williams", "position": "WR", "team": "DET", "rank_value": 123},
        {"name": "Romeo Doubs", "position": "WR", "team": "GB", "rank_value": 124},
        {"name": "Rashid Shaheed", "position": "WR", "team": "NO", "rank_value": 125},
        {"name": "Skyy Moore", "position": "WR", "team": "KC", "rank_value": 126},
        {"name": "Kadarius Toney", "position": "WR", "team": "KC", "rank_value": 127},
        {"name": "Alec Pierce", "position": "WR", "team": "IND", "rank_value": 128},
        {"name": "Wan'Dale Robinson", "position": "WR", "team": "NYG", "rank_value": 129},
        {"name": "Khalil Shakir", "position": "WR", "team": "BUF", "rank_value": 130},
        {"name": "Darnell Mooney", "position": "WR", "team": "ATL", "rank_value": 131},
        {"name": "Tyler Lockett", "position": "WR", "team": "SEA", "rank_value": 132},
        {"name": "Allen Lazard", "position": "WR", "team": "NYJ", "rank_value": 133},
        {"name": "Rondale Moore", "position": "WR", "team": "ATL", "rank_value": 134},
        {"name": "Jayden Reed", "position": "WR", "team": "GB", "rank_value": 135},
        {"name": "Xavier Worthy", "position": "WR", "team": "KC", "rank_value": 136},
        {"name": "Jauan Jennings", "position": "WR", "team": "SF", "rank_value": 137},
        {"name": "Dontayvion Wicks", "position": "WR", "team": "GB", "rank_value": 138},
        {"name": "Jalen Tolbert", "position": "WR", "team": "DAL", "rank_value": 139},
        {"name": "Demario Douglas", "position": "WR", "team": "NE", "rank_value": 140},
        {"name": "Odell Beckham Jr.", "position": "WR", "team": "MIA", "rank_value": 141},
        {"name": "Tutu Atwell", "position": "WR", "team": "LAR", "rank_value": 142},
        {"name": "Jalin Hyatt", "position": "WR", "team": "NYG", "rank_value": 143},
        {"name": "Andrei Iosivas", "position": "WR", "team": "CIN", "rank_value": 144},
        {"name": "Cedric Tillman", "position": "WR", "team": "CLE", "rank_value": 145},
        {"name": "Jalen Brooks", "position": "WR", "team": "DAL", "rank_value": 146},
        {"name": "Tre Tucker", "position": "WR", "team": "LV", "rank_value": 147},
        {"name": "Marvin Mims Jr.", "position": "WR", "team": "DEN", "rank_value": 148},
        {"name": "Kayshon Boutte", "position": "WR", "team": "NE", "rank_value": 149},
        {"name": "Justyn Ross", "position": "WR", "team": "KC", "rank_value": 150}
    ]
    
    # Create DataFrame
    df = pd.DataFrame(players)
    
    # Add placeholder columns
    df["bye"] = 0
    df["status"] = "Active"
    df["player_id"] = None
    
    return df

def main(league_id=None, user_id=None):
    """
    Main function to create rankings and optionally update config.
    
    Args:
        league_id (str, optional): The Sleeper league ID for config
        user_id (str, optional): The Sleeper user ID for config
    """
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Create config if league_id is provided
    if league_id:
        create_config(league_id, user_id)
        print(f"Updated config.json with league_id: {league_id}")
    else:
        print("No league_id provided, skipping config update")
    
    # Fetch rankings
    rankings_df = fetch_player_rankings()
    
    # If rankings fetch failed, use fallback
    if rankings_df.empty:
        rankings_df = create_fallback_rankings()
    
    # Fetch player IDs
    ids_df = fetch_player_ids()
    
    # Get Sleeper players for additional metadata
    sleeper_players = fetch_sleeper_players()
    
    # Merge rankings with IDs
    final_df = merge_rankings_with_ids(rankings_df, ids_df, sleeper_players)
    
    # Convert player_id to integer where possible (removing .0)
    def convert_id_to_int(player_id):
        if pd.notna(player_id):
            try:
                # Convert to integer by first converting to float
                return str(int(float(player_id)))
            except:
                pass
        return ""
    
    # Apply conversion to player_id column - store as strings to avoid decimal points
    final_df["player_id"] = final_df["player_id"].apply(convert_id_to_int)
    
    # Ensure player_id is stored as string in CSV to preserve exact format
    final_df["player_id"] = final_df["player_id"].astype(str)
    final_df["player_id"] = final_df["player_id"].replace('nan', '')
    
    # Save to CSV
    output_path = "data/dynasty_rankings.csv"
    final_df.to_csv(output_path, index=False)
    print(f"Rankings saved to {output_path}")
    
    return final_df

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create dynasty rankings CSV")
    parser.add_argument("--league_id", help="Sleeper league ID (optional, only needed for config.json)")
    parser.add_argument("--user_id", help="Sleeper user ID (optional, only needed for config.json)")
    
    args = parser.parse_args()
    
    main(args.league_id, args.user_id)

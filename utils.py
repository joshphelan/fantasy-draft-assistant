import requests
import pandas as pd
import time
import os
import json
from typing import Dict, List, Any, Optional

# --- Constants ---
BASE_URL = "https://api.sleeper.app/v1"
RANKINGS_PATH = "data/dynasty_rankings.csv"

# --- API Functions ---
def get_user_id(username: str) -> Optional[str]:
    """
    Get the Sleeper user ID for a given username.
    
    Args:
        username (str): The Sleeper username
        
    Returns:
        str: The user ID if found, None otherwise
    """
    try:
        response = requests.get(f"{BASE_URL}/user/{username}")
        response.raise_for_status()
        user_data = response.json()
        user_id = user_data.get("user_id")
        
        if user_id:
            print(f"User ID for {username}: {user_id}")
            return user_id
        else:
            print(f"No user ID found for username: {username}")
            return None
    except Exception as e:
        print(f"Error fetching user ID: {str(e)}")
        return None

def get_user_leagues(user_id: str, sport: str = "nfl", season: str = "2025") -> List[Dict]:
    """
    Get all leagues for a user in a specific sport and season.
    
    Args:
        user_id (str): The Sleeper user ID
        sport (str): The sport (default: nfl)
        season (str): The season (default: 2025)
        
    Returns:
        list: List of leagues
    """
    try:
        response = requests.get(f"{BASE_URL}/user/{user_id}/leagues/{sport}/{season}")
        response.raise_for_status()
        leagues = response.json()
        
        if leagues:
            print(f"Found {len(leagues)} {sport} leagues for the {season} season")
            for i, league in enumerate(leagues):
                print(f"{i+1}. {league.get('name')} (ID: {league.get('league_id')})")
            return leagues
        else:
            print(f"No {sport} leagues found for the {season} season")
            return []
    except Exception as e:
        print(f"Error fetching leagues: {str(e)}")
        return []

def get_league_info(league_id: str) -> Optional[Dict]:
    """
    Get information about a league.
    
    Args:
        league_id (str): The Sleeper league ID
        
    Returns:
        dict: League information if found, None otherwise
    """
    try:
        response = requests.get(f"{BASE_URL}/league/{league_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching league info: {str(e)}")
        return None

def get_draft_info(draft_id: str) -> Optional[Dict]:
    """
    Get information about a draft.
    
    Args:
        draft_id (str): The Sleeper draft ID
        
    Returns:
        dict: Draft information if found, None otherwise
    """
    try:
        response = requests.get(f"{BASE_URL}/draft/{draft_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching draft info: {str(e)}")
        return None

def get_draft_picks(draft_id: str) -> List[Dict]:
    """
    Get all picks made in a draft.
    
    Args:
        draft_id (str): The Sleeper draft ID
        
    Returns:
        list: List of draft picks
    """
    try:
        response = requests.get(f"{BASE_URL}/draft/{draft_id}/picks")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching draft picks: {str(e)}")
        return []

def get_all_players() -> Dict:
    """
    Get all NFL players from Sleeper.
    
    Returns:
        dict: Dictionary of player data keyed by player_id
    """
    try:
        response = requests.get(f"{BASE_URL}/players/nfl", timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching players: {str(e)}")
        return {}

# --- Config Functions ---
def load_config() -> Dict:
    """
    Load the config from Streamlit secrets.
    
    Returns:
        dict: The config data
    """
    try:
        import streamlit as st
        return {
            "league_id": st.secrets["sleeper"]["league_id"],
            "user_id": st.secrets["sleeper"]["user_id"],
            "roster_settings": {
                "QB": 1,
                "RB": 2,
                "WR": 3,
                "TE": 1,
                "FLEX": 2
            }
        }
    except (ImportError, KeyError):
        # Fallback for non-Streamlit environments or missing secrets
        print("Warning: Streamlit secrets not available. Using default config.")
        return {
            "league_id": "",
            "user_id": "",
            "roster_settings": {
                "QB": 1,
                "RB": 2,
                "WR": 3,
                "TE": 1,
                "FLEX": 2
            }
        }

def save_config(config: Dict) -> None:
    """
    This function is deprecated. Configuration is now managed through Streamlit secrets.
    
    Args:
        config (dict): The config data (ignored)
    """
    print("Warning: Configuration is now managed through Streamlit secrets.")
    print("To update configuration, edit .streamlit/secrets.toml locally or use the Streamlit Cloud dashboard.")

# --- Data Processing Functions ---
def build_available_pool(rankings_df: pd.DataFrame, picks: List[Dict]) -> pd.DataFrame:
    """
    Build a pool of available players by removing drafted players.
    
    Args:
        rankings_df (pd.DataFrame): DataFrame with player rankings
        picks (list): List of draft picks
        
    Returns:
        pd.DataFrame: DataFrame with available players
    """
    # Extract player IDs that have been drafted
    drafted_ids = {pick.get("player_id") for pick in picks if pick.get("player_id")}
    
    # Filter rankings to only include available players
    available = rankings_df[~rankings_df["player_id"].isin(drafted_ids)]
    
    # Sort by rank value
    return available.sort_values("rank_value")

def compute_position_needs(roster_settings: Dict[str, int], drafted_df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """
    Compute positional needs based on roster settings and drafted players.
    
    Args:
        roster_settings (dict): Dictionary of position requirements
        drafted_df (pd.DataFrame): DataFrame with drafted players
        
    Returns:
        dict: Dictionary of positional needs
    """
    position_counts = {pos: {"required": count, "drafted": 0, "needed": count} 
                      for pos, count in roster_settings.items()}
    
    # Count drafted players by position
    for pos in position_counts:
        drafted_count = drafted_df[drafted_df["position"] == pos].shape[0]
        position_counts[pos]["drafted"] = drafted_count
        position_counts[pos]["needed"] = max(position_counts[pos]["required"] - drafted_count, 0)
    
    return position_counts

def picks_until_next(picks: List[Dict], draft_order: Dict[str, int], user_id: str) -> int:
    """
    Calculate how many picks until the user's next turn.
    
    Args:
        picks (list): List of draft picks
        draft_order (dict): Dictionary mapping user IDs to draft positions
        user_id (str): The user's ID
        
    Returns:
        int: Number of picks until the user's next turn
    """
    # Get current pick number
    current_pick = len(picks)
    
    # Get total teams
    teams = len(draft_order)
    
    # Find user's draft position
    user_position = None
    for uid, position in draft_order.items():
        if uid == user_id:
            user_position = position
            break
    
    if user_position is None:
        return -1  # User not found in draft order
    
    # Calculate next pick for user
    picks_until_turn = 0
    current_position = current_pick % teams
    
    # Handle snake drafts (assuming snake draft)
    current_round = current_pick // teams + 1
    
    if current_round % 2 == 0:  # Even rounds go backwards
        # Logic for even rounds in snake draft
        if user_position <= current_position:
            picks_until_turn = current_position - user_position
        else:
            picks_until_turn = (teams - user_position) + current_position + teams
    else:  # Odd rounds
        # Logic for odd rounds
        if user_position >= current_position:
            picks_until_turn = user_position - current_position
        else:
            picks_until_turn = (teams - current_position) + user_position + teams
    
    return picks_until_turn

def toggle_star(player_id: str, starred_set: set) -> set:
    """
    Toggle a player's starred status.
    
    Args:
        player_id (str): The player ID
        starred_set (set): Set of starred player IDs
        
    Returns:
        set: Updated set of starred player IDs
    """
    if player_id in starred_set:
        starred_set.remove(player_id)
    else:
        starred_set.add(player_id)
    
    return starred_set

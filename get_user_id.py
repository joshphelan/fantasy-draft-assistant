import requests
import sys

def get_user_id(username):
    """
    Get the Sleeper user ID for a given username.
    
    Args:
        username (str): The Sleeper username
        
    Returns:
        str: The user ID if found, None otherwise
    """
    try:
        response = requests.get(f"https://api.sleeper.app/v1/user/{username}")
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

def get_user_leagues(user_id, sport="nfl", season="2025"):
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
        response = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/{sport}/{season}")
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        username = input("Enter your Sleeper username: ")
    else:
        username = sys.argv[1]
    
    user_id = get_user_id(username)
    
    if user_id:
        get_user_leagues(user_id)

import os
import sys
import subprocess
import json

def main():
    print("Fantasy Draft Assistant Setup")
    print("============================")
    print("This script will help you set up your Fantasy Draft Assistant.")
    print("It will get your Sleeper user ID and create the rankings CSV file.")
    print()
    
    # Check if config.json exists
    if not os.path.exists("config.json"):
        print("Error: config.json not found. Please make sure you're in the correct directory.")
        return
    
    # Load config
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # Check if league ID is set
    league_id = config.get("league_id")
    if not league_id:
        league_id = input("Enter your Sleeper league ID: ")
        config["league_id"] = league_id
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
    else:
        print(f"League ID: {league_id}")
    
    # Check if user ID is set
    user_id = config.get("user_id")
    if not user_id:
        # Ask for username
        username = input("Enter your Sleeper username: ")
        
        # Get user ID
        print("\nGetting your Sleeper user ID...")
        result = subprocess.run(
            [sys.executable, "get_user_id.py", username],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if "User ID for" in result.stdout:
            # Extract user ID from output
            user_id_line = [line for line in result.stdout.split("\n") if "User ID for" in line][0]
            user_id = user_id_line.split(": ")[1].strip()
            
            # Update config
            config["user_id"] = user_id
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            print(f"User ID saved to config.json: {user_id}")
        else:
            user_id = input("Could not automatically get your user ID. Please enter it manually: ")
            config["user_id"] = user_id
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
    else:
        print(f"User ID: {user_id}")
    
    # Create rankings
    print("\nCreating rankings CSV file...")
    print("This may take a few minutes as it fetches data from multiple sources.")
    print()
    
    result = subprocess.run(
        [sys.executable, "create_rankings.py", league_id, "--user_id", user_id],
        capture_output=False
    )
    
    # Check if rankings file was created
    if os.path.exists("data/dynasty_rankings.csv"):
        print("\nSetup complete!")
        print("You can now run the Fantasy Draft Assistant with:")
        print("streamlit run app.py")
    else:
        print("\nError: Failed to create rankings file.")
        print("Please check the output above for errors.")

if __name__ == "__main__":
    main()

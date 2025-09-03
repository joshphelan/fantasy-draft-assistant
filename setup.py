import os
import sys
import subprocess
import json
import toml

def main():
    print("Fantasy Draft Assistant Setup")
    print("============================")
    print("This script will help you set up your Fantasy Draft Assistant.")
    print("It will get your Sleeper user ID and create the rankings CSV file.")
    print()
    
    # Create .streamlit directory if it doesn't exist
    if not os.path.exists(".streamlit"):
        os.makedirs(".streamlit")
        print("Created .streamlit directory for Streamlit secrets")
    
    # Check if secrets.toml exists
    secrets_path = ".streamlit/secrets.toml"
    if os.path.exists(secrets_path):
        # Load existing secrets
        with open(secrets_path, "r") as f:
            secrets_content = f.read()
            try:
                secrets = toml.loads(secrets_content)
            except:
                secrets = {}
                
        # Initialize sleeper section if it doesn't exist
        if "sleeper" not in secrets:
            secrets["sleeper"] = {}
    else:
    # Create new secrets file
        secrets = {"sleeper": {}}
        print(f"Created new {secrets_path} file for configuration")
    
    # Extract config values
    league_id = secrets.get("sleeper", {}).get("league_id", "")
    user_id = secrets.get("sleeper", {}).get("user_id", "")
    
    # Check if league ID is set
    if not league_id:
        league_id = input("Enter your Sleeper league ID: ")
        secrets["sleeper"]["league_id"] = league_id
        with open(secrets_path, "w") as f:
            toml.dump(secrets, f)
        print(f"League ID saved to {secrets_path}")
    else:
        print(f"League ID: {league_id}")
    
    # Check if user ID is set
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
            
            # Update secrets
            secrets["sleeper"]["user_id"] = user_id
            with open(secrets_path, "w") as f:
                toml.dump(secrets, f)
            
            print(f"User ID saved to {secrets_path}: {user_id}")
        else:
            user_id = input("Could not automatically get your user ID. Please enter it manually: ")
            secrets["sleeper"]["user_id"] = user_id
            with open(secrets_path, "w") as f:
                toml.dump(secrets, f)
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
        print("Configuration saved to .streamlit/secrets.toml")
        print("You can now run the Fantasy Draft Assistant with:")
        print("streamlit run app.py")
        print("\nFor deployment to Streamlit Cloud:")
        print("1. Add your configuration to the Streamlit Cloud dashboard")
        print("2. In the app settings, add the following secrets:")
        print(f"   [sleeper]\n   league_id = \"{league_id}\"\n   user_id = \"{user_id}\"")
    else:
        print("\nError: Failed to create rankings file.")
        print("Please check the output above for errors.")

if __name__ == "__main__":
    main()

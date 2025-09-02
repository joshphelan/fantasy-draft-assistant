# Fantasy Draft Assistant

A real-time dynasty draft assistant for Sleeper fantasy football leagues. This tool helps you make informed draft decisions by showing best available players, positional needs, and picks-until-your-turn indicators.

## Features

- **Real-time Draft Updates**: Auto-refreshes to show latest picks (default 30 seconds)
- **Best Available Players**: Shows top-ranked players based on your dynasty rankings
- **Positional KPIs**: Visual indicators of your positional needs (red for 0 players)
- **Smart Recommendations**: Top 5 recommended players based on ranking and positional needs
- **Picks-Until-Your-Turn**: Shows how many picks until you're on the clock
- **Recent Picks Feed**: See the most recent draft picks

## Setup

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the setup script to configure your Sleeper user ID:
   ```
   python setup.py
   ```
   - You'll be prompted for your Sleeper username
   - The script will fetch your user ID and create the rankings CSV

3. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

## Configuration

The `config.json` file contains your league settings:

```json
{
  "league_id": "your_league_id",
  "user_id": "your_user_id"
}
```

- `league_id`: Your Sleeper league ID
- `user_id`: Your Sleeper user ID
- `roster_settings`: The number of players required at each position

You can edit this file directly or use the configuration panel in the app's sidebar.

## Player Rankings

The app uses a CSV file with player rankings located at `data/dynasty_rankings.csv`. This file includes:

- Player name
- Position
- Team
- Rank value
- Bye week
- Status

The rankings are used to recommend the best available players during your draft.

## Usage Tips

1. **Recommended Players**: The top 5 recommended players are marked with a star (⭐) in the player table
2. **Filter by Position**: Use the position filter to focus on specific positions
3. **Auto-refresh**: Toggle auto-refresh on/off and adjust the refresh rate in the sidebar
4. **Positional Needs**: The color-coded position metrics show which positions you need to prioritize
   - Green: Position requirement met
   - Orange: Some players but need more
   - Red: No players at this position (highest priority)

## Troubleshooting

- If the app can't connect to Sleeper, check your league ID and user ID
- If player rankings aren't showing, make sure the `data/dynasty_rankings.csv` file exists
- If the draft order can't be determined, the draft may not have started yet

## Recommendation Logic

The app uses a smart recommendation system that balances these key factors:

1. **Player Ranking**: Base score is derived from the player's overall rank. Higher-ranked players receive higher base scores.

2. **Position Requirements**:
   - QB and TE positions are not recommended once you've reached your limits (2 QBs and 1 TE)
   - This ensures you don't overdraft positions with limited roster spots

3. **RB/WR Balance**:
   - The system only adjusts recommendations when the RB/WR ratio is significantly imbalanced (outside 0.7-1.3 range)
   - When ratio > 1.3 (too many RBs): WR positions get a boost
   - When ratio < 0.7 (too many WRs): RB positions get a boost
   - Within the balanced range (0.7-1.3): No position adjustments are made

This approach prioritizes getting the best available players while maintaining position balance and ensuring you don't overdraft positions with limited roster spots.

## Project Structure

```
fantasy-draft-assistant/
├── app.py              # Streamlit dashboard (UI + layout)
├── utils.py            # Helper functions for API calls, player pool, KPIs, etc.
├── create_rankings.py  # Script to generate rankings from multiple sources
├── compare_player_ids.py # Script to compare player IDs from different sources
├── fix_player_ids.py   # Script to fix player IDs in rankings
├── get_user_id.py      # Script to get your Sleeper user ID
├── setup.py            # Easy setup script to get started quickly
├── config.json         # Configuration with league_id, user_id, roster settings
├── .gitignore          # Git ignore file for virtual environment and cache files
├── data/               # Directory for the rankings CSV
├── requirements.txt    # Python dependencies
└── README.md           # This file

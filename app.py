import streamlit as st
import pandas as pd
import requests
import json
import time
import os
import math
from typing import Dict, List, Any, Optional, Tuple

# --- Configuration ---
# Use Streamlit secrets for configuration
CONFIG = {
    "league_id": st.secrets["sleeper"]["league_id"],
    "user_id": st.secrets["sleeper"]["user_id"]
}

# --- Sleeper API Client ---
class SleeperClient:
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self, league_id: str, user_id: str):
        self.league_id = league_id
        self.user_id = user_id
        self._draft_id = None
        self._players_cache = None
        self._draft_data = None
        self._picks_cache = []
        self._last_picks_timestamp = 0
        self._league_users = None
    
    @st.cache_data(ttl=3600)
    def get_players(_self):
        """Get all NFL players from Sleeper"""
        if not _self._players_cache:
            try:
                with st.spinner("Fetching players from Sleeper..."):
                    resp = requests.get(f"{_self.BASE_URL}/players/nfl", timeout=15)
                    resp.raise_for_status()
                    _self._players_cache = resp.json()
            except Exception as e:
                st.error(f"Failed to get players: {str(e)}")
                return {}
        return _self._players_cache
    
    def get_draft_id(self):
        """Get draft ID for the league"""
        if not self._draft_id:
            try:
                resp = requests.get(f"{self.BASE_URL}/league/{self.league_id}", timeout=10)
                resp.raise_for_status()
                data = resp.json()
                self._draft_id = data.get("draft_id")
                if not self._draft_id:
                    st.warning(f"No draft found for league {self.league_id}")
                    return None
            except Exception as e:
                st.error(f"Failed to get draft ID: {str(e)}")
                return None
        return self._draft_id
    
    def get_draft_data(self):
        """Get full draft data"""
        if not self._draft_data:
            draft_id = self.get_draft_id()
            if not draft_id:
                return None
                
            try:
                resp = requests.get(f"{self.BASE_URL}/draft/{draft_id}", timeout=10)
                resp.raise_for_status()
                self._draft_data = resp.json()
            except Exception as e:
                st.error(f"Failed to get draft data: {str(e)}")
                return None
        return self._draft_data
    
    @st.cache_data(ttl=10)
    def get_draft_picks(_self):
        """Get all draft picks made so far"""
        draft_id = _self.get_draft_id()
        if not draft_id:
            return []
            
        try:
            resp = requests.get(f"{_self.BASE_URL}/draft/{draft_id}/picks", timeout=10)
            resp.raise_for_status()
            picks = resp.json()
            _self._picks_cache = picks
            return picks
        except Exception as e:
            st.error(f"Failed to get draft picks: {str(e)}")
            # Return cached picks if available
            if _self._picks_cache:
                st.warning("Using cached picks due to API error")
                return _self._picks_cache
            return []
    
    @st.cache_data(ttl=300)
    def get_league_users(_self):
        """Get all users in the league"""
        if not _self._league_users:
            try:
                resp = requests.get(f"{_self.BASE_URL}/league/{_self.league_id}/users", timeout=10)
                resp.raise_for_status()
                _self._league_users = resp.json()
            except Exception as e:
                st.error(f"Failed to get league users: {str(e)}")
                return []
        return _self._league_users
    
    def get_user_picks(self):
        """Get picks made by the current user"""
        all_picks = self.get_draft_picks()
        return [pick for pick in all_picks if pick.get("picked_by") == self.user_id]
    
    def calculate_picks_until_turn(self):
        """Calculate picks until user's next turn"""
        draft_data = self.get_draft_data()
        if not draft_data:
            return -1
            
        # Get draft order and slot_to_roster_id
        draft_order = draft_data.get("draft_order", {})
        slot_to_roster_id = draft_data.get("slot_to_roster_id", {})
        
        # If neither draft_order nor slot_to_roster_id is available, try to get draft status
        if not draft_order and not slot_to_roster_id:
            # Try to get draft status to see if it's the user's turn
            try:
                draft_id = self.get_draft_id()
                if not draft_id:
                    return -1
                    
                resp = requests.get(f"{self.BASE_URL}/draft/{draft_id}/state", timeout=10)
                resp.raise_for_status()
                state = resp.json()
                
                # Check if it's the user's turn
                if state.get("current_player") == self.user_id:
                    return 0
                
                # If we can't determine the exact number of picks, but we know it's not the user's turn
                return 1  # Just indicate that it's not the user's turn
            except Exception as e:
                st.error(f"Failed to get draft state: {str(e)}")
                return -1
        
        # Determine user's position in the draft
        user_position = None
        
        if draft_order:
            # Find user's draft position from draft_order
            for user_id, position in draft_order.items():
                if user_id == self.user_id:
                    user_position = position
                    break
        else:
            # Find user's position from slot_to_roster_id
            # First, find user's roster ID
            user_roster_id = None
            for roster in self.get_rosters():
                if roster.get("owner_id") == self.user_id:
                    user_roster_id = roster.get("roster_id")
                    break
                    
            if user_roster_id:
                # Find user's draft slot
                for slot, roster_id in slot_to_roster_id.items():
                    if str(roster_id) == str(user_roster_id):
                        user_position = int(slot)
                        break
        
        # If we couldn't determine the user's position, return -1
        if user_position is None:
            return -1
        
        # Get current pick number
        picks = self.get_draft_picks()
        current_pick = len(picks)
        
        # Get total roster spots and teams
        settings = draft_data.get("settings", {})
        rounds = settings.get("rounds", 15)
        teams = len(slot_to_roster_id) if slot_to_roster_id else len(draft_order)
        
        # If no teams found, try to get from league settings
        if teams == 0:
            try:
                resp = requests.get(f"{self.BASE_URL}/league/{self.league_id}", timeout=10)
                resp.raise_for_status()
                league_data = resp.json()
                teams = league_data.get("total_rosters", 12)  # Default to 12 if not found
            except Exception:
                teams = 12  # Default to 12 teams if we can't determine
        
        total_picks = rounds * teams
        
        # If draft is complete
        if current_pick >= total_picks:
            return -1
        
        # Calculate next pick for user
        current_round = (current_pick // teams) + 1
        pick_in_round = current_pick % teams
        
        # Handle snake drafts
        is_snake = settings.get("type") == 2
        
        # If it's the user's turn right now
        if (is_snake and current_round % 2 == 0 and (teams - pick_in_round) == user_position) or \
           (not is_snake or current_round % 2 != 0) and pick_in_round == user_position - 1:
            return 0
        
        # Calculate picks until next turn
        if is_snake and current_round % 2 == 0:  # Even rounds go backwards
            if teams - pick_in_round > user_position:
                # User already picked in this round
                picks_until_turn = (teams - pick_in_round - user_position) + teams + user_position - 1
            else:
                # User still needs to pick in this round
                picks_until_turn = teams - pick_in_round - user_position
                if picks_until_turn < 0:
                    picks_until_turn = teams + picks_until_turn
        else:  # Odd rounds or standard draft
            if user_position <= pick_in_round:
                # User already picked in this round
                picks_until_turn = teams - pick_in_round + user_position - 1
            else:
                # User still needs to pick in this round
                picks_until_turn = user_position - pick_in_round - 1
        
        return max(0, picks_until_turn)
    
    def get_rosters(self):
        """Get all rosters in the league"""
        try:
            resp = requests.get(f"{self.BASE_URL}/league/{self.league_id}/rosters", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            st.error(f"Failed to get rosters: {str(e)}")
            return []

# --- Draft Assistant Logic ---
class DraftAssistant:
    def __init__(self, client: SleeperClient, rankings_df: pd.DataFrame, config: Dict):
        self.client = client
        self.rankings = rankings_df
        self.config = config
        # Hard requirements: 2 QBs and 1 TE
        self.required_positions = {
            "QB": 2,
            "TE": 1
        }
    
    def get_available_players(self):
        """Get available players sorted by ranking"""
        # Get all picks
        all_picks = self.client.get_draft_picks()
        
        # Extract player IDs that have been drafted
        # Convert all player_ids to strings for consistent comparison
        drafted_ids = {str(pick.get("player_id")) for pick in all_picks if pick.get("player_id")}
        
        # Filter rankings to only include available players
        available = self.rankings[~self.rankings["player_id"].isin(drafted_ids)]
        
        # Sort by rank value
        return available.sort_values("rank_value")
    
    def get_user_roster(self) -> pd.DataFrame:
        """Get the user's current roster as a DataFrame"""
        # Get user's picks
        my_picks = self.client.get_user_picks()
        
        # Create a list to store roster data
        roster_data = []
        
        for pick in my_picks:
            player_id = pick.get("player_id")
            if player_id:
                # Find player in rankings - convert to string for consistent comparison
                player_id_str = str(player_id)
                player_data = self.rankings[self.rankings["player_id"] == player_id_str]
                if not player_data.empty:
                    player = player_data.iloc[0]
                    roster_data.append({
                        "name": player["name"],
                        "position": player["position"],
                        "team": player["team"],
                        "rank_value": player["rank_value"],
                        "pick_no": pick.get("pick_no", 0),
                        "round": pick.get("round", 0)
                    })
        
        # Convert to DataFrame
        if roster_data:
            roster_df = pd.DataFrame(roster_data)
            return roster_df.sort_values(["position", "rank_value"])
        
        return pd.DataFrame(columns=["name", "position", "team", "rank_value", "pick_no", "round"])
    
    def compute_position_counts(self) -> Dict[str, int]:
        """Count the number of players drafted by position"""
        # Get user's roster
        roster = self.get_user_roster()
        
        # Count by position
        position_counts = {}
        if not roster.empty:
            position_counts = roster["position"].value_counts().to_dict()
        
        # Ensure all required positions are in the counts
        for pos in self.required_positions:
            if pos not in position_counts:
                position_counts[pos] = 0
        
        # Add RB and WR if not present
        if "RB" not in position_counts:
            position_counts["RB"] = 0
        if "WR" not in position_counts:
            position_counts["WR"] = 0
        
        return position_counts
    
    def compute_position_metrics(self) -> Tuple[Dict[str, Dict[str, Any]], float]:
        """Calculate position metrics and RB/WR ratio"""
        position_counts = self.compute_position_counts()
        
        # Calculate metrics for required positions (QB, TE)
        metrics = {}
        for pos, required in self.required_positions.items():
            drafted = position_counts.get(pos, 0)
            needed = max(required - drafted, 0)
            percentage = (drafted / required) * 100 if required > 0 else 100
            
            metrics[pos] = {
                "drafted": drafted,
                "required": required,
                "needed": needed,
                "percentage": percentage
            }
        
        # Calculate RB/WR ratio
        rb_count = position_counts.get("RB", 0)
        wr_count = position_counts.get("WR", 0)
        
        # Only consider ratio when total RB+WR count is greater than 3
        total_rb_wr = rb_count + wr_count
        
        # Default to a balanced ratio of 1.0 if not enough players
        if total_rb_wr <= 3:
            rb_wr_ratio = 1.0
        # Avoid division by zero
        elif wr_count == 0:
            rb_wr_ratio = 2.0  # Fixed value when no WRs but we have RBs
        else:
            rb_wr_ratio = rb_count / wr_count
        
        # Add RB and WR counts to metrics
        metrics["RB"] = {
            "drafted": rb_count,
            "count": rb_count
        }
        
        metrics["WR"] = {
            "drafted": wr_count,
            "count": wr_count
        }
        
        return metrics, rb_wr_ratio
    
    def get_recommendations(self, top_n=5):
        """Generate top recommendations with reasoning"""
        available = self.get_available_players()
        if available.empty:
            return []
            
        # Get position metrics and RB/WR ratio
        position_metrics, rb_wr_ratio = self.compute_position_metrics()
        
        # Create a copy for scoring
        scored_players = available.copy()
        
        # Add a score column based on ranking and RB/WR ratio
        def calculate_score(row):
            position = row["position"]
            rank = row["rank_value"]
            
            # Base score is inverse of rank (lower rank = higher score)
            base_score = 1000 - rank
            
            # Position multiplier based on RB/WR ratio
            position_multiplier = 1.0
            
            # Don't recommend QB/TE if we've already reached the limit
            if position in self.required_positions:
                metric = position_metrics.get(position, {})
                needed = metric.get("needed", 0)
                
                # If we don't need any more of this position, apply a severe penalty
                if needed <= 0:
                    position_multiplier = 0.1  # Effectively removes from recommendations
            
            # Handle RB and WR based on RB/WR ratio, but only when outside balanced range
            elif position == "RB" or position == "WR":
                # If RB/WR ratio is significantly high (more RBs than WRs), favor WRs
                if position == "WR" and rb_wr_ratio > 1.3:
                    position_multiplier = rb_wr_ratio
                # If RB/WR ratio is significantly low (more WRs than RBs), favor RBs
                elif position == "RB" and rb_wr_ratio < 0.7:
                    position_multiplier = 1.0 / max(rb_wr_ratio, 0.1)
            
            return base_score * position_multiplier
        
        scored_players["score"] = scored_players.apply(calculate_score, axis=1)
        
        # Sort by score and take top N
        recommendations = scored_players.sort_values("score", ascending=False).head(top_n)
        
        # Add reasoning
        def generate_reasoning(row):
            position = row["position"]
            rank = row["rank_value"]
            
            reasoning = f"Ranked #{int(rank)} overall. "
            
            if position in self.required_positions:
                metric = position_metrics.get(position, {})
                needed = metric.get("needed", 0)
                drafted = metric.get("drafted", 0)
                required = metric.get("required", 0)
                
                if needed > 0:
                    reasoning += f"You need {needed} more {position}(s). "
                    reasoning += f"Currently have {drafted}/{required} {position}s."
                else:
                    reasoning += f"You've filled your {position} requirement ({drafted}/{required})."
            
            elif position == "RB" or position == "WR":
                rb_count = position_metrics.get("RB", {}).get("drafted", 0)
                wr_count = position_metrics.get("WR", {}).get("drafted", 0)
                
                reasoning += f"Current RB/WR ratio: {rb_count}/{wr_count} = "
                
                if wr_count == 0:
                    reasoning += "∞ (no WRs yet). "
                else:
                    reasoning += f"{rb_wr_ratio:.1f}. "
                
                if position == "WR" and rb_wr_ratio > 1.0:
                    reasoning += "Need more WRs to balance roster."
                elif position == "RB" and rb_wr_ratio < 1.0:
                    reasoning += "Need more RBs to balance roster."
                else:
                    reasoning += "Maintains good position balance."
            
            return reasoning
        
        recommendations["reasoning"] = recommendations.apply(generate_reasoning, axis=1)
        
        return recommendations.to_dict("records")

# --- Streamlit UI ---
def main():
    st.set_page_config(
        page_title="Fantasy Draft Assistant",
        page_icon="🏈",
        layout="wide"
    )
    
    st.title("🏈 Fantasy Draft Assistant")
    
    # Check if rankings file exists
    rankings_path = "data/dynasty_rankings.csv"
    if not os.path.exists(rankings_path):
        st.error("Rankings file not found. Please run create_rankings.py first.")
        st.stop()
    
    # Load rankings
    rankings_df = pd.read_csv(rankings_path)
    
    # Ensure player_id is treated as string for consistent comparison
    rankings_df["player_id"] = rankings_df["player_id"].astype(str)
    # Replace 'nan' with empty string
    rankings_df["player_id"] = rankings_df["player_id"].replace('nan', '')
    
    # Remove bye and status columns if they exist
    if "bye" in rankings_df.columns:
        rankings_df = rankings_df.drop(columns=["bye"])
    if "status" in rankings_df.columns:
        rankings_df = rankings_df.drop(columns=["status"])
    
    # Sidebar for configuration and controls
    with st.sidebar:
        st.header("Sleeper Configuration")
        
        # League and user ID inputs
        league_id = st.text_input("League ID", value=CONFIG.get("league_id", ""))
        user_id = st.text_input("User ID", value=CONFIG.get("user_id", ""))
        
        # Save config button
        if st.button("Save Configuration"):
            # Update the CONFIG dictionary
            CONFIG["league_id"] = league_id
            CONFIG["user_id"] = user_id
            
            # Create .streamlit directory if it doesn't exist
            if not os.path.exists(".streamlit"):
                os.makedirs(".streamlit")
            
            # Save to secrets.toml
            try:
                import toml
                secrets = {"sleeper": {"league_id": league_id, "user_id": user_id}}
                with open(".streamlit/secrets.toml", "w") as f:
                    toml.dump(secrets, f)
                st.success("Configuration saved!")
            except Exception as e:
                st.error(f"Failed to save configuration: {str(e)}")
        
        # Divider
        st.divider()
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        refresh_rate = st.slider("Refresh Rate (seconds)", min_value=10, max_value=60, value=30)
        
        # Manual refresh button
        if st.button("Refresh Now"):
            st.rerun()
    
    # Check if configuration is valid
    if not league_id or not user_id:
        st.warning("Please enter your League ID and User ID in the sidebar.")
        return
    
    # Initialize Sleeper client
    client = SleeperClient(league_id, user_id)
    
    # Initialize draft assistant
    assistant = DraftAssistant(client, rankings_df, CONFIG)
    
    # Main content
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Picks until next turn
        picks_left = client.calculate_picks_until_turn()
        if picks_left >= 0:
            if picks_left == 0:
                st.success("It's your turn to pick!")
                st.metric("Picks Until Your Turn", picks_left)
            else:
                st.metric("Picks Until Your Turn", picks_left)
        else:
            st.warning("Could not determine draft order")
    
    # Position metrics
    position_metrics, rb_wr_ratio = assistant.compute_position_metrics()
    
    # Create columns for position metrics
    st.subheader("Position Metrics")
    
    # Create 3 columns for QB, TE, and RB/WR ratio
    metric_cols = st.columns(3)
    
    # QB metric
    qb_metric = position_metrics.get("QB", {})
    qb_drafted = qb_metric.get("drafted", 0)
    qb_required = qb_metric.get("required", 2)
    qb_percentage = qb_metric.get("percentage", 0)
    
    # Determine color based on percentage
    if qb_percentage == 0:
        qb_color = "red"
    elif qb_percentage < 100:
        qb_color = "orange"
    else:
        qb_color = "green"
    
    # Display QB metric
    metric_cols[0].metric(
        "QB", 
        f"{qb_drafted}/{qb_required}",
        help=f"You need {qb_metric.get('needed', 0)} more QBs"
    )
    metric_cols[0].markdown(
        f"<div style='background-color: {qb_color}; height: 5px; border-radius: 2px;'></div>", 
        unsafe_allow_html=True
    )
    
    # TE metric
    te_metric = position_metrics.get("TE", {})
    te_drafted = te_metric.get("drafted", 0)
    te_required = te_metric.get("required", 1)
    te_percentage = te_metric.get("percentage", 0)
    
    # Determine color based on percentage
    if te_percentage == 0:
        te_color = "red"
    elif te_percentage < 100:
        te_color = "orange"
    else:
        te_color = "green"
    
    # Display TE metric
    metric_cols[1].metric(
        "TE", 
        f"{te_drafted}/{te_required}",
        help=f"You need {te_metric.get('needed', 0)} more TEs"
    )
    metric_cols[1].markdown(
        f"<div style='background-color: {te_color}; height: 5px; border-radius: 2px;'></div>", 
        unsafe_allow_html=True
    )
    
    # RB/WR ratio
    rb_count = position_metrics.get("RB", {}).get("drafted", 0)
    wr_count = position_metrics.get("WR", {}).get("drafted", 0)
    
    # Format ratio for display
    if rb_count == 0 and wr_count == 0:
        ratio_display = "0/0 = N/A"
    elif wr_count == 0:
        ratio_display = f"{rb_count}/0 = N/A"
    else:
        ratio_display = f"{rb_count}/{wr_count} = {rb_wr_ratio:.1f}"
    
    # Determine color based on ratio
    if rb_count == 0 and wr_count == 0:
        ratio_color = "gray"  # No players yet
    elif rb_count == 0 or wr_count == 0:
        ratio_color = "red"  # Missing one position
    elif rb_wr_ratio > 1.3 or rb_wr_ratio < 0.7:
        ratio_color = "orange"  # Unbalanced
    else:
        ratio_color = "green"  # Balanced
    
    # Display RB/WR ratio
    metric_cols[2].metric(
        "RB/WR Ratio", 
        ratio_display,
        help="Aim for a balanced ratio between 0.7 and 1.3"
    )
    metric_cols[2].markdown(
        f"<div style='background-color: {ratio_color}; height: 5px; border-radius: 2px;'></div>", 
        unsafe_allow_html=True
    )
    
    
    # Recommendations
    st.subheader("Top Recommendations")
    
    # Explain recommendation logic
    with st.expander("How recommendations work"):
        st.write("""
        **Recommendation Logic Explained:**
        
        The recommendation system balances these key factors:
        
        1. **Player Ranking:** The base score is derived from the player's overall rank. Higher-ranked players (lower rank numbers) receive higher base scores.
        
        2. **Position Requirements:**
            - QB and TE positions are not recommended once you've reached your limits (2 QBs and 1 TE).
            - This ensures you don't overdraft positions with limited roster spots.
        
        3. **RB/WR Balance:** 
            - The system only adjusts recommendations when the RB/WR ratio is significantly imbalanced (outside 0.7-1.3 range).
            - When ratio > 1.3 (too many RBs): WR positions get a boost proportional to the ratio.
            - When ratio < 0.7 (too many WRs): RB positions get a boost inversely proportional to the ratio.
            - Within the balanced range (0.7-1.3): No position adjustments are made.
        
        The final recommendation score is: `Base Score × Position Multiplier`
        
        This approach prioritizes getting the best available players while maintaining position balance and ensuring you don't overdraft positions with limited roster spots.
        """)
    recommendations = assistant.get_recommendations(top_n=5)
    
    if recommendations:
        # Display as cards in 3 columns
        rec_cols = st.columns(3)
        for i, player in enumerate(recommendations[:6]):  # Show up to 6 recommendations
            with rec_cols[i % 3]:
                # Use a single container with border
                container = st.container(border=True)
                container.subheader(f"{player['name']} ({player['position']})")
                container.caption(f"{player['team']}")
                container.write(player['reasoning'])
    else:
        st.info("No recommendations available. Check your rankings or draft status.")
    
    # Available players table
    st.subheader("Best Available")
    
    # Position filter
    all_positions = sorted(rankings_df["position"].unique())
    selected_positions = st.multiselect("Filter by Position", all_positions, default=all_positions)
    
    # Get available players
    available = assistant.get_available_players()
    
    # Apply position filter
    if selected_positions:
        available = available[available["position"].isin(selected_positions)]
    
    # Display table
    if not available.empty:
        # Calculate recommendation scores
        def calculate_recommendation_score(row):
            position = row["position"]
            rank = row["rank_value"]
            
            # Base score is inverse of rank (lower rank = higher score)
            base_score = 2000 - (rank * 2)
            
            # Position multiplier based on RB/WR ratio
            position_multiplier = 1.0
            
            # Don't recommend QB/TE if we've already reached the limit
            if position in assistant.required_positions:
                metric = position_metrics.get(position, {})
                needed = metric.get("needed", 0)
                
                # If we don't need any more of this position, apply a severe penalty
                if needed <= 0:
                    position_multiplier = 0.1  # Effectively removes from recommendations
            
            # Handle RB and WR based on RB/WR ratio, but only when outside balanced range
            elif position == "RB" or position == "WR":
                # If RB/WR ratio is significantly high (more RBs than WRs), favor WRs
                if position == "WR" and rb_wr_ratio > 1.3:
                    position_multiplier = rb_wr_ratio
                # If RB/WR ratio is significantly low (more WRs than RBs), favor RBs
                elif position == "RB" and rb_wr_ratio < 0.7:
                    position_multiplier = 1.0 / max(rb_wr_ratio, 0.1)
            
            return base_score * position_multiplier
        
        # Add score column
        available["rec_score"] = available.apply(calculate_recommendation_score, axis=1)
        
        # Sort by recommendation score
        available_sorted = available.sort_values("rec_score", ascending=False)
        
        # Get recommended players from the cards to highlight in the table
        recommended_player_ids = set()
        for player in recommendations:
            player_id = player.get("player_id", "")
            name = player.get("name", "")
            if player_id:
                recommended_player_ids.add(player_id)
            else:
                recommended_player_ids.add(f"name_{name}")
        
        # Add recommendation star column
        def get_recommendation_status(row):
            if pd.notna(row["player_id"]) and row["player_id"] in recommended_player_ids:
                return "⭐"
            elif pd.isna(row["player_id"]) and f"name_{row['name']}" in recommended_player_ids:
                return "⭐"
            return ""
        
        available["starred"] = available.apply(get_recommendation_status, axis=1)
        
        # Reorder columns
        display_cols = ["starred", "rank_value", "name", "position", "team"]
        
        # Display table
        st.dataframe(
            available[display_cols],
            column_config={
                "starred": st.column_config.Column("Recommended", width="small"),
                "rank_value": st.column_config.NumberColumn("Rank"),
                "name": "Player",
                "position": "Pos",
                "team": "Team"
            },
            hide_index=True,
            height=400,
            use_container_width=True
        )
    else:
        st.info("No available players match your filters.")
    
    # Create two columns for roster and recent picks
    roster_col, picks_col = st.columns(2)
    
    # Current roster
    with roster_col:
        st.subheader("Your Current Roster")
        roster_df = assistant.get_user_roster()
        
        if not roster_df.empty:
            # Display roster table
            st.dataframe(
                roster_df,
                column_config={
                    "name": "Player",
                    "position": "Pos",
                    "team": "Team",
                    "rank_value": st.column_config.NumberColumn("Rank"),
                    "pick_no": "Pick"
                },
                hide_index=True
            )
        else:
            st.info("You haven't drafted any players yet.")
    
    # Draft picks
    with picks_col:
        st.subheader("Recent Draft Picks")
        picks = client.get_draft_picks()
        
        if picks:
            # Convert to DataFrame for easier display
            picks_df = pd.DataFrame(picks)
            
            # Get player details
            def get_player_details(player_id):
                # Convert player_id to string for consistent comparison
                player_id_str = str(player_id)
                player_data = rankings_df[rankings_df["player_id"] == player_id_str]
                if not player_data.empty:
                    return player_data.iloc[0]["name"], player_data.iloc[0]["position"]
                return "Unknown", "?"
            
            # Add player name and position
            picks_df["player_name"], picks_df["position"] = zip(*picks_df["player_id"].apply(get_player_details))
            
            # Get user details
            users = {user["user_id"]: user["display_name"] for user in client.get_league_users()}
            
            # Add drafter name
            picks_df["drafter_name"] = picks_df["picked_by"].apply(lambda x: users.get(x, "Unknown"))
            
            # Display recent picks (last 10)
            recent_picks = picks_df[["round", "pick_no", "player_name", "position", "drafter_name"]].tail(10)
            recent_picks.columns = ["Round", "Pick", "Player", "Pos", "Drafted By"]
            st.dataframe(recent_picks, hide_index=True)
        else:
            st.info("No draft picks made yet.")
    
    # Last updated timestamp
    st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()

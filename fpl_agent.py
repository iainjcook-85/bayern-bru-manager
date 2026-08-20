import os
import requests
from google import genai

def run_manager():
    # 1. Fetch live FPL data with a browser footprint
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    data = response.json()

    # 2. Map Team IDs and Positions for the AI
    teams = {t['id']: t['name'] for t in data['teams']}
    positions = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    # 3. Extract active players cleanly
    active_players = [
        f"{p['web_name']} - {positions.get(p['element_type'])} - £{p['now_cost']/10}m - Team: {teams.get(p['team'])}" 
        for p in data["elements"] if p["status"] != 'u'
    ]
    fpl_context = "\n".join(active_players)

    # 4. Construct the GW1 Squad Prompt
    prompt = f"""You are the manager for my FPL team, Bayern Bru. 
Select our initial 15-man squad for Gameweek 1 based strictly on this data.

Core Constraints:
- Total Budget: Maximum £100.0m.
- Squad Structure: Exactly 15 players (2 GKs, 5 DEFs, 5 MIDs, 3 FWDs).
- Team Limit: Maximum of 3 players from any single Premier League team.
- Designate 1 Captain (C) and 1 Vice-Captain (VC).
- List the players clearly grouped by team.

Player Data:
{fpl_context}
"""

    # 5. Generate the AI strategy with the active model
    client = genai.Client() 
    response = client.models.generate_content(
        model="gemini-3.6-flash", 
        contents=prompt
    )

    print("--- Bayern Bru: Gameweek 1 Initial Squad ---")
    print(response.text)

if __name__ == "__main__":
    run_manager()

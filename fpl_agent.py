import os
import requests
from google import genai
from google.genai import types

def run_manager():
    # 1. Fetch live FPL data with a browser footprint
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    data = response.json()

    # 2. Map Team IDs and Positions
    teams = {t['id']: t['name'] for t in data['teams']}
    positions = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    # 3. Extract active players cleanly with injury/ban news
    active_players = []
    for p in data["elements"]:
        if p["status"] != 'u': 
            news = f" - Warning: {p['news']}" if p.get('news') else ""
            active_players.append(
                f"{p['web_name']} - {positions.get(p['element_type'])} - £{p['now_cost']/10}m - Team: {teams.get(p['team'])} - Status: {p['status']}{news}"
            )
    
    fpl_context = "\n".join(active_players)

    # 4. Construct the GW1 Squad Prompt with Team Selection First
    prompt = f"""You are the manager for my FPL team, Bayern Bru. 
Select our initial 15-man squad for Gameweek 1 based strictly on this data.

Core Constraints:
- Total Budget: Maximum £100.0m.
- Squad Structure: Exactly 15 players (2 GKs, 5 DEFs, 5 MIDs, 3 FWDs).
- Team Limit: Maximum of 3 players from any single Premier League team.
- CRITICAL: Do NOT select any player unless their Status is 'a' (available). Exclude all injured ('i'), suspended ('s'), or doubtful ('d') players.

Output Structure Required:
1. 15-Man Squad Grouped by Team (Alphabetical by Premier League Team name with player name, position, and price for quick entry).
2. Total Squad Cost Verification (£100.0m limit).
3. Formation & Starting XI (e.g., 3-5-2 or 3-4-3).
4. Captain (C) and Vice-Captain (VC).
5. Substitutes in Exact Priority Order:
   - Sub GK
   - Bench 1 (1st outfield sub)
   - Bench 2 (2nd outfield sub)
   - Bench 3 (3rd outfield sub)

Player Data:
{fpl_context}
"""

    # 5. Generate the AI strategy with temperature set to 0.0 (deterministic)
    client = genai.Client() 
    response = client.models.generate_content(
        model="gemini-3.6-flash", 
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
        )
    )

    print("--- Bayern Bru: Gameweek 1 Complete Squad & Tactics ---")
    print(response.text)

if __name__ == "__main__":
    run_manager()

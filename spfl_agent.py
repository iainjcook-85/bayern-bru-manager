import os
import requests
from google import genai
from google.genai import types

def run_spfl_manager():
    # 1. Fetch live SPFL player pool
    url = "https://fantasy.spfl.co.uk/v1/private/searchjoueurs?lg=en"
    
    # Headers using your SPFL session token & access key
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "authorization": os.getenv("SPFL_AUTH_TOKEN", "Token eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3ODcyMjIwNDgsImV4cCI6MTc4OTkwMDQ0OCwianRpIjoiTFhKNlVBVHI4VFd6QUVmVUhwRFJQQT09IiwiaXNzIjoiaHR0cHM6XC9cL2ZhbnRhc3kuc3BmbC5jby51ayIsInN1YiI6eyJpZCI6Ijg4NjciLCJtYWlsIjoiaWFpbi5jb29rQGhvdG1haWwuY28udWsiLCJtYW5hZ2VyIjoiQmF5ZXJuIEJydSIsImlkbCI6IjEiLCJpZGciOiI2NTciLCJmdXNlYXUiOiJFdXJvcGVcL01hZHJpZCIsIm1lcmNhdG8iOjAsImlkamciOiI5NDY5IiwiaXNhZG1pbmNsaWVudCI6ZmFsc2UsImlzYWRtaW4iOmZhbHNlLCJpc3N1cGVyYWRtaW4iOmZhbHNlLCJpbnZpdGUiOmZhbHNlLCJ2aXAiOmZhbHNlLCJpZGVudGl0eSI6NjQwLCJpZ25vcmVjb2RlIjpmYWxzZSwiY29kZSI6IjY0MC41IiwiY29kZUY1IjoiNjQwLjIiLCJkZWNvIjowfX0.Of9kuQZjxA-Tf--HTic4DeknbMfdU0GfPR99Vai7V9c"),
        "x-access-key": os.getenv("SPFL_ACCESS_KEY", "640@21.01@@9bb4ed46-7d95-47b0-8a33-a8e071b9cc81")
    }

    # Request all players in one payload
    payload = {
        "filters": {
            "nom": "",
            "club": "",
            "position": "",
            "budget_ok": False,
            "valeur_max": 25,
            "engage": False,
            "partant": False,
            "dreamteam": False,
            "quota": "",
            "sort": "valeur",
            "idj": "3",
            "pageIndex": 0,
            "pageSize": 500,
            "loadSelect": 1,
            "searchonly": 0
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()

    # 2. Map positions: 1: GK, 2: DEF, 3: MID, 4: FWD
    pos_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    
    players = data.get("joueurs", [])
    formatted_pool = []
    
    for p in players:
        name = p.get("nomcomplet") or p.get("nom")
        club = p.get("club", "Unknown")
        pos = pos_map.get(p.get("id_position"), "MID")
        val = float(p.get("valeur", 0.0))
        
        formatted_pool.append(f"{name} | {pos} | {club} | £{val:.1f}m")

    spfl_context = "\n".join(formatted_pool)

    # 3. Construct the SPFL Optimization Prompt
    prompt = f"""You are the lead data scientist and manager for the SPFL fantasy football team 'Bayern Bru'.
Select the mathematically optimal 15-man squad for Gameweek 3 based strictly on the live SPFL data below.

Core SPFL Rules & Mechanics:
- Total Budget: Maximum £100.0m.
- Squad Structure: Exactly 15 players (2 GKs, 5 DEFs, 5 MIDs, 3 FWDs).
- Team Limit: Maximum 3 players from any single Scottish Premiership team (e.g., Celtic, Rangers, Aberdeen, Hearts, Hibs, etc.).
- BENCH SCORING RULE: All 4 bench players earn 50% of their points each week, and there are NO auto-subs. Do NOT select non-playing £4.0m deadwood. All 15 players must play regular minutes.
- SUPERSUB RULE: Designate 1 bench player as the 'Supersub' (select an attacking player or winger who frequently comes on as an impactful real-life substitute to trigger the 3x multiplier).
- CAPTAIN BONUS: Captain scores double points PLUS a +20 flat bonus. Select the highest ceiling goal/assist threat in the league.

Output Structure Required:
1. 15-Man Squad Grouped by Premiership Club (Alphabetical by team with player name, position, and exact price).
2. Total Squad Cost Verification (£100.0m limit).
3. Formation & Starting XI.
4. Captain (C) and Vice-Captain (VC).
5. Bench (4 players) in priority order, explicitly designating the 'Supersub'.

Player Data Pool:
{spfl_context}
"""

    # 4. Generate deterministic selection
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
        )
    )

    print("--- Bayern Bru: SPFL Gameweek 3 Squad & Tactics ---")
    print(response.text)

if __name__ == "__main__":
    run_spfl_manager()

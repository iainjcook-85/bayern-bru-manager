import os
import requests
from google import genai
from google.genai import types

def run_spfl_manager():
    url = "https://fantasy.spfl.co.uk/v1/private/searchjoueurs?lg=en"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "authorization": os.getenv("SPFL_AUTH_TOKEN", "Token eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3ODcyMjIwNDgsImV4cCI6MTc4OTkwMDQ0OCwianRpIjoiTFhKNlVBVHI4VFd6QUVmVUhwRFJQQT09IiwiaXNzIjoiaHR0cHM6XC9cL2ZhbnRhc3kuc3BmbC5jby51ayIsInN1YiI6eyJpZCI6Ijg4NjciLCJtYWlsIjoiaWFpbi5jb29rQGhvdG1haWwuY28udWsiLCJtYW5hZ2VyIjoiQmF5ZXJuIEJydSIsImlkbCI6IjEiLCJpZGciOiI2NTciLCJmdXNlYXUiOiJFdXJvcGVcL01hZHJpZCIsIm1lcmNhdG8iOjAsImlkamciOiI5NDY5IiwiaXNhZG1pbmNsaWVudCI6ZmFsc2UsImlzYWRtaW4iOmZhbHNlLCJpc3N1cGVyYWRtaW4iOmZhbHNlLCJpbnZpdGUiOmZhbHNlLCJ2aXAiOmZhbHNlLCJpZGVudGl0eSI6NjQwLCJpZ25vcmVjb2RlIjpmYWxzZSwiY29kZSI6IjY0MC41IiwiY29kZUY1IjoiNjQwLjIiLCJkZWNvIjowfX0.Of9kuQZjxA-Tf--HTic4DeknbMfdU0GfPR99Vai7V9c"),
        "x-access-key": os.getenv("SPFL_ACCESS_KEY", "640@21.01@@9bb4ed46-7d95-47b0-8a33-a8e071b9cc81")
    }

    payload = {
        "filters": {
            "nom": "", "club": "", "position": "", "budget_ok": False,
            "valeur_max": 25, "engage": False, "partant": False,
            "dreamteam": False, "quota": "", "sort": "valeur",
            "idj": "3", "pageIndex": 0, "pageSize": 500, "loadSelect": 1, "searchonly": 0
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()

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

    prompt = f"""You are the manager for SPFL fantasy team 'Bayern Bru'.
Gameweek 3 is a MASSIVE BLANK GAMEWEEK: 5 of 6 matches are postponed. 
The ONLY fixture taking place is Dundee United vs Dundee.

Rules & Optimization Strategy:
1. MAXIMIZE ACTIVE GW3 POINTS: Select exactly 3 players from Dundee United and 3 players from Dundee in the Starting XI.
2. CAPTAINCY (+20pt flat bonus + 2x multiplier): MUST be assigned to an active attacker/playmaker from Dundee United or Dundee.
3. SUPERSUB (3x multiplier): Designate a bench player from Dundee or Dundee United who is likely to come on as an impact substitute.
4. REMAINING 9 PLAYERS: Fill with elite, nailed assets from Celtic, Rangers, Aberdeen, and Hearts who will score 0 this week but provide immediate high value for Gameweek 4 and future Double Gameweeks.
5. Strict £100.0m total budget and max 3 players per club.

Output Structure Required:
1. 15-Man Squad Grouped by Club (Alphabetical with position and price).
2. Total Squad Cost Verification (£100.0m limit).
3. Formation & Starting XI (Highlighting the 6 playing Dundee Derby assets).
4. Captain (C) & Vice-Captain (VC).
5. Bench (4 players) with explicit designation of the 'Supersub'.

Player Data Pool:
{spfl_context}
"""

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0)
    )

    print("--- Bayern Bru: SPFL Blank Gameweek 3 Master Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_spfl_manager()

import os
import requests
from google import genai
from google.genai import types

def run_fpl_manager():
    # 1. Fetch live FPL element data & fixture metrics
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    data = response.json()

    teams = {t['id']: t['name'] for t in data['teams']}
    positions = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    # 2. Map all available players
    all_players = {}
    market_pool = []
    
    for p in data["elements"]:
        name = p["web_name"]
        cost = p["now_cost"] / 10
        pos = positions.get(p["element_type"], "MID")
        team = teams.get(p["team"], "Unknown")
        status = p["status"]
        chance = p.get("chance_of_playing_next_round")
        ep_next = float(p.get("ep_next") or 0.0)
        form = float(p.get("form") or 0.0)
        ict = float(p.get("ict_index") or 0.0)

        player_summary = (
            f"{name} | {pos} | {team} | Cost: £{cost:.1f}m | Status: {status} "
            f"(Playing Chance: {chance}%) | xP: {ep_next} | Form: {form} | ICT: {ict}"
        )
        
        all_players[name.lower()] = player_summary

        # Add active, high-performing targets to transfer candidate list
        if status == 'a' and (chance is None or chance == 100) and (ep_next >= 4.0 or form >= 5.0):
            market_pool.append(player_summary)

    # 3. Define Current 'Bayern Bru' Locked Squad (GW1 Base)
    current_squad_names = [
        "Petrović", "Woodman",
        "Gabriel", "Gvardiol", "Konsa", "Davis", "O.Richards",
        "Saka", "Palmer", "Rogers", "Smith Rowe", "Hughes",
        "Haaland", "Isak", "Obi"
    ]

    current_squad_stats = []
    for name in current_squad_names:
        # Fuzzy match or fallback
        stat = all_players.get(name.lower(), f"{name} | Current Squad Member")
        current_squad_stats.append(stat)

    current_squad_context = "\n".join(current_squad_stats)
    market_context = "\n".join(market_pool[:60]) # Top 60 market movers

    # 4. Construct Stage 2 Weekly Decision Prompt
    prompt = f"""You are the lead data scientist and manager for the FPL team 'Bayern Bru'.
Gameweek 1 has concluded. We are preparing our tactical plan for Gameweek 2.

Team Parameters:
- Free Transfers Available: 1
- Bank Balance: £0.0m
- Max 3 players per Premier League club.

Current Squad (15 Players):
{current_squad_context}

Top Market Transfer Targets (Live FPL Pool):
{market_context}

Management Directives:
1. SQUAD AUDIT: Flag any injuries, suspensions, or red/yellow flags in the current 15.
2. TRANSFER STRATEGY (1 Free Transfer):
   - Option A (ROLL TRANSFER): If the starting XI is fully fit and fixtures are favorable, RECOMMEND ROLLING the free transfer to enter Gameweek 3 with 2 FTs (highest strategic value).
   - Option B (MAKE TRANSFER): If a starter is injured or a critical fixture upgrade is mathematically clear, execute 1 transfer within the £0.0m bank limit.
3. STARTING XI & FORMATION: Choose the optimal 11 starters (3-5-2, 3-4-3, or 4-4-2) maximizing expected points (xP).
4. CAPTAINCY: Select Captain (C) and Vice-Captain (VC) based strictly on GW2 fixture ceiling.
5. BENCH ORDER: Sequence Sub GK, Bench 1, Bench 2, Bench 3 in exact order of expected substitute impact.

Output Structure Required:
1. Squad Health & Status Check (Bullet points on flagged/injured assets).
2. Transfer Verdict: [ROLL TRANSFER] or [EXECUTE TRANSFER: Player OUT -> Player IN (Cost Math)].
3. Gameweek 2 Starting XI & Formation (with tactical justifications).
4. Captain (C) & Vice-Captain (VC).
5. Substitutes in Priority Order.
"""

    # 5. Deterministic Evaluation
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0)
    )

    print("--- Bayern Bru: Gameweek 2 Tactical & Transfer Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_fpl_manager()

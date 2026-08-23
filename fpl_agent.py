import os
import requests
from google import genai
from google.genai import types

def run_fpl_manager():
    TEAM_ID = 6671455
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 1. Fetch live FPL bootstrap data
    url_bootstrap = "https://fantasy.premierleague.com/api/bootstrap-static/"
    resp_boot = requests.get(url_bootstrap, headers=headers)
    data = resp_boot.json()

    teams = {t['id']: t['name'] for t in data['teams']}
    positions = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    players_by_id = {p['id']: p for p in data['elements']}

    # Determine current and next Gameweek
    current_gw = 1
    next_gw = 2
    for event in data["events"]:
        if event.get("is_current"):
            current_gw = event["id"]
        if event.get("is_next"):
            next_gw = event["id"]

    # 2. Fetch your live team picks directly from the FPL API
    url_picks = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/event/{current_gw}/picks/"
    resp_picks = requests.get(url_picks, headers=headers)
    
    if resp_picks.status_code != 200:
        print(f"Failed to fetch team picks for ID {TEAM_ID}. Status: {resp_picks.status_code}")
        return

    picks_data = resp_picks.json()
    entry_history = picks_data.get("entry_history", {})
    bank_balance = entry_history.get("bank", 0) / 10
    total_points = entry_history.get("total_points", 0)

    # 3. Build live squad payload with real-time stats
    current_squad_stats = []
    for pick in picks_data.get("picks", []):
        p_id = pick["element"]
        pos_order = pick["position"]
        is_cap = " (C)" if pick.get("is_captain") else ""
        is_vc = " (VC)" if pick.get("is_vice_captain") else ""
        is_bench = " [BENCH]" if pos_order > 11 else " [STARTER]"

        p = players_by_id.get(p_id, {})
        name = p.get("web_name", f"ID_{p_id}")
        pos = positions.get(p.get("element_type"), "MID")
        team = teams.get(p.get("team"), "Unknown")
        cost = p.get("now_cost", 0) / 10
        status = p.get("status", "a")
        chance = p.get("chance_of_playing_next_round", 100)
        ep_next = float(p.get("ep_next") or 0.0)
        form = float(p.get("form") or 0.0)
        ict = float(p.get("ict_index") or 0.0)

        current_squad_stats.append(
            f"Slot {pos_order}{is_bench}: {name}{is_cap}{is_vc} | {pos} | {team} | Cost: £{cost:.1f}m | "
            f"Status: {status} (Chance: {chance}%) | xP (GW{next_gw}): {ep_next} | Form: {form} | ICT: {ict}"
        )

    # 4. Extract top live market transfer targets
    market_pool = []
    for p in data["elements"]:
        if p["status"] == 'a' and float(p.get("chance_of_playing_next_round") or 100) == 100:
            cost = p["now_cost"] / 10
            ep_next = float(p.get("ep_next") or 0.0)
            form = float(p.get("form") or 0.0)
            ict = float(p.get("ict_index") or 0.0)
            
            if ep_next >= 4.0 or form >= 5.0 or ict >= 15.0:
                name = p["web_name"]
                pos = positions.get(p["element_type"], "MID")
                team = teams.get(p["team"], "Unknown")
                market_pool.append(
                    f"{name} | {pos} | {team} | Cost: £{cost:.1f}m | xP: {ep_next} | Form: {form} | ICT: {ict}"
                )

    current_squad_context = "\n".join(current_squad_stats)
    market_context = "\n".join(market_pool[:50])

    # 5. Tactical Stage 2 Prompt
    prompt = f"""You are the lead manager for the FPL team 'Bayern Bru' (Team ID: {TEAM_ID}).
We are preparing our strategy for Gameweek {next_gw}.

Account Status:
- Total Points: {total_points}
- In the Bank (ITB): £{bank_balance:.1f}m
- Free Transfers Available: 1
- Max 3 players per Premier League club.

Current Live Squad (Synced from FPL API):
{current_squad_context}

Top Market Transfer Targets (Live FPL Pool):
{market_context}

Directives:
1. SQUAD AUDIT: Flag any injuries, suspensions, or rotation risks.
2. TRANSFER DECISION (1 Free Transfer):
   - ROLL TRANSFER: If the starting XI is fit and has strong GW{next_gw} fixtures, roll the transfer to bank 2 FTs for Gameweek 3.
   - EXECUTE TRANSFER: If an active transfer within £{bank_balance:.1f}m ITB provides significant expected points improvement, execute [Player OUT -> Player IN].
3. STARTING XI & FORMATION: Structure the best 11 starters (3-5-2, 3-4-3, or 4-4-2) based on xP.
4. CAPTAINCY: Select Captain (C) and Vice-Captain (VC) for Gameweek {next_gw}.
5. BENCH SEQUENCING: Sequence Sub GK, Bench 1, Bench 2, Bench 3 in exact order of priority.

Output Structure Required:
1. Squad Health & Status Check
2. Transfer Verdict: [ROLL TRANSFER] or [EXECUTE TRANSFER] (with full financial math)
3. Gameweek {next_gw} Starting XI & Formation
4. Captain (C) & Vice-Captain (VC)
5. Substitutes in Priority Order
"""

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0)
    )

    print(f"--- Bayern Bru: Gameweek {next_gw} Automated Tactical Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_fpl_manager()

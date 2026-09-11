import os
import requests
from google import genai
from google.genai import types

def run_fpl_manager():
    TEAM_ID = 6671455
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 1. Fetch live FPL static bootstrap and fixtures
    url_bootstrap = "https://fantasy.premierleague.com/api/bootstrap-static/"
    resp_boot = requests.get(url_bootstrap, headers=headers)
    data = resp_boot.json()

    url_fixtures = "https://fantasy.premierleague.com/api/fixtures/"
    fixtures_data = requests.get(url_fixtures, headers=headers).json()

    teams = {t['id']: t['name'] for t in data['teams']}
    team_short = {t['id']: t['short_name'] for t in data['teams']}
    positions = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    players_by_id = {p['id']: p for p in data['elements']}

    # Determine current and upcoming Gameweeks
    current_gw = 1
    next_gw = 2
    for event in data["events"]:
        if event.get("is_current"):
            current_gw = event["id"]
        if event.get("is_next"):
            next_gw = event["id"]

    # 2. Fetch team history & dynamically calculate banked Free Transfers (Cap: 5)
    url_history = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/history/"
    resp_history = requests.get(url_history, headers=headers)
    
    available_fts = 1
    bank_balance = 0.0
    total_points = 0

    if resp_history.status_code == 200:
        hist_data = resp_history.json()
        completed_events = hist_data.get("current", [])
        if completed_events:
            last_event = completed_events[-1]
            bank_balance = last_event.get("bank", 0) / 10
            total_points = last_event.get("total_points", 0)

        for ev in completed_events:
            gw_num = ev.get("event")
            if gw_num < 2 or gw_num >= next_gw:
                continue
            transfers_made = ev.get("event_transfers", 0)
            transfers_cost = ev.get("event_transfers_cost", 0)
            free_used = max(0, transfers_made - (transfers_cost // 4))
            remaining = max(0, available_fts - free_used)
            available_fts = min(5, remaining + 1)

    # 3. Build 4-Week Fixture Horizon (GW_next to GW_next+3)
    horizon_gws = list(range(next_gw, next_gw + 4))
    team_schedule = {t_id: [] for t_id in teams}

    for fix in fixtures_data:
        event = fix.get("event")
        if event in horizon_gws:
            h_team = fix["team_h"]
            a_team = fix["team_a"]
            h_diff = fix["team_h_difficulty"]
            a_diff = fix["team_a_difficulty"]

            team_schedule[h_team].append(f"GW{event}:{team_short[a_team]}(H)[FDR{h_diff}]")
            team_schedule[a_team].append(f"GW{event}:{team_short[h_team]}(A)[FDR{a_diff}]")

    def get_schedule_str(team_id):
        return ", ".join(team_schedule.get(team_id, []))

    # 4. Fetch live picks directly from the FPL API
    target_picks_gw = current_gw if current_gw > 0 else 1
    url_picks = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/event/{target_picks_gw}/picks/"
    resp_picks = requests.get(url_picks, headers=headers)
    
    if resp_picks.status_code != 200:
        url_picks = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/event/{max(1, target_picks_gw - 1)}/picks/"
        resp_picks = requests.get(url_picks, headers=headers)

    if resp_picks.status_code != 200:
        print(f"Failed to fetch picks for Team ID {TEAM_ID}.")
        return

    picks_data = resp_picks.json()

    # 5. Build live squad payload with Threat, Creativity & Fixtures
    current_squad_stats = []
    for pick in picks_data.get("picks", []):
        p_id = pick["element"]
        pos_order = pick["position"]
        is_cap = " (C)" if pick.get("is_captain") else ""
        is_vc = " (VC)" if pick.get("is_vice_captain") else ""
        is_bench = " [BENCH]" if pos_order > 11 else " [STARTER]"

        p = players_by_id.get(p_id, {})
        name = p.get("web_name", f"ID_{p_id}")
        t_id = p.get("team")
        pos = positions.get(p.get("element_type"), "MID")
        team = teams.get(t_id, "Unknown")
        cost = p.get("now_cost", 0) / 10
        status = p.get("status", "a")
        chance = p.get("chance_of_playing_next_round", 100)
        ep_next = float(p.get("ep_next") or 0.0)
        threat = float(p.get("threat") or 0.0)
        creat = float(p.get("creativity") or 0.0)
        goals = p.get("goals_scored", 0)
        assists = p.get("assists", 0)
        schedule = get_schedule_str(t_id)

        current_squad_stats.append(
            f"Slot {pos_order}{is_bench}: {name}{is_cap}{is_vc} | {pos} | {team} | Cost: £{cost:.1f}m | "
            f"Status: {status} ({chance}%) | xP(GW{next_gw}): {ep_next} | Threat: {threat:.0f} | "
            f"Creativity: {creat:.0f} | G+A: {goals}+{assists} | Run: [{schedule}]"
        )

    # 6. Extract top live market transfer targets (Filtering out non-attacking CDMs)
    market_pool = []
    for p in data["elements"]:
        if p["status"] == 'a' and float(p.get("chance_of_playing_next_round") or 100) == 100:
            cost = p["now_cost"] / 10
            ep_next = float(p.get("ep_next") or 0.0)
            form = float(p.get("form") or 0.0)
            threat = float(p.get("threat") or 0.0)
            creat = float(p.get("creativity") or 0.0)
            t_id = p.get("team")
            pos_type = p.get("element_type")

            # Ignore defensive midfielders with negligible threat/creativity
            if pos_type == 3 and threat < 30.0 and creat < 30.0 and form < 4.0:
                continue

            if ep_next >= 3.8 or form >= 4.5 or threat >= 60.0:
                name = p["web_name"]
                pos = positions.get(pos_type, "MID")
                team = teams.get(t_id, "Unknown")
                goals = p.get("goals_scored", 0)
                assists = p.get("assists", 0)
                schedule = get_schedule_str(t_id)
                market_pool.append(
                    f"{name} | {pos} | {team} | Cost: £{cost:.1f}m | xP(GW{next_gw}): {ep_next} | "
                    f"Threat: {threat:.0f} | Creat: {creat:.0f} | G+A: {goals}+{assists} | Run: [{schedule}]"
                )

    current_squad_context = "\n".join(current_squad_stats)
    market_context = "\n".join(market_pool[:60])

    # 7. Construct Guardrailed Tactical Prompt
    prompt = f"""You are the lead tactical analyst for FPL team 'Bayern Bru' (ID: {TEAM_ID}).
We are preparing our strategy for Gameweek {next_gw} with a 4-Gameweek horizon (GW{next_gw} to GW{next_gw + 3}).

Manager Dashboard:
- Current Overall Points: {total_points}
- In the Bank (ITB): £{bank_balance:.1f}m
- Free Transfers Available (FT): {available_fts}
- Max Free Transfers Bankable: 5
- Squad Constraints: Exactly 15 players, max 3 players per Premier League club.

Current Live Squad (Synced from FPL API):
{current_squad_context}

Top Market Targets (Live Filtered Pool):
{market_context}

CRITICAL RULES & FORMATION CONSTRAINTS:
1. STRICT ROSTER ACCOUNTING:
   - Exactly 11 starters and exactly 4 bench players.
   - EVERY PLAYER MUST APPEAR EXACTLY ONCE. A player CANNOT be listed as both a starter and on the bench.
   - You only have 2 active playing forwards (Haaland, Isak; Obi is non-playing bench fodder). Therefore, 3-4-3 is STRICTLY IMPOSSIBLE.
   - Permissible formations for this squad: 4-4-2, 3-5-2, or 5-3-2.

2. ANTI-CDM TRANSFER RULE:
   - NEVER sell an attacking midfielder (winger/number 10 like Smith Rowe) for a defensive/holding midfielder (CDM like Janelt, Norgaard, Soucek), even if their short-term xP is inflated by clean-sheet projections.
   - Midfield targets MUST have genuine attacking threat and high open-play involvement.

3. TRANSFER DECISION LOGIC:
   - Available FTs: {available_fts}.
   - If no starter is injured/suspended, and no target offers a clear multi-week attacking upgrade within £{bank_balance:.1f}m ITB, you MUST recommend **[ROLL TRANSFER]** to bank transfers for subsequent weeks.

Output Structure:
1. **4-Week Fixture & Squad Health Audit**
2. **Transfer Decision**: **[ROLL TRANSFER]** or **[EXECUTE TRANSFER: OUT -> IN]** with financial math
3. **Gameweek {next_gw} Starting XI & Formation** (Must be a legal 11-man formation)
4. **Captain (C) & Vice-Captain (VC)**
5. **Bench Priority Order** (Sub GK, Bench 1, Bench 2, Bench 3 - exactly 4 unique players not in Starting XI)
"""

    # 8. Deterministic Generation
    client = genai.Client()
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(temperature=0.0)
    )
    response = chat.send_message(prompt)

    print(f"--- Bayern Bru: Gameweek {next_gw} 4-Week Horizon Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_fpl_manager()

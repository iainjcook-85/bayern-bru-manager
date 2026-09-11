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

        # Calculate exact FT accumulation from GW2 onwards
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

    # 5. Build live squad payload with 4-week fixture runs
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
        form = float(p.get("form") or 0.0)
        schedule = get_schedule_str(t_id)

        current_squad_stats.append(
            f"Slot {pos_order}{is_bench}: {name}{is_cap}{is_vc} | {pos} | {team} | Cost: £{cost:.1f}m | "
            f"Status: {status} ({chance}%) | xP(GW{next_gw}): {ep_next} | Form: {form} | Run: [{schedule}]"
        )

    # 6. Extract top live market transfer targets
    market_pool = []
    for p in data["elements"]:
        if p["status"] == 'a' and float(p.get("chance_of_playing_next_round") or 100) == 100:
            cost = p["now_cost"] / 10
            ep_next = float(p.get("ep_next") or 0.0)
            form = float(p.get("form") or 0.0)
            ict = float(p.get("ict_index") or 0.0)
            t_id = p.get("team")

            if ep_next >= 3.8 or form >= 4.5 or ict >= 12.0:
                name = p["web_name"]
                pos = positions.get(p["element_type"], "MID")
                team = teams.get(t_id, "Unknown")
                schedule = get_schedule_str(t_id)
                market_pool.append(
                    f"{name} | {pos} | {team} | Cost: £{cost:.1f}m | xP(GW{next_gw}): {ep_next} | Run: [{schedule}]"
                )

    current_squad_context = "\n".join(current_squad_stats)
    market_context = "\n".join(market_pool[:60])

    # 7. Construct Tactical Prompt
    prompt = f"""You are the lead tactical analyst for FPL team 'Bayern Bru' (ID: {TEAM_ID}).
We are preparing our strategy for Gameweek {next_gw} with a mandatory 4-Gameweek horizon (GW{next_gw} to GW{next_gw + 3}).

Manager Dashboard:
- Current Overall Points: {total_points}
- In the Bank (ITB): £{bank_balance:.1f}m
- Free Transfers Available (FT): {available_fts}
- Max Free Transfers Bankable: 5
- Squad Constraints: Exactly 15 players, max 3 players per Premier League club.

Current Live Squad (Synced from FPL API with 4-Week Fixture Radar):
{current_squad_context}

Top Market Targets (With 4-Week Fixture Schedules):
{market_context}

Strategic Objectives & Directives:
1. 4-WEEK SQUAD AUDIT:
   - Identify flagged, doubtful, or benched assets.
   - Evaluate fixture difficulty across GW{next_gw}–GW{next_gw+3} (FDR 2 = Easy green, FDR 4/5 = Hard red).
2. TRANSFER DECISION:
   - You currently have {available_fts} Free Transfer(s) available.
   - ROLL TRANSFER: If the current starting XI is healthy and has favorable fixtures, recommend rolling to accumulate further transfers (up to 5 max).
   - EXECUTE TRANSFER: If you have 2+ FTs or an injured/flagged player, evaluate executing single or coordinated double-moves within £{bank_balance:.1f}m ITB.
3. STARTING XI & FORMATION:
   - Select 11 starters based on Gameweek {next_gw} expected points and fixture match-ups.
4. CAPTAINCY SELECTION:
   - Assign Captain (C) and Vice-Captain (VC).
5. BENCH ORDER:
   - Order substitutes strictly by expected points for GW{next_gw}.

Output Format:
1. **4-Week Fixture & Squad Health Audit**
2. **Transfer Decision**: State **[ROLL TRANSFER]** (projecting banked FTs for next week) or **[EXECUTE TRANSFER: OUT -> IN]** with full financial math
3. **Gameweek {next_gw} Starting XI & Optimal Formation**
4. **Captain (C) & Vice-Captain (VC)**
5. **Bench Priority Order**
"""

    # 8. Deterministic Generation using chat interface
    client = genai.Client()
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(temperature=0.0)
    )
    response = chat.send_message(prompt)

    print(f"--- Bayern Bru: Gameweek {next_gw} 4-Week Horizon Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_fpl_manager()

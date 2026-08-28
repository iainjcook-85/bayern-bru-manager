import os
import requests
from google import genai
from google.genai import types

def run_fpl_manager():
    TEAM_ID = 6671455
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 1. Fetch live FPL bootstrap & fixture schedules
    url_bootstrap = "https://fantasy.premierleague.com/api/bootstrap-static/"
    resp_boot = requests.get(url_bootstrap, headers=headers)
    data = resp_boot.json()

    url_fixtures = "https://fantasy.premierleague.com/api/fixtures/"
    fixtures_data = requests.get(url_fixtures, headers=headers).json()

    teams = {t['id']: t['name'] for t in data['teams']}
    team_short = {t['id']: t['short_name'] for t in data['teams']}
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

    # 2. Build 4-Week Fixture Horizon per Team (GW2 to GW5)
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

    # Format schedule string helper
    def get_schedule_str(team_id):
        return ", ".join(team_schedule.get(team_id, []))

    # 3. Fetch live team picks directly from FPL API
    url_picks = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/event/{current_gw}/picks/"
    resp_picks = requests.get(url_picks, headers=headers)
    
    if resp_picks.status_code != 200:
        print(f"Failed to fetch picks for Team ID {TEAM_ID}. Status: {resp_picks.status_code}")
        return

    picks_data = resp_picks.json()
    entry_history = picks_data.get("entry_history", {})
    bank_balance = entry_history.get("bank", 0) / 10
    total_points = entry_history.get("total_points", 0)

    # 4. Build live squad context with 4-week fixture radar
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
            f"Slot {pos_order}{is_bench}: {name}{is_cap}{is_vc} | {pos} | {team} | £{cost:.1f}m | "
            f"Status: {status} ({chance}%) | xP(GW{next_gw}): {ep_next} | Form: {form} | Run: [{schedule}]"
        )

    # 5. Build market target context with 4-week schedules
    market_pool = []
    for p in data["elements"]:
        if p["status"] == 'a' and float(p.get("chance_of_playing_next_round") or 100) == 100:
            cost = p["now_cost"] / 10
            ep_next = float(p.get("ep_next") or 0.0)
            form = float(p.get("form") or 0.0)
            ict = float(p.get("ict_index") or 0.0)
            t_id = p.get("team")

            if ep_next >= 3.8 or form >= 5.0 or ict >= 12.0:
                name = p["web_name"]
                pos = positions.get(p["element_type"], "MID")
                team = teams.get(t_id, "Unknown")
                schedule = get_schedule_str(t_id)
                market_pool.append(
                    f"{name} | {pos} | {team} | £{cost:.1f}m | xP(GW{next_gw}): {ep_next} | Run: [{schedule}]"
                )

    current_squad_context = "\n".join(current_squad_stats)
    market_context = "\n".join(market_pool[:60])

    # 6. Strategic Multi-Week Prompt
    prompt = f"""You are the lead tactical analyst for FPL team 'Bayern Bru' (ID: {TEAM_ID}).
We are planning for Gameweek {next_gw} with a mandatory 4-Gameweek forward horizon (GW{next_gw} to GW{next_gw + 3}).

Manager Dashboard:
- Current Overall Points: {total_points}
- In the Bank (ITB): £{bank_balance:.1f}m
- Free Transfers (FT): 1
- Squad Constraints: Exactly 15 players, max 3 players per club.

Current Live Squad (Synced from FPL API with 4-Week Fixture Radar):
{current_squad_context}

Top Market Targets (With 4-Week Schedules):
{market_context}

Strategic Objectives & Directives:
1. MULTI-WEEK SQUAD AUDIT:
   - Identify flagged or injured players.
   - Evaluate each asset's next 4 fixtures (FDR 2 = Easy green fixture, FDR 4/5 = Tough red fixture).
   - Flag players with declining fixture runs vs. players entering prime 4-week green streaks.

2. TRANSFER VERDICT (1 Free Transfer):
   - ROLL TRANSFER: Strongly preferred if the starting XI is fit and has favorable multi-week outlooks. Banking the transfer grants 2 FTs in GW3 when player roles, set-piece takers, and price swings are clearer.
   - EXECUTE TRANSFER: Only recommend if an asset has a severe injury/benching risk OR if moving to an elite target unlocks an immediate + sustained 4-week xP swing within £{bank_balance:.1f}m ITB.

3. STARTING XI & OPTIMAL FORMATION:
   - Select 11 starters based on Gameweek {next_gw} match difficulty and xP.

4. CAPTAINCY SELECTION:
   - Assign Captain (C) and Vice-Captain (VC) targeting the single highest ceiling fixture in GW{next_gw}.

5. BENCH ORDERING:
   - Order substitutes (Sub GK, Bench 1, Bench 2, Bench 3) strictly by GW{next_gw} expected points.

Output Format:
1. **4-Week Fixture & Squad Health Audit** (Key findings across the GW{next_gw}–GW{next_gw+3} horizon)
2. **Transfer Decision**: Explicitly state **[ROLL TRANSFER]** or **[EXECUTE TRANSFER: OUT -> IN]** with financial math
3. **Gameweek {next_gw} Starting XI & Formation** (e.g., 3-5-2 or 3-4-3)
4. **Captain (C) & Vice-Captain (VC)**
5. **Bench Priority Order**
"""

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0)
    )

    print(f"--- Bayern Bru: Gameweek {next_gw} 4-Week Horizon Plan ---")
    print(response.text)

if __name__ == "__main__":
    run_fpl_manager()

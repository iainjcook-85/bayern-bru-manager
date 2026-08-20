import os
import requests
from google import genai

def run_manager():
    # 1. Fetch live FPL data
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    data = requests.get(url).json()

    # 2. Extract active players to save token space
    active_players = [
        f"{p['web_name']} - £{p['now_cost']/10}m - {p['total_points']}pts - Status: {p['status']}" 
        for p in data["elements"] if p["status"] != 'u'
    ]
    fpl_context = "\n".join(active_players)

    # 3. Construct the prompt
    prompt = f"You are the manager for my FPL team, Bayern Bru. Analyze this data and suggest 1 optimal transfer for the upcoming Gameweek:\n{fpl_context}"

    # 4. Generate the AI strategy
    # The client automatically picks up the GEMINI_API_KEY environment variable
    client = genai.Client() 
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=prompt
    )

    print("--- Bayern Bru Weekly Strategy ---")
    print(response.text)

if __name__ == "__main__":
    run_manager()

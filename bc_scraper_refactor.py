import argparse
import json
import os
import requests
import pandas as pd
from time import sleep

API_RATE_LIMIT = 0.5  # seconds between requests (2 calls per second limit)

def fetch_json(url, headers, params=None):
    """Fetches and returns JSON data from a URL with headers and optional parameters."""
    sleep(API_RATE_LIMIT)
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()

def get_replay_ids(group_url, auth_key):
    """Fetch replay IDs from a Ballchasing group URL."""
    group_id = group_url.split("/")[-1]
    url = "https://ballchasing.com/api/replays/"
    headers = {'Authorization': auth_key}
    params = {'group': group_id}

    data = fetch_json(url, headers, params)
    return pd.json_normalize(data["list"])

def get_group_stats(group_url, auth_key, stat_type):
    """Fetch player or team stats from a group URL based on stat_type."""
    headers = {'Authorization': auth_key}

    if stat_type == "player":
        player_stats = []
        replay_ids = get_replay_ids(group_url, auth_key)['id']

        for replay_id in replay_ids:
            replay_url = f"https://ballchasing.com/api/replays/{replay_id}"
            replay_data = fetch_json(replay_url, headers)
            for team_color in ["blue", "orange"]:
                players = replay_data.get(team_color, {}).get("players", [])
                for player in players:
                    flat_stats = {}
                    flat_stats.update({
                        "replay_id": replay_id,
                        "team": team_color,
                        "player_name": player.get("name"),
                        "player_platform_id": player.get("id", {}).get("id"),
                        "player_platform": player.get("id", {}).get("platform"),
                        "car_id": player.get("car_id"),
                        "car_name": player.get("car_name"),
                    })
                    stats_categories = player.get("stats", {})
                    for category, stats in stats_categories.items():
                        for stat_key, stat_value in stats.items():
                            flat_stats[f"{category}_{stat_key}"] = stat_value
                    player_stats.append(flat_stats)

        return pd.DataFrame(player_stats) if player_stats else pd.DataFrame()

    elif stat_type == "team":
        group_id = group_url.split("/")[-1]
        url = f"https://ballchasing.com/api/groups/{group_id}"
        data = fetch_json(url, headers)
        return pd.json_normalize(data.get("teams", []))


def get_game_stats(group_url, auth_key):
    """Fetch game-by-game stats for a group."""
    replay_data = get_replay_ids(group_url, auth_key)
    replay_ids = replay_data['id'].tolist()

    headers = {'Authorization': auth_key}
    game_stats = []

    for replay_id in replay_ids:
        url = f"https://ballchasing.com/api/replays/{replay_id}"
        game_data = fetch_json(url, headers)
        game_stats.append(pd.json_normalize(game_data))

    return pd.concat(game_stats, ignore_index=True) if game_stats else pd.DataFrame()

def save_to_csv(df, filename):
    """Saves a DataFrame to a CSV file."""
    os.makedirs("output", exist_ok=True)
    filepath = os.path.join("output", filename)
    df.to_csv(filepath, index=False)
    print(f"Saved data to {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Extract stats from Ballchasing API.")
    parser.add_argument("json_file", help="Path to the JSON file containing group URLs.")
    args = parser.parse_args()
    auth_key = os.getenv("BALLCHASING_API_KEY")

    with open(args.json_file, 'r') as file:
        group_urls = json.load(file)

    for group_url in group_urls:
        print(f"Processing group: {group_url}")

        replay_ids_df = get_replay_ids(group_url, auth_key)
        save_to_csv(replay_ids_df, f"replay_ids_{group_url.split('/')[-1]}.csv")

        player_stats_df = get_group_stats(group_url, auth_key, "player")
        save_to_csv(player_stats_df, f"player_stats_{group_url.split('/')[-1]}.csv")

        team_stats_df = get_group_stats(group_url, auth_key, "team")
        save_to_csv(team_stats_df, f"team_stats_{group_url.split('/')[-1]}.csv")

        game_stats_df = get_game_stats(group_url, auth_key)
        save_to_csv(game_stats_df, f"game_stats_{group_url.split('/')[-1]}.csv")

if __name__ == "__main__":
    main()
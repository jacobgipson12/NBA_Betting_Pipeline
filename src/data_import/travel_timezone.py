"""Derives per-game travel distance, direction, and timezone shift for each team.

Not an API dataset - combines game_logs.csv (schedule) with the hand-authored
config/team_locations.csv (arena lat/lon + IANA timezone) to work out, for
each team's each game, how far and which direction they traveled from their
previous game's host city, and how many timezone-hours that shift was.
"""

from datetime import datetime
from math import atan2, cos, degrees, radians, sin
from zoneinfo import ZoneInfo

import pandas as pd

from . import settings, io_utils

EARTH_RADIUS_MILES = 3958.8
_COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_LOCAL_GAME_HOUR = 19  # typical NBA tip-off time, used only to resolve DST for a given date


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    lat1r, lon1r, lat2r, lon2r = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * atan2(a**0.5, (1 - a) ** 0.5)


def initial_bearing_degrees(lat1, lon1, lat2, lon2) -> float:
    lat1r, lat2r = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    x = sin(dlon) * cos(lat2r)
    y = cos(lat1r) * sin(lat2r) - sin(lat1r) * cos(lat2r) * cos(dlon)
    return (degrees(atan2(x, y)) + 360) % 360


def compass_label(bearing_degrees: float) -> str:
    index = round(bearing_degrees / 45) % 8
    return _COMPASS_POINTS[index]


def utc_offset_hours(date, timezone_name: str) -> float:
    local_dt = datetime(date.year, date.month, date.day, _LOCAL_GAME_HOUR, tzinfo=ZoneInfo(timezone_name))
    return local_dt.utcoffset().total_seconds() / 3600


def _host_abbreviation(row) -> str:
    tokens = row["MATCHUP"].split()
    return tokens[0] if row["IS_HOME"] else tokens[-1]


def import_travel_timezone(season: str):
    game_logs = io_utils.load_existing(season, "game_logs")
    if game_logs.empty:
        raise RuntimeError(f"No game_logs.csv found for {season}; run game_logs import first.")

    locations = pd.read_csv(settings.TEAM_LOCATIONS_PATH).set_index("abbreviation")

    games = game_logs.copy()
    games["GAME_DATE"] = pd.to_datetime(games["GAME_DATE"])
    games["IS_HOME"] = games["IS_HOME"].astype(bool)
    games["HOST_ABBREV"] = games.apply(_host_abbreviation, axis=1)
    games = games.merge(
        locations[["city", "latitude", "longitude", "timezone"]],
        left_on="HOST_ABBREV",
        right_index=True,
        how="left",
    )

    rows = []
    for team_id, team_games in games.sort_values("GAME_DATE").groupby("TEAM_ID"):
        team_abbrev = team_games["TEAM_ABBREVIATION"].iloc[0]
        home = locations.loc[team_abbrev]
        prev_city, prev_lat, prev_lon, prev_tz = home["city"], home["latitude"], home["longitude"], home["timezone"]

        for _, game in team_games.iterrows():
            distance = haversine_miles(prev_lat, prev_lon, game["latitude"], game["longitude"])
            direction = compass_label(initial_bearing_degrees(prev_lat, prev_lon, game["latitude"], game["longitude"])) if distance > 0 else None
            tz_shift = utc_offset_hours(game["GAME_DATE"], game["timezone"]) - utc_offset_hours(game["GAME_DATE"], prev_tz)

            rows.append(
                {
                    "GAME_ID": game["GAME_ID"],
                    "TEAM_ID": team_id,
                    "TEAM_ABBREVIATION": team_abbrev,
                    "GAME_DATE": game["GAME_DATE"].date().isoformat(),
                    "PREV_CITY": prev_city,
                    "CURRENT_CITY": game["city"],
                    "DISTANCE_MILES": round(distance, 1),
                    "TRAVEL_DIRECTION": direction,
                    "TIMEZONE_SHIFT_HOURS": tz_shift,
                }
            )
            prev_city, prev_lat, prev_lon, prev_tz = game["city"], game["latitude"], game["longitude"], game["timezone"]

    out_df = pd.DataFrame(rows)
    path = io_utils.dataset_path(season, "travel_timezone")
    out_df.to_csv(path, index=False)
    print(f"[{season}] wrote {len(out_df)} travel/timezone rows to {path}")


def import_all(seasons=None):
    for season in seasons or settings.SEASONS:
        import_travel_timezone(season)


if __name__ == "__main__":
    import_all()

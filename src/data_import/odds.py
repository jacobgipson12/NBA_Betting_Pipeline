"""Fetches closing point-spread data and matches it to our own GAME_IDs.

Not the NBA stats API - source is sportsdataverse's community-maintained
hoopR-nba-data GitHub repo (https://github.com/sportsdataverse/hoopR-nba-data),
which republishes The Odds API's consensus closing lines. Two of its files are
combined:
  - nba/schedules/nba_schedule_master.parquet: ESPN's own game_id, date, and
    home/away team abbreviations - used only to translate ESPN's numeric
    game_id into a game we can match against our own game_logs.csv.
  - nba/betting_lines/closing_lines_odds_api.parquet: home_point, the closing
    spread already expressed from the home team's perspective (negative =
    home favored, positive = home underdog) - exactly the sign convention
    the training table wants, so it's carried through unchanged.

ESPN's team abbreviations differ from NBA.com's for six teams (GS/NO/NY/SA/
UTAH/WSH vs GSW/NOP/NYK/SAS/UTA/WAS); ESPN_TO_NBA_ABBREV reconciles that
before matching on (date, home team, away team) against game_logs.csv. A
small number of games (so far: one, 2022-11-16 DEN/NYK) have no closing line
in the source data at all; those are dropped and reported, not silently
left null.
"""

import io

import pandas as pd
import requests

from . import io_utils, settings

_BASE_URL = "https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/main/nba"
_SCHEDULE_URL = f"{_BASE_URL}/schedules/nba_schedule_master.parquet"
_CLOSING_LINES_URL = f"{_BASE_URL}/betting_lines/closing_lines_odds_api.parquet"

_REGULAR_SEASON_TYPE = 2  # ESPN's season_type code; 3 = playoffs, 5 = play-in

# The largest real pregame NBA spread on record is around -24 (a team missing
# most of its rotation against a contender). The upstream source has one row
# (game 401810853, 2026-03-17 SAC/SAS) where the "closing" snapshot was taken
# ~49 minutes after tipoff - by then the game was already a blowout, so the
# line reflects the live score, not a pregame market. Filtering on magnitude
# catches that row without discarding the ~1% of rows whose snapshot lands a
# few minutes past commence_time but still carries a plausible pregame line.
_MAX_PLAUSIBLE_SPREAD = 25

ESPN_TO_NBA_ABBREV = {
    "GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS",
}


def _season_end_year(season: str) -> int:
    """"2022-23" -> 2023, matching ESPN's schedule "season" (end-year) label."""
    return int(season.split("-")[0]) + 1


def _download_parquet(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=settings.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return pd.read_parquet(io.BytesIO(response.content))


def fetch_espn_closing_spreads() -> pd.DataFrame:
    """One combined download covering every season - sliced per season by the caller."""
    schedule = _download_parquet(_SCHEDULE_URL)
    lines = _download_parquet(_CLOSING_LINES_URL)

    schedule = schedule[schedule["season_type"] == _REGULAR_SEASON_TYPE].copy()
    schedule["home_abbreviation"] = schedule["home_abbreviation"].replace(ESPN_TO_NBA_ABBREV)
    schedule["away_abbreviation"] = schedule["away_abbreviation"].replace(ESPN_TO_NBA_ABBREV)
    schedule["game_date"] = pd.to_datetime(schedule["game_date"])

    implausible = lines["home_point"].abs() > _MAX_PLAUSIBLE_SPREAD
    if implausible.any():
        print(f"dropping {implausible.sum()} closing line(s) with |spread| > {_MAX_PLAUSIBLE_SPREAD} "
              f"(likely a post-tipoff snapshot, not a true closing line): "
              f"{lines.loc[implausible, 'game_id'].tolist()}")
        lines = lines[~implausible]

    merged = schedule.merge(lines[["game_id", "home_point"]], on="game_id", how="inner")
    return merged.rename(columns={
        "season": "SEASON_END_YEAR",
        "game_date": "GAME_DATE",
        "home_abbreviation": "HOME_TEAM_ABBREVIATION",
        "away_abbreviation": "AWAY_TEAM_ABBREVIATION",
        "home_point": "HOME_CLOSING_SPREAD",
    })[["SEASON_END_YEAR", "GAME_DATE", "HOME_TEAM_ABBREVIATION", "AWAY_TEAM_ABBREVIATION", "HOME_CLOSING_SPREAD"]]


def import_closing_spreads(season: str, espn_spreads: pd.DataFrame = None):
    game_logs = io_utils.load_existing(season, "game_logs")
    if game_logs.empty:
        raise RuntimeError(f"No game_logs.csv found for {season}; run game_logs import first.")

    espn_spreads = espn_spreads if espn_spreads is not None else fetch_espn_closing_spreads()

    game_logs = game_logs.copy()
    game_logs["GAME_DATE"] = pd.to_datetime(game_logs["GAME_DATE"])
    game_logs["IS_HOME"] = game_logs["IS_HOME"].astype(bool)

    home = game_logs[game_logs["IS_HOME"]][["GAME_ID", "GAME_DATE", "TEAM_ABBREVIATION"]].rename(
        columns={"TEAM_ABBREVIATION": "HOME_TEAM_ABBREVIATION"}
    )
    away = game_logs[~game_logs["IS_HOME"]][["GAME_ID", "TEAM_ABBREVIATION"]].rename(
        columns={"TEAM_ABBREVIATION": "AWAY_TEAM_ABBREVIATION"}
    )
    games = home.merge(away, on="GAME_ID", how="inner")

    season_spreads = espn_spreads[espn_spreads["SEASON_END_YEAR"] == _season_end_year(season)]
    matched = games.merge(
        season_spreads[["GAME_DATE", "HOME_TEAM_ABBREVIATION", "AWAY_TEAM_ABBREVIATION", "HOME_CLOSING_SPREAD"]],
        on=["GAME_DATE", "HOME_TEAM_ABBREVIATION", "AWAY_TEAM_ABBREVIATION"],
        how="left",
        validate="one_to_one",
    )

    missing = matched["HOME_CLOSING_SPREAD"].isna().sum()
    if missing:
        print(f"[{season}] no closing spread found for {missing}/{len(matched)} game(s) - dropped")
        matched = matched.dropna(subset=["HOME_CLOSING_SPREAD"])

    out_df = matched[["GAME_ID", "HOME_CLOSING_SPREAD"]]
    path = io_utils.dataset_path(season, "closing_spreads")
    out_df.to_csv(path, index=False)
    print(f"[{season}] wrote {len(out_df)} closing-spread rows to {path}")


def import_all(seasons=None):
    seasons = seasons or settings.SEASONS
    espn_spreads = fetch_espn_closing_spreads()
    for season in seasons:
        import_closing_spreads(season, espn_spreads)


if __name__ == "__main__":
    import_all()

"""Team advanced stats (per date, bulk) and player box scores (per game).

Team advanced stats use LeagueDashTeamStats filtered to a single date - one
call covers every team that played that day, cutting ~1,230 games/season down
to ~160-165 API calls. This is safe because a team's identity never changes,
so attributing a day's stats to TEAM_ID is always correct no matter when the
data is pulled.

Player stats CANNOT use the equivalent bulk-by-date endpoint
(LeagueDashPlayerStats), even though it exists and returns the right shape.
That endpoint attributes a player's stats to whatever team he is CURRENTLY
on as of whenever the query runs - not the team he played for on the
historical date being queried. Any player who has since changed teams (trade,
free agency, waiver claim) has his pre-move games silently misattributed to
his new team. Verified directly: comparing summed player PTS against the
authoritative team PTS in game_logs.csv, 40-56% of team-games per season
didn't match when player stats were pulled via the per-date approach - e.g. a
Nov 2023 Charlotte game's player rows included two players who were on OKC at
the time and evidently joined Charlotte at some later point.
BoxScoreTraditionalV3 is keyed by GAME_ID and reflects the immutable
historical box score, so player stats are pulled that way instead - one call
per game, no shortcut available.
"""

import pandas as pd
from tqdm import tqdm

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguedashteamstats

from . import settings, io_utils
from .http import fetch_with_retry

_PLAYER_ID_RENAME = {"gameId": "GAME_ID", "teamId": "TEAM_ID", "personId": "PLAYER_ID"}


def _load_game_logs(season: str) -> pd.DataFrame:
    game_logs = io_utils.load_existing(season, "game_logs")
    if game_logs.empty:
        raise RuntimeError(f"No game_logs.csv found for {season}; run game_logs import first.")
    game_logs = game_logs.copy()
    game_logs["TEAM_ID"] = game_logs["TEAM_ID"].astype("int64")
    game_logs["GAME_DATE"] = pd.to_datetime(game_logs["GAME_DATE"]).dt.date
    return game_logs


def _attach_game_id(df: pd.DataFrame, day_games: pd.DataFrame, game_date) -> pd.DataFrame:
    df = df.copy()
    df = df.drop(columns=[c for c in df.columns if c.endswith("_RANK")])  # meaningless over a 1-day sample
    df["TEAM_ID"] = df["TEAM_ID"].astype("int64")
    merged = df.merge(day_games, on="TEAM_ID", how="left")
    merged.insert(0, "GAME_DATE", game_date.isoformat())
    merged.insert(0, "GAME_ID", merged.pop("GAME_ID"))
    return merged


def import_team_advanced_stats(season: str):
    game_logs = _load_game_logs(season)
    all_dates = sorted(game_logs["GAME_DATE"].unique())

    existing = io_utils.load_existing(season, "team_advanced_stats")
    done_dates = set(existing["GAME_DATE"]) if not existing.empty and "GAME_DATE" in existing.columns else set()

    pending = [d for d in all_dates if d.isoformat() not in done_dates]
    if not pending:
        print(f"[{season}] team_advanced_stats already up to date ({len(all_dates)} game dates).")
        return

    for game_date in tqdm(pending, desc=f"{season} team advanced stats"):
        day_games = game_logs.loc[game_logs["GAME_DATE"] == game_date, ["TEAM_ID", "GAME_ID"]]
        api_date = game_date.strftime("%m/%d/%Y")
        adv = fetch_with_retry(
            leaguedashteamstats.LeagueDashTeamStats,
            season=season,
            season_type_all_star=settings.SEASON_TYPE,
            measure_type_detailed_defense="Advanced",
            date_from_nullable=api_date,
            date_to_nullable=api_date,
        )
        team_advanced = _attach_game_id(adv.get_data_frames()[0], day_games, game_date)
        io_utils.append_rows(season, "team_advanced_stats", team_advanced)


def import_player_stats(season: str):
    game_logs = io_utils.load_existing(season, "game_logs")
    if game_logs.empty:
        raise RuntimeError(f"No game_logs.csv found for {season}; run game_logs import first.")
    game_ids = sorted(game_logs["GAME_ID"].astype(str).str.zfill(10).unique())

    done = io_utils.already_fetched_game_ids(season, marker_dataset="player_stats")
    pending = [gid for gid in game_ids if gid not in done]
    if not pending:
        print(f"[{season}] player_stats already up to date ({len(game_ids)} games).")
        return

    for game_id in tqdm(pending, desc=f"{season} player box scores"):
        trad = fetch_with_retry(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)
        player_stats = trad.get_data_frames()[0].rename(columns=_PLAYER_ID_RENAME)
        io_utils.append_rows(season, "player_stats", player_stats)


def import_per_game_details(season: str):
    import_team_advanced_stats(season)
    import_player_stats(season)


def import_all(seasons=None):
    for season in seasons or settings.SEASONS:
        import_per_game_details(season)


if __name__ == "__main__":
    import_all()

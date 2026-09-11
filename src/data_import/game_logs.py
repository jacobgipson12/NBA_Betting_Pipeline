"""Team game logs (one row per team per game: score, date, home/away, result).

Home/away is normally read off the MATCHUP text ("TEAM vs. OPP" = home,
"TEAM @ OPP" = away), but a small number of games - so far seen for games
played at a neutral/international site (e.g. NBA Cup semifinals, NBA Paris
Games) - have MATCHUP set to "@" for *both* teams, which would otherwise
leave the game with no home team at all. For just those ambiguous games,
the official home team is looked up via BoxScoreSummaryV2 (one call per
ambiguous game, not per game in the season) and written into a persisted
IS_HOME column so downstream code never has to re-derive it from MATCHUP.
"""

import warnings

from nba_api.stats.endpoints import boxscoresummaryv2, leaguegamelog

from . import settings, io_utils
from .http import fetch_with_retry


def _resolve_home_team(df):
    df = df.copy()
    df["IS_HOME"] = df["MATCHUP"].str.contains(" vs. ")

    home_counts = df.groupby("GAME_ID")["IS_HOME"].transform("sum")
    ambiguous_game_ids = df.loc[home_counts != 1, "GAME_ID"].unique()

    for game_id in ambiguous_game_ids:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            summary = fetch_with_retry(boxscoresummaryv2.BoxScoreSummaryV2, game_id=game_id)
        home_team_id = summary.get_data_frames()[0]["HOME_TEAM_ID"].iloc[0]
        mask = df["GAME_ID"] == game_id
        df.loc[mask, "IS_HOME"] = df.loc[mask, "TEAM_ID"] == home_team_id
        print(f"  resolved ambiguous home team for game {game_id} via BoxScoreSummaryV2")

    return df


def import_game_logs(season: str, force: bool = False):
    path = io_utils.dataset_path(season, "game_logs")
    if path.exists() and not force:
        print(f"[{season}] game_logs.csv already exists, skipping (pass force=True to refetch).")
        return

    log = fetch_with_retry(
        leaguegamelog.LeagueGameLog,
        season=season,
        season_type_all_star=settings.SEASON_TYPE,
        player_or_team_abbreviation="T",
        league_id=settings.LEAGUE_ID,
    )
    df = log.get_data_frames()[0]
    df = _resolve_home_team(df)
    df.to_csv(path, index=False)
    print(f"[{season}] wrote {len(df)} team-game rows to {path}")


def import_all(seasons=None, force: bool = False):
    for season in seasons or settings.SEASONS:
        import_game_logs(season, force=force)


if __name__ == "__main__":
    import_all()

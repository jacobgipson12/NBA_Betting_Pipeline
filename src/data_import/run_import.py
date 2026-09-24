"""CLI entrypoint for the raw-data import pipeline.

Usage (from the repo root):
    python3 -m src.data_import.run_import
    python3 -m src.data_import.run_import --seasons 2022-23 2023-24
    python3 -m src.data_import.run_import --datasets game_logs per_game_details
    python3 -m src.data_import.run_import --fresh   # ignore existing game_logs.csv and refetch

Safe to interrupt and re-run: game_logs is skipped if already present (unless
--fresh), and per_game_details resumes from the last completed GAME_ID.
"""

import argparse

from . import settings, game_logs, per_game_details, travel_timezone, odds


def run(seasons, datasets, fresh: bool):
    espn_spreads = None
    for season in seasons:
        print(f"=== {season} ===")
        if "game_logs" in datasets:
            game_logs.import_game_logs(season, force=fresh)
        if "per_game_details" in datasets:
            per_game_details.import_per_game_details(season)
        if "travel_timezone" in datasets:
            travel_timezone.import_travel_timezone(season)
        if "odds" in datasets:
            if espn_spreads is None:
                espn_spreads = odds.fetch_espn_closing_spreads()
            odds.import_closing_spreads(season, espn_spreads)


def main():
    parser = argparse.ArgumentParser(description="Import raw NBA data for the betting pipeline.")
    parser.add_argument("--seasons", nargs="+", default=settings.SEASONS, help="Seasons to import, e.g. 2023-24")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=settings.DATASETS,
        choices=settings.DATASETS,
        help="Which datasets to import",
    )
    parser.add_argument("--fresh", action="store_true", help="Refetch game_logs.csv even if it already exists")
    args = parser.parse_args()

    run(args.seasons, args.datasets, args.fresh)


if __name__ == "__main__":
    main()

"""Shared configuration for the NBA raw-data import pipeline."""

from pathlib import Path

# Repo root is three levels up from this file: src/data_import/settings.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
TEAM_LOCATIONS_PATH = REPO_ROOT / "config" / "team_locations.csv"

# Last 4 completed NBA seasons: most recent is the test set, the 3 before it are train.
TEST_SEASON = "2025-26"
TRAIN_SEASONS = ["2022-23", "2023-24", "2024-25"]
SEASONS = TRAIN_SEASONS + [TEST_SEASON]

SEASON_TYPE = "Regular Season"
LEAGUE_ID = "00"

# Rate limiting / retry behavior for calls to the NBA stats API.
REQUEST_DELAY_SECONDS = 0.6
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 5
RETRY_BACKOFF_BASE_SECONDS = 2.0

DATASETS = ["game_logs", "per_game_details", "travel_timezone", "odds"]

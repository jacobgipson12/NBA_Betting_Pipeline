"""Output path helpers and incremental CSV I/O for resumable imports."""

import pandas as pd

from . import settings

# GAME_ID values are zero-padded numeric strings (e.g. "0022300061"); without
# forcing str dtype, pandas silently parses the column as int64 on read and
# strips the leading zero, which then breaks every downstream endpoint call.
_STR_COLUMNS = {"GAME_ID", "TEAM_ID"}


def season_dir(season: str):
    path = settings.RAW_DATA_DIR / season
    path.mkdir(parents=True, exist_ok=True)
    return path


def dataset_path(season: str, dataset_name: str):
    return season_dir(season) / f"{dataset_name}.csv"


def append_rows(season: str, dataset_name: str, df: pd.DataFrame):
    """Append rows to a season's dataset CSV, writing a header only if new."""
    if df.empty:
        return
    path = dataset_path(season, dataset_name)
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def load_existing(season: str, dataset_name: str) -> pd.DataFrame:
    path = dataset_path(season, dataset_name)
    if not path.exists():
        return pd.DataFrame()
    header = pd.read_csv(path, nrows=0).columns
    dtype = {col: str for col in header if col in _STR_COLUMNS}
    return pd.read_csv(path, dtype=dtype)


def already_fetched_game_ids(season: str, marker_dataset: str) -> set:
    """GAME_IDs already present in the marker dataset for this season, used to skip re-fetching.

    The marker dataset should be the *last* one written per game_id in a given
    import step, so a game only counts as done once every write for it succeeded.
    """
    existing = load_existing(season, marker_dataset)
    if existing.empty or "GAME_ID" not in existing.columns:
        return set()
    return set(existing["GAME_ID"].astype(str))

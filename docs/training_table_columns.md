# `training_table_avg<N>.csv` column reference

Produced by [`data/build_training_table.ipynb`](../data/build_training_table.ipynb). One row per game.
`N` is the trailing-window size (`N_GAMES` in the notebook) — for
`data/processed/training_table_avg10.csv`, `N = 10`.

Every feature column is a team's trailing **N-game rolling average**,
computed as of and **excluding** the game in that row (no leakage from the
game being predicted). Each base stat below expands into three columns:

| Pattern | Meaning |
|---|---|
| `HOME_<STAT>_AVG<N>` | Home team's trailing N-game average of `<STAT>` |
| `AWAY_<STAT>_AVG<N>` | Away team's trailing N-game average of `<STAT>` |
| `DIFF_<STAT>_AVG<N>` | `HOME_<STAT>_AVG<N> - AWAY_<STAT>_AVG<N>` (home-team edge) |

e.g. `PTS` becomes `HOME_PTS_AVG10`, `AWAY_PTS_AVG10`, `DIFF_PTS_AVG10`.

## Identifier columns

| Column | Definition |
|---|---|
| `GAME_ID` | NBA.com game identifier |
| `SEASON` | Season string, e.g. `2023-24` |
| `GAME_DATE` | Date the game was played |
| `HOME_TEAM_ID` | NBA team ID of the home team |
| `HOME_TEAM_ABBREVIATION` | 3-letter abbreviation of the home team |
| `AWAY_TEAM_ID` | NBA team ID of the away team |
| `AWAY_TEAM_ABBREVIATION` | 3-letter abbreviation of the away team |

## Base stats

### Box-score counts (rolled as-is)

| Stat | Definition |
|---|---|
| `FGM` | Field goals made per game |
| `FGA` | Field goals attempted per game |
| `FG3M` | 3-point field goals made per game |
| `FG3A` | 3-point field goals attempted per game |
| `FTM` | Free throws made per game |
| `FTA` | Free throws attempted per game |
| `OREB` | Offensive rebounds per game |
| `DREB` | Defensive rebounds per game |
| `REB` | Total rebounds per game |
| `AST` | Assists per game |
| `STL` | Steals per game |
| `BLK` | Blocks per game |
| `TOV` | Turnovers per game |
| `PF` | Personal fouls per game |
| `PTS` | Points scored per game |
| `PLUS_MINUS` | Point differential (plus/minus) per game |
| `WIN` | Win rate (fraction of games won, 0-1) |
| `POSS` | Possessions per game (also an input to `OFF_RATING`/`DEF_RATING`/`TM_TOV_PCT` below) |

### NBA-reported advanced stats (averaged directly)

Not reconstructable from the box score with acceptable accuracy (see the
notebook's "Derive rate stats" section), so the per-game values are averaged
directly rather than re-derived from rolled counts.

| Stat | Definition |
|---|---|
| `OREB_PCT` | Offensive rebound percentage |
| `DREB_PCT` | Defensive rebound percentage |
| `PACE` | Possessions per 48 minutes |
| `PIE` | Player Impact Estimate, team-level |

### Derived rate/efficiency stats

Computed from the already-rolled counts above (e.g. `AVG(FGM) / AVG(FGA)`),
not by averaging each game's own rate.

| Stat | Definition |
|---|---|
| `FG_PCT` | Field goal percentage = `AVG(FGM) / AVG(FGA)` |
| `FG3_PCT` | 3-point percentage = `AVG(FG3M) / AVG(FG3A)` |
| `FT_PCT` | Free throw percentage = `AVG(FTM) / AVG(FTA)` |
| `EFG_PCT` | Effective field goal percentage = `(AVG(FGM) + 0.5*AVG(FG3M)) / AVG(FGA)` |
| `TS_PCT` | True shooting percentage = `AVG(PTS) / (2 * (AVG(FGA) + 0.44*AVG(FTA)))` |
| `AST_PCT` | Assist percentage = `AVG(AST) / AVG(FGM)` |
| `AST_TO` | Assist-to-turnover ratio = `AVG(AST) / AVG(TOV)` |
| `AST_RATIO` | Assists per 100 team plays = `100*AVG(AST) / (AVG(FGA) + 0.44*AVG(FTA) + AVG(AST) + AVG(TOV))` |
| `TM_TOV_PCT` | Turnover percentage = `AVG(TOV) / AVG(POSS)` |
| `OFF_RATING` | Points scored per 100 possessions = `100*AVG(PTS) / AVG(POSS)` |
| `REB_PCT` | Total rebound percentage = `AVG(REB) / (AVG(REB) + AVG(OPP_REB))` |
| `DEF_RATING` | Points allowed per 100 possessions = `100*AVG(OPP_PTS) / AVG(POSS)` |
| `NET_RATING` | Net rating = `OFF_RATING - DEF_RATING` |

## Rest days

Not part of the `HOME_<STAT>_AVG<N>` pattern above — a raw, pre-game schedule
feature (known before tip-off), not a rolling average.

| Column | Definition |
|---|---|
| `HOME_REST` | Full days off between the home team's previous game and this one (`0` = back-to-back, `1` = one day off, etc.) |
| `AWAY_REST` | Full days off between the away team's previous game and this one |
| `REST_DIFF` | `HOME_REST - AWAY_REST`. Positive means the home team is better rested. |

## Betting market

Not part of the `HOME_<STAT>_AVG<N>` pattern above — a pre-game market signal
(known before tip-off, from closing sportsbook lines), not a rolling average
of box-score stats. Sourced separately from the NBA stats API by
`src/data_import/odds.py`.

| Column | Definition |
|---|---|
| `HOME_SPREAD` | Closing point spread, from the home team's perspective. Negative means the home team was favored (e.g. `-2` = home favored by 2); positive means the home team was the underdog. |

## Outcome columns

Actual results of the game itself (not averages) — these are the prediction
targets, not features.

| Column | Definition |
|---|---|
| `HOME_PTS` | Points the home team actually scored in this game |
| `AWAY_PTS` | Points the away team actually scored in this game |
| `HOME_WIN` | 1 if the home team won this game, else 0 |
| `HOME_DIFF` | Margin of victory/loss for the home team = `HOME_PTS - AWAY_PTS`. Positive means the home team won, negative means they lost. |

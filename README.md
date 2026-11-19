# QuantDesk

**A native Windows desktop workbench for daily-bar quantitative research.**

QuantDesk imports or downloads real historical daily bars, keeps strategy definitions as inspectable data, runs an event-driven backtest over those bars, reconciles the resulting account ledger bar by bar, sweeps parameters across a grid, and stores every run so results can be compared, restored and exported later. The shipping application talks to its own Python service layer and to a single SQLite library database: it starts no HTTP server, opens no browser tab and binds no local port.

The window is an ordinary desktop window rather than a fullscreen surface. It opens no wider than 1280 x 800 and adapts to the available screen area; the minimum supported size is 1060 x 680. All page and control labels in the current build are Chinese; the English page names used in this document are translations of those labels.

## Status and scope

This is a working research prototype for one instrument at a time on daily bars. The feature list below is implemented and covered by tests. The limits listed under [Data and calculation conventions](#data-and-calculation-conventions) are deliberate design boundaries of this version, not unfinished work: there is no order routing, no broker or exchange connection, no live quote subscription, and no shared capital across instruments.

## Features

- **Market data.** Fetch daily bars from Yahoo or Stooq, import your own CSV, or use the built-in historical sample. Every dataset keeps its source URL or file path, provider, retrieval time, date coverage, content hash and cleaning report, viewable in the source and cleaning panel. Query by date range, chart the bars, and export the series back to CSV.
- **Strategy management.** Eight declarative templates: dual SMA, dual EMA, RSI mean reversion, Bollinger band reversion, MACD, channel breakout, buy and hold, and a custom rule template. Common parameters are edited in a form; custom rules are edited as JSON. Strategies can be saved, loaded, saved as a copy and updated.
- **Event backtest.** Choose a strategy, adjust periods, set initial capital, commission, slippage and position size, and expand the risk controls to configure take-profit, stop-loss, trading unit and capacity. Charts show price and fills, volume or an indicator, equity versus the buy-and-hold benchmark, and drawdown. Double-clicking a fill jumps to that date.
- **Ledger reconciliation.** The per-bar ledger pairs cash plus position value against equity, and realized plus unrealized profit and loss against total profit and loss. The acceptance run asserts both identities on every bar of the curve, and imported reports are validated the same way.
- **Parameter research.** Tick the parameters to sweep, enter comma-separated candidate values, and run the grid. Runs are aligned to a common trading start, and up to 20 new curves are selected and overlaid automatically when the sweep finishes. Saved strategies can be compared in a batch; data hash and date range must match, otherwise the reason is shown and the overlay stops.
- **Reports and task log.** Export a run as `report.json` plus five CSVs. Download, backtest and sweep jobs run in the background and can be cancelled; a network cancellation completes when the current request returns or times out.

## Tech stack

- **PySide6** (Qt for Python) for the native interface, **pyqtgraph** for price, volume and equity charts, **numpy** for indicator math.
- **SQLite** single-file library in WAL mode for datasets, bars, strategy documents, configurations, experiments and logs. The ledger and all metrics are computed in Python, not in SQL.
- **PyInstaller** for the Windows build. Python 3.11 to 3.13 when running from source; verified on Windows 11 with Python 3.13.9.
- No web server, no browser and no local port anywhere in the desktop path.

Pinned dependency versions, from `requirements.txt` and `requirements-dev.txt`:

```text
PySide6==6.11.2
pyqtgraph==0.14.0
numpy==2.5.3
pyinstaller==6.22.3      (development only)
backtrader==1.9.78.123   (development only, independent oracle test)
```

## Install and run

### Packaged application

1. Unzip the application archive completely.
2. Run `dist/QuantDesk/QuantDesk.exe`, or run `start.ps1` from the repository root.
3. Keep the `_internal` folder next to the executable. The whole `dist/QuantDesk` directory is the runtime boundary, so send the folder rather than the executable alone, and do not remove DLLs or plugins from `_internal`.

The packaged build needs no Python installation. On first launch it loads and selects the built-in public AAPL sample and draws its candlestick chart right away.

### From source

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe download_data.py
.venv/Scripts/python.exe desktop.py
```

`download_data.py` downloads the public sample into `data/` and writes `data/metadata.json` with the source URL, retrieval time, SHA-256, row count and date range. That step needs network access once; everything afterwards runs offline. `download_data.py` and `desktop.py` are the only entry points you need.

`start.ps1` launches `dist/QuantDesk/QuantDesk.exe` when it exists and otherwise falls back to `.venv/Scripts/python.exe desktop.py`. It changes nothing else and passes no arguments.

### Build the executable

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` downloads the real historical sample when `data/aapl.csv` is missing, then runs PyInstaller with `packaging/QuantDesk.spec`. The spec bundles `data/aapl.csv` into the executable and excludes `pyqtgraph.opengl`. Output is `dist/QuantDesk/QuantDesk.exe`; distribute the entire `QuantDesk` folder.

### Build release archives

```powershell
.venv/Scripts/python.exe packaging/make_release.py
```

This writes `releases/<timestamp>-<commit>/` containing `QuantDesk-Windows-x64.zip`, `QuantDesk-Source.zip`, `manifest.json` and `SHA256SUMS.txt`. Every run creates a new directory and never overwrites an older archive. The script refuses to package a runtime folder that contains a database, SQLite file, log or `.env`, and it reads no personal database. The seven extended sample CSVs are copied from `data/demo` when that folder exists; without it the application archive still works offline with the built-in AAPL sample.

## Data locations

| What | Location |
|---|---|
| Data directory (default) | `%LOCALAPPDATA%/QuantDesk` |
| Library database | `%LOCALAPPDATA%/QuantDesk/library.sqlite3` |
| Interface preferences | `%LOCALAPPDATA%/QuantDesk/ui.ini` |
| Data directory override | environment variable `QUANTDESK_HOME` |
| Fallback when `LOCALAPPDATA` is unset | `~/QuantDesk` |

Datasets, bars, strategies, configurations, experiments and the task log all live in `library.sqlite3`. The theme choice (light or dark) is stored in `ui.ini` in the same directory.

Setting `QUANTDESK_HOME` to another path makes the application read and write a completely separate library, which is how the acceptance run below keeps its temporary state away from your working data.

Moving, updating or replacing the application folder does not touch this directory, and distributing the application does not copy your library. To back it up, close the application first and then copy the whole data directory; the SQLite write-ahead log is closed on exit, so a plain folder copy is consistent.

## Built-in sample market data

The packaged build and a fresh source checkout both start from one public historical sample:

| Field | Value |
|---|---|
| Symbol | AAPL |
| Range | 2015-02-17 to 2017-02-16 |
| Daily bars | 506 |
| Source | `raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv` |
| Retrieved | 2026-10-02 |
| SHA-256 | `24c7604edfd5afe862ddb9f9535e2fd7351f43711bfc442bca52055e15e37bcd` |
| Currency | USD |
| Price basis | Raw OHLC; the adjusted column is not used, so dividends are excluded and the series is not a total return |

The sample is embedded into the executable at build time, so the first launch shows a chart with no network access. See [docs/market-data.md](docs/market-data.md) for how each source is fetched and validated.

A larger optional set is documented for local use: `data/demo/` holds AAPL, MSFT, NVDA, TSLA, SPY, QQQ and `000001.SS`, covering 2022-01-03 to 2025-12-31 with 1,003 daily bars each except `000001.SS` (969 bars, starting 2022-01-04), 6,987 bars in total. Each CSV has a matching `.source.json` recording the vendor response. `data/` is ignored by Git, so these files are not part of the repository; the release script copies them into the application archive when they are present. `000001.SS` is the SSE Composite index and is for index research only, not a tradable stock.

## Usage order

1. **Market data.** Fetch or import a CSV, then check the source, hash and cleaning report. Query a date range, chart the bars, export the series.
2. **Strategy management.** Pick one of the eight templates or edit the custom rule JSON. Save, load, save as a copy, or update.
3. **Backtest research.** Select the strategy and dataset, set the period, capital, commission, slippage and position size, optionally configure the risk controls, then run. Editing parameters after a run marks the displayed result as stale; loading a saved experiment restores the configuration that produced it.
4. **Experiments and comparison.** Sweep parameters or compare saved strategies, sort by clicking a column header, multi-select rows and load one by double-click. The colour chip before each name matches its curve.
5. **Export.** Write `report.json` plus the summary, trades, orders, round trips and equity CSV files. A report can be imported back into the experiment library.
6. **Task log.** Inspect failures and diagnostics. Downloads, backtests and sweeps run in the background and can be cancelled.

Custom rules are data, never executed Python. `entry` and `exit` each accept 1 to 10 AND conditions comparing an indicator or a number, including cross-above and cross-below. The available fields are `close`, `sma_fast`, `sma_slow`, `ema_fast`, `ema_slow`, `rsi`, `bb_upper`, `bb_lower`, `macd`, `macd_signal`, `atr`, `high_channel` and `low_channel`; the operators are `>`, `<`, `>=`, `<=`, `cross_above` and `cross_below`. See the `custom` template in `quantdesk/strategies.py`.

## Data and calculation conventions

**CSV contract.** Columns `date,open,high,low,close,volume`. Common Chinese column names and `AAPL.Open` style prefixes are recognised. Dates are `YYYY-MM-DD`. Rows are validated for OHLC ordering, finite positive prices and non-negative volume, with at most 250,000 rows per import and at least 3 bars after cleaning. Duplicate-date policy and invalid-row policy must be chosen explicitly (reject, keep first or keep last; drop or fail). Missing trading days are never invented and prices are never forward filled; gaps longer than a week are reported.

**Execution model.** Signals are evaluated on the close and executed at the next bar's open, so a decision cannot be applied retroactively to the same day's open. Warm-up uses bars before the start date and the run is refused when there are not enough. Long only, single instrument, no leverage, integer trading units. Commission is proportional to turnover; slippage is applied adversely on both sides. A zero-volume bar does not fill, and an order that exceeds configured capacity is rejected as a whole. The open position is marked at the final close and is not assumed to be liquidated.

**Risk controls.** Take-profit and stop-loss are simulated on daily bars: gaps execute at the open, two triggers on the same bar resolve in favour of the stop-loss, and protection is active from the buy day onward. A daily bar cannot reconstruct the intraday path, and protection fills are still subject to capacity.

**Metrics.** Equity equals cash plus shares times close. Profit and loss equals realized plus unrealized. Drawdown is measured from the running peak that includes the initial capital. Annualized return is the calendar-day CAGR. Sharpe uses the sample standard deviation of daily returns and the configured number of trading days per year. Win rate and profit-to-loss ratio use closed round trips. An undefined denominator is shown as a dash rather than as zero, and the exact definitions are written into the exported report.

**Not modelled.** Dividends, cash adjustments from corporate actions, taxes, minimum commission, price limits, T+1 settlement, exchange calendars, and capital shared across several instruments. Yahoo raw OHLC and imported CSV files must be checked for their adjustment basis, and the upstream provider's conventions govern volume units. This is not a complete A-share simulation and not a live broker.

## Tests and verification

Unit tests (38 test methods across the `tests/` package):

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Coverage includes CSV cleaning and duplicate policy, indicators, the eight strategy templates, custom rule validation, account conservation on every bar, the experiment library, desktop workflows and the legacy preview server. `tests/test_oracle.py` is an independent Backtrader comparison over the real sample and is skipped unless `backtrader` is installed.

Native acceptance run, which drives the real background jobs and writes screenshots plus JSON evidence:

```powershell
$env:QUANTDESK_HOME="$PWD/outputs/acceptance-home"
dist/QuantDesk/QuantDesk.exe --verify outputs/acceptance
```

`--verify <directory>` runs a backtest on the selected dataset, saves all eight strategy templates, compares them, sweeps `fast` in 5, 10, 15 against `slow` in 20, 30, 60 (9 runs), checks that every compared and swept run shares one trading start, reloads the saved experiment and compares the restored summary, asserts the ledger identities on every bar, exports the six files, and writes `desktop.png`, `comparison.png` and `acceptance.json` before exiting. Use a separate data directory as shown so acceptance state never mixes with your own library.

The Backtrader oracle checks fills and the per-bar cash, position and equity of the real sample. It aligns only the dual-SMA configuration with no slippage and proportional commission; it does not prove that every risk-control path is equivalent.

Two optional browser checks exist for the offline HTML demo: `tests/demo_browser_check.cjs <html>` (Node and Playwright with the local Chrome) and `tests/browser_check.py` (Playwright for Python). Both are development aids and are not part of the unit test run.

## Repository layout

| Path | Purpose |
|---|---|
| `desktop.py` | Production desktop entry point |
| `quantdesk/` | Application package: `ui.py`, `service.py`, `storage.py`, `data.py`, `backtest.py`, `strategies.py`, `indicators.py`, `charts.py`, `reports.py`, `theme.py`, `strategy_form.py`, `verify.py` |
| `tests/` | Unit tests, oracle test and optional browser checks |
| `docs/` | User documentation (see below) |
| `demo/` | Generator, template and README for the offline HTML demo |
| `packaging/` | PyInstaller spec and the release archive builder |
| `data/` | Local market data and metadata (ignored by Git) |
| `outputs/` | Local verification evidence: screenshots, reports, download snapshots (ignored by Git) |
| `dist/`, `build/`, `releases/` | Build output and archives (ignored by Git) |
| `download_data.py` | Downloads the public historical sample |
| `engine.py`, `server.py`, `web/` | Earlier browser prototype, kept for traceability only |
| `start.ps1` | Launches the packaged executable, falling back to the source entry point |
| `build.ps1` | Builds `dist/QuantDesk/QuantDesk.exe` with PyInstaller |
| `requirements.txt`, `requirements-dev.txt` | Pinned runtime and development dependencies |

## Documentation

- [docs/quickstart.md](docs/quickstart.md) - first complete backtest, step by step, and how to read the results.
- [docs/market-data.md](docs/market-data.md) - how each market data source is fetched, what has been imported, and the price basis.
- [docs/delivery.md](docs/delivery.md) - what goes into the application archive versus the source archive, and how to regenerate them.
- [demo/README.md](demo/README.md) - the single-file offline HTML walkthrough.

## Legacy web preview

`server.py` and `web/` are an earlier browser prototype of the same ideas. Running `python server.py` serves a preview on `127.0.0.1:8765`, and `tests/test_server.py` still covers its HTTP handler. The production desktop path never calls it: the desktop entry point is `desktop.py`, and the packaging and release scripts do not include the preview in the runtime folder.

## Disclaimer

QuantDesk is a research and teaching tool. Nothing it produces is investment advice, a recommendation, or a forecast. Historical data can be incomplete, revised, adjusted differently by each provider, or simply wrong, and a backtest that looks good in-sample routinely fails out of sample. Results depend on the data window, cost assumptions and parameter choices you supply. Verify any number before relying on it, and use the software at your own risk; it comes with no warranty of any kind. Market data remains subject to the terms of the provider it came from, and you are responsible for complying with them.

## License

This repository does not include a LICENSE file yet, so no license is currently granted for reuse or redistribution. Add an explicit license before publishing the project.

Third-party components keep their own licenses and are not covered by any project license: PySide6 (LGPLv3 or GPLv3, plus commercial options from Qt), pyqtgraph (MIT), numpy (BSD-3-Clause), PyInstaller (GPL-2.0-or-later with the bootloader exception) and Backtrader (GPL-3.0, development only). Check each project's current license text before you redistribute a build.

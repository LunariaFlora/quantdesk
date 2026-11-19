# Delivery and directory layout

## Two kinds of archive

The **application archive** is for people who just want to use the software: unzip it completely and run `QuantDesk/QuantDesk.exe`, with no Python involved. The whole `dist/QuantDesk` folder is the runtime boundary, so sending the executable alone is not enough, and DLLs or plugins inside `_internal` must not be removed.

The release script additionally puts the quickstart, the market data notes, the seven CSV files (when `data/demo` exists) and their source records into the application archive. Those CSVs are imported by hand on the receiving computer; the archive neither goes online nor carries the sender's experiment library. The built-in AAPL fixed sample stays inside the runtime directory.

The **source archive** is for a reviewer who wants to read the implementation. It contains the desktop entry point, the `quantdesk` package, the tests, the documentation, the pinned dependency list and the packaging configuration as tracked by Git, plus the `data/aapl.csv` sample and the demo CSVs that are required to run from source. The old `server.py` and `web/` directory are only a historical browser preview; the production entry point is `desktop.py`. They are kept for traceability and do not constitute a second project.

Neither archive contains `.venv`, `.git`, `build`, other `dist` folders, `outputs`, the local database, logs, `.env` files or credentials. There is no need to send the whole project directory. If someone only wants to see the result, send the application archive; if they also want to read the code, add the source archive.

## Generating the release archives

Build the executable with `build.ps1` first, then run:

```powershell
.venv/Scripts/python.exe packaging/make_release.py
```

The script writes the archives and a SHA-256 checksum list into `releases/<timestamp>-<commit>/`. Each run creates a new directory and never overwrites an older archive. It does not download samples and does not read a personal database. The seven extended samples come from `data/demo`; without that directory it still produces an application archive that works offline with the fixed AAPL sample.

The source archive reflects the working-tree file contents at the moment the release script runs, and the version string is the Git HEAD commit. Test and commit source changes before publishing. The SHA-256 values let the recipient confirm that a ZIP survived transfer intact.

## Development directory responsibilities

| Directory or file | Purpose | Given to end users |
|---|---|---|
| `dist/QuantDesk` | Executable and all runtime libraries | Yes, keep it complete |
| `releases` | Generated application ZIP, source ZIP and checksum list | Send only the needed ZIP |
| `quantdesk`, `desktop.py` | Production desktop source | Source review only |
| `tests`, `docs`, `packaging` | Tests, documentation, build and release scripts | Source review only |
| `data/aapl.csv`, `data/demo` | Fixed sample and extended CSVs | Picked by the release script from named directories only |
| `.venv`, `build` | Local development environment and build intermediates | Never sent |
| `outputs` | Local evidence: verification screenshots, reports, download snapshots | Select individual files if needed, never the whole directory |
| `%LOCALAPPDATA%/QuantDesk` | Personal data, strategies, experiments, settings | Never travels with the application |

## Acceptance and applicable scope

The end-to-end demo loop is: real historical bars, then a strategy, then a backtest, then ledger reconciliation, then parameter comparison, then report export. Automated tests cover data validation, indicators, strategies, account conservation, the experiment library and the desktop workflows. The Backtrader comparison only verifies dual-SMA fills and the per-bar account under aligned settings; it does not prove that every strategy or every real trading rule is equivalent.

Before publishing, unzip the archive for real and run the executable's `--verify` acceptance with a separate `QUANTDESK_HOME`, checking the eight-strategy comparison, the nine parameter runs, experiment reload and the six exported files. A recipient should still launch it once on their own Windows computer: acceptance on this machine does not prove coverage of every Windows version.

This version is suitable for delivery as a teaching and research prototype. Live order placement, capital shared across several instruments, short selling, leverage, full T+1, price limit and trading calendar rules, and dividend or corporate-action handling are not implemented. Public data services can stop working, and a daily stop-loss cannot reconstruct the intraday path. These limits should not be omitted when the project is presented.

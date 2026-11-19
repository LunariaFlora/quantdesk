# How market data is obtained

QuantDesk is a historical daily-bar research tool. On startup it reads the local library and does not go online or subscribe to live quotes by itself; a download happens only after you click fetch.

| Entry | What actually happens | Coverage |
|---|---|---|
| Yahoo daily | HTTPS request to `query1.finance.yahoo.com/v8/finance/chart/{symbol}` with the `period1` and `period2` timestamps, `interval=1d` and `events=history`; the JSON timestamps and open/high/low/close/volume fields are parsed | The symbol and dates you specify. All seven downloads in the recorded batch succeeded. No API key is required by the program today, and a third-party public endpoint is not a stability guarantee |
| Stooq daily | HTTPS request to `stooq.com/q/d/l/` with `s`, `i=d` and `d1`/`d2` as `YYYYMMDD`; symbols without a suffix get `.us` appended | In the recorded attempt the SPY request returned content that was not a price series and failed validation. Prefer Yahoo in the current setup. The program never fabricates data and never silently switches source |
| Public fixed sample | Downloads `finance-charts-apple.csv` from the Plotly GitHub datasets repository | AAPL only, 2015-02-17 to 2017-02-16, 506 rows. The executable contains this offline sample |
| CSV import | Reads the file you select and recognises English or Chinese OHLCV headers | Whatever dates your file covers. Duplicate and invalid-row handling is decided explicitly by the import options |

After a download or import, rows are checked for dates, finite prices, OHLC ordering, non-negative volume and duplicate dates, then sorted by date. Missing trading days are not invented and a previous day's price is not carried forward. Yahoo rows without valid fields are dropped and the cleaning record keeps what happened.

Validated daily bars are stored in `%LOCALAPPDATA%/QuantDesk/library.sqlite3` and can afterwards be queried, backtested and exported offline. If `QUANTDESK_HOME` is set, that directory is used instead. The source URL or file path, provider, retrieval time, date coverage, data hash and cleaning record are kept in the dataset metadata and are visible in the *Source and cleaning* panel. A saved experiment keeps the data identifier and metadata it was produced from.

Prices use the OHLC fields returned by the provider. The Yahoo adapter does not read the adjusted close and applies no extra adjustment or dividend cash handling. Corporate actions and volume units follow the provider's conventions. No brokerage account, exchange order book or live feed is connected.

## What was actually added in the recorded batch

Imported into the current user's database on 2026-10-05 without changing existing datasets or experiments:

| Symbol | Category | Daily bars | Actual dates |
|---|---|---:|---|
| AAPL | Apple stock | 1,003 | 2022-01-03 to 2025-12-31 |
| MSFT | Microsoft stock | 1,003 | same as above |
| NVDA | Nvidia stock | 1,003 | same as above |
| TSLA | Tesla stock | 1,003 | same as above |
| SPY | S&P 500 ETF | 1,003 | same as above |
| QQQ | Nasdaq 100 ETF | 1,003 | same as above |
| 000001.SS | SSE Composite index | 969 | 2022-01-04 to 2025-12-31 |

Seven groups, 6,987 daily bars in total; the library then held nine datasets. The index data is for historical market research and is not a directly tradable stock. This batch ends explicitly at the end of 2025, so the interface shows historical dates and never presents them as today's quote.

Import evidence is in `outputs/data-expansion/import-report.json`, with the per-symbol download snapshots in the same directory and the provider probe results in `provider-check.json`. Download snapshots, the local database, screenshots and the executable are all ignored by Git. These seven groups are not embedded inside the executable; the delivery ZIP additionally ships the seven CSVs and their source records under `samples`, so they can be imported by hand without downloading anything again. An empty database on another computer still loads the fixed AAPL sample first, and neither your personal database nor your experiments travel with the application.

## Verification recorded for this round

38 tests passed, including that no experiment is created before a backtest has run, that market cards match the actual daily bars, an MA20 hand-calculation cross-check, switching the date range, and the normal window launch. The source screenshots `dashboard-data.png` and `dashboard-before-backtest.png` were reviewed. The packaged executable's `outputs/market-preview-verify/acceptance.json` passed with PID 82844: eight strategies compared, nine parameter runs, six exported files, exit code 0.

The actual new executable window, PID 87884, sat at screen position (214,128) with a size of 2452 by 1522 physical pixels, offered a maximise button in its title bar and did not fill the screen; the newly imported `000001.SS` data was observed to be usable for research. No automated clicks were sent to the already open window afterwards.

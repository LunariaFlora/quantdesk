# Quickstart: your first complete backtest

This walkthrough takes one backtest from a fresh install to an exported report. The italicised English names below are the labels you will click.

## Open the application and prepare data

Unzip the application archive completely, then double-click `QuantDesk/QuantDesk.exe`. No Python installation is needed, and the `_internal` folder must stay next to the executable. The application starts as a normal window that you can maximise manually.

The first launch shows the bundled AAPL sample of 506 daily bars. At this stage the candles, moving averages and volume are market data only; no strategy result exists yet.

To work with the 2022 to 2025 data, open *Market data*, click import CSV, select one of the files in the application's `samples` folder, for example `AAPL.csv`, and enter the matching symbol. After importing, select the dataset and check the actual dates, the row count and the *Source and cleaning* panel. The seven files hold 6,987 rows in total. `000001.SS` is the SSE Composite index: it is for index research only and is not a tradable stock. The vendor response for each CSV is stored next to it in a `.source.json` file with the same base name, and the application records this retrieval as a CSV import.

Alternatively, choose Yahoo, enter the symbol and the start and end dates, then click fetch. The program goes online only at that moment; once the data is saved you can research offline. Third-party endpoints can fail, in which case continue with a CSV or the offline AAPL sample and read the reason in the *Task log*.

## Run the first strategy

1. Open *Backtest research* and confirm which dataset is selected.
2. Choose the dual SMA template, set the fast period to 10 and the slow period to 30. SMA10 is the average of the last 10 closes. This template targets a long position while the fast line is above the slow line and targets flat while it is not; if the fast line is already above the slow line when warm-up ends, it can enter without waiting for a fresh crossover. Use the built-in template here, no JSON is required.
3. Leave the start and end dates empty so the program picks the runnable range after warm-up. If you specify dates yourself, keep the warm-up bars before the start date inside the dataset. If the application reports insufficient history, move the start later or switch to a longer dataset.
4. Set capital to 100,000, commission to 5 bps, slippage to 5 bps and position size to 80%. One basis point is 0.01%, so 5 bps equals 0.05%. Leave the remaining settings alone and click run, or press Ctrl+Enter.
5. Read the equity curve and the buy-and-hold benchmark, then the maximum drawdown, the return, the fills and the account detail. Double-click a fill to jump to the matching bar.
6. Click export and pick an empty folder. You get `report.json` and five CSV files: summary, trades, orders, round trips and equity. Keep the whole set together; the JSON file can be imported back into the experiment library.

Signals are fixed at the close and executed no earlier than the next trading day's open, so the engine cannot buy at an open that already knew that day's close. Commission, slippage and integer trading units make real fill quantities and returns differ from an idealised price calculation. Any position still open at the end is marked at the final close, so unrealised gains are not the same thing as realised profit.

## Read the results and continue

- **Cumulative return** is the change in account equity relative to the initial capital. It is not the same as realised profit and loss.
- **Maximum drawdown** is the largest fall from a running equity peak to a later low, and it describes how much loss the account carried along the way.
- **Buy-and-hold benchmark** helps you judge whether the strategy did anything beyond following a rising market. Compare only over the same data and the same date range.
- **Fills versus orders** - a fill is a simulated execution, while the order list can also contain rejections. Check capacity, trading unit and similar reasons there.
- **Win rate** uses closed round trips only, and a high win rate can still be cancelled out by a small number of large losses.

Change the slow period to 60 and run again, then watch how the number of trades and the drawdown change. Editing parameters does not update an old result: you must run again.

Open *Experiments and comparison* and try fast `5,10,15` against slow `20,30,60`, which is nine runs. Select several experiments to see their curves overlaid, and double-click one to restore its configuration. A comparison requires matching data hashes and date ranges; a parameter sweep with different warm-up lengths aligns every run to one common trading start.

The best parameters in a historical sample do not prove the best parameters in the future. To go further, choose parameters on one segment and then validate them on a later segment that took no part in the choice, keeping the failures as well as the successes.

## A demonstration order (about 5 to 8 minutes)

Open the application and explain where the historical data comes from, import one CSV, show the SMA10/30 rule and next-open execution, run the backtest, locate one fill and inspect the account, compare several parameter sets, and export the six report files.

The honest one-line description is "single-instrument daily-bar quantitative research prototype". It does fetch and import data, define strategies, run event backtests, sweep parameters, save experiments and export reports. It does not place real orders, share capital across a portfolio, model full A-share trading rules or handle corporate actions. Show what is finished and state those boundaries in the same breath.

## Data storage and backup

The default data directory is `%LOCALAPPDATA%/QuantDesk`, which holds `library.sqlite3` and the interface settings. Moving or updating the application folder does not delete that directory. Close the application before backing up, then copy the data directory. Distributing the application never copies your personal database.

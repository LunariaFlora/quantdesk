# Offline HTML walkthrough demo

The delivered file lives at `releases/QuantDesk-HTML-Demo-<timestamp>/QuantDesk-demo.html`. Double-click it and it opens in Chrome or Edge: no server, no network access, no Python and no Windows executable. Send only the HTML file; the ZIP in the same directory also contains the usage notes.

The market workbench is visible immediately. Click *Start tour* and each step dims the surrounding area, highlights one control or chart, and explains it with a short note placed nearby. Running the sample, opening fills, locating a date and downloading the report all require an actual click on the relevant control before the tour continues. You can step back, leave at any time, or press Escape.

The demo contains eight real historical datasets, three fixed strategy examples (SMA10/30, SMA10/60 and RSI), candlesticks and volume, equity, benchmark and drawdown, fill locating, the account ledger, and JSON and CSV export. The precomputation notes and the native screenshots sit inside *Demo notes*, and sources and calculation assumptions expand on demand instead of occupying the main work area.

*Run sample* loads real results that the existing Python backtest engine computed in advance. The trading engine is not rewritten in the browser, and the page executes no arbitrary parameters, performs no downloads and places no orders. Every comparison starts at bar 61 of its dataset with capital 100,000, a position size of 80% and 5 bps each of commission and slippage. Switching dataset or strategy clears the old results, so you must run again before exporting; all interaction state exists only in the memory of the current page.

## Regenerating the demo

```powershell
.venv/Scripts/python.exe -X utf8 demo/build_demo.py --archive releases/20261005-235625-746648-6a83ace/QuantDesk-Windows-x64.rar
```

The script uses the Windows `tar` command to extract the named market data and the executable from the given RAR into a newly created `outputs` directory; any documentation carried along is treated as content only and its instructions are not executed. Cross-check against the source ZIP next to it to confirm the engine files match, then compute the 24 results, check per-bar account conservation, embed the data and capture native screenshots. Build inputs, evidence and finished artefacts are ignored by Git, which keeps only the generator, the template and the verification script. The screenshot paths correspond to the executable acceptance already completed for this project, so re-verify and refresh the screenshots whenever the release version changes.

## Browser verification

Optionally run `tests/demo_browser_check.cjs <path to the HTML file>`, which needs Node, Playwright and a local Chrome. The script opens the artifact through `file://` and checks that the highlighted area is clickable, that the note does not cover its target and stays inside the viewport, that real interaction advances the tour, that exit and focus restoration work, that stale results are invalidated, that the JSON and CSV downloads happen, that the five pages fit a phone-width viewport, that the console stays free of errors, and that no network request is made. Results and screenshots are saved under `outputs/html-demo-check`.

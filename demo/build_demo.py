"""Build a self-contained, offline HTML walkthrough from the distributed RAR."""
import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quantdesk.backtest import run
from quantdesk.data import clean_csv
from quantdesk.strategies import TEMPLATES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'releases/20261005-235625-746648-6a83ace/QuantDesk-Windows-x64.rar')
    args = parser.parse_args()
    archive = args.archive.resolve()
    prefix = 'QuantDesk-Windows-x64/QuantDesk/'
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    inputs = ROOT / 'outputs' / ('html-demo-input-' + stamp)
    inputs.mkdir(parents=True, exist_ok=False)
    symbols = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'SPY', 'QQQ', '000001.SS']
    members = [prefix + '_internal/data/aapl.csv', prefix + 'QuantDesk.exe']
    members += [prefix + 'samples/' + s + suffix for s in symbols for suffix in ('.csv', '.source.json')]
    subprocess.run(['tar', '-xf', str(archive), '-C', str(inputs), *members], check=True)
    home = inputs / prefix
    # Confirm that calculations use the engine shipped alongside this release.
    with zipfile.ZipFile(archive.parent / 'QuantDesk-Source.zip') as source:
        for name in ('backtest.py', 'indicators.py', 'strategies.py', 'data.py'):
            assert source.read('QuantDesk-Source/quantdesk/' + name) == (ROOT / 'quantdesk' / name).read_bytes(), name
    datasets = []
    paths = [('sample', 'AAPL · 内置样本', 'AAPL', home / '_internal/data/aapl.csv')]
    paths += [(s, s + ' · 2022–2025', s, home / 'samples' / (s + '.csv')) for s in symbols]
    for ident, name, symbol, path in paths:
        rows, cleaning = clean_csv(path.read_text(encoding='utf-8-sig'))
        metadata = {'provider': 'Plotly 公开 AAPL 样本', 'price_basis': '样本原始 OHLC；无额外复权或分红现金处理'}
        if ident != 'sample':
            metadata = json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
        metadata.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=len(rows), start=rows[0]['date'], end=rows[-1]['date'], cleaning=cleaning)
        dataset = {'id': ident, 'name': name, 'symbol': symbol, 'metadata': metadata}
        results = {}
        definitions = {'sma30': {**TEMPLATES['sma'], 'fast': 10, 'slow': 30},
                       'sma60': {**TEMPLATES['sma'], 'fast': 10, 'slow': 60},
                       'rsi': TEMPLATES['rsi']}
        # All examples share the same start for honest comparison within a dataset.
        settings = {'capital': 100000, 'fee_bps': 5, 'slippage_bps': 5, 'allocation_pct': 80, 'start': rows[60]['date']}
        for key, definition in definitions.items():
            result = run(rows, definition, settings)
            result['dataset'] = dataset
            for bar in result['curve']:
                assert abs(bar['cash'] + bar['market_value'] - bar['equity']) < 1e-6
            results[key] = result
        datasets.append({'id': ident, 'name': name, 'symbol': symbol, 'metadata': metadata, 'rows': rows, 'results': results})
    executable_digest = hashlib.sha256((home / 'QuantDesk.exe').read_bytes()).hexdigest()
    current_digest = hashlib.sha256((ROOT / 'dist/QuantDesk/QuantDesk.exe').read_bytes()).hexdigest()
    assert executable_digest == current_digest, 'The native screenshot must match the distributed executable.'
    screenshot = ROOT / 'outputs/release-check-20261005-235420-208431-cf554bc/acceptance/desktop.png'
    screenshot_data = 'data:image/png;base64,' + base64.b64encode(screenshot.read_bytes()).decode('ascii')
    content = (ROOT / 'demo/index.template.html').read_text(encoding='utf-8')
    payload = json.dumps({'datasets': datasets, 'archive': archive.name, 'exe_sha256': executable_digest}, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    content = content.replace('__DEMO_DATA__', payload).replace('__NATIVE_SCREENSHOT__', screenshot_data)
    destination = ROOT / 'releases' / ('QuantDesk-HTML-Demo-' + stamp)
    destination.mkdir(exist_ok=False)
    page = destination / 'QuantDesk-demo.html'
    page.write_text(content, encoding='utf-8')
    (destination / '使用说明.txt').write_text('双击 QuantDesk-demo.html，用 Chrome 或 Edge 打开。无需联网、安装或启动桌面软件。\n这是交互演示：行情是真实历史数据，结果由项目引擎预先计算，支持 8 个数据集和 3 个固定策略示例，不执行任意参数回测或真实下单。\n点击“开始导览”，跟随高亮区域选择、运行、查看与导出；可查看原生程序截图，导出真实报告或行情 CSV。\n发送演示只需发送 HTML；若通过邮件，可发送同目录 ZIP。\n', encoding='utf-8-sig')
    with zipfile.ZipFile(destination / 'QuantDesk-HTML-Demo.zip', 'w', zipfile.ZIP_DEFLATED) as package:
        package.write(page, page.name)
        package.write(destination / '使用说明.txt', '使用说明.txt')
    proof = {'archive': str(archive), 'exe_sha256': executable_digest, 'datasets': len(datasets),
             'results': sum(len(d['results']) for d in datasets), 'html_bytes': page.stat().st_size,
             'output': str(page), 'source_engine_matches_release': True, 'accounting_verified': True}
    (inputs / 'build-evidence.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(proof, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

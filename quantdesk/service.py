"""Application commands shared by desktop, tests and command-line research."""
import csv
import io
import json
import itertools
import time
from pathlib import Path
from copy import deepcopy
from .storage import Store, now
from .data import clean_csv, fetch, to_csv
from .strategies import validate, warmup
from .backtest import run, config


class Service:
    def __init__(self, home=None):
        self.store = Store(home)

    def import_csv(self, path, name=None, symbol='CUSTOM', drop_invalid=False, duplicates='error'):
        path = Path(path)
        try:
            raw = path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            raw = path.read_text(encoding='gb18030')
        rows, report = clean_csv(raw, drop_invalid, duplicates)
        ident = self.store.add_dataset(name or path.stem, symbol, rows,
                                       {'source': str(path), 'provider': 'csv', 'price_basis': '用户导入；复权口径由用户确认', 'cleaning': report})
        self.store.log('INFO', f'导入 {name or path.stem}：{len(rows)} 根日线，清洗移除 {report["removed"]} 行')
        return ident

    def fetch(self, provider, symbol, start, end):
        try:
            rows, metadata = fetch(provider, symbol, start, end)
            ident = self.store.add_dataset(f'{symbol} · {provider} · {start}–{end}', symbol, rows, metadata)
            self.store.log('INFO', f'下载 {symbol}：{len(rows)} 根日线，来源 {provider}')
            return ident
        except Exception as exc:
            self.store.log('ERROR', f'下载失败 {symbol} / {provider}', str(exc))
            raise

    def backtest(self, dataset_id, strategy, settings, name=None, cancel=None):
        started = time.perf_counter()
        dataset = self.store.dataset(dataset_id)
        result = run(self.store.bars(dataset_id), strategy, settings, cancel)
        result.update(dataset=dataset, created_at=now(), duration_seconds=time.perf_counter()-started)
        ident = self.store.save('experiment', name or f'{strategy["name"]} · {result["summary"]["start"]}', result)
        self.store.log('INFO', f'回测完成 {strategy["name"]}，{result["summary"]["trades"]} 笔成交，{result["duration_seconds"]:.3f}s')
        return {'id': ident, **result}

    def tune(self, dataset_id, strategy, settings, grid, cancel=None, progress=None):
        if not isinstance(grid, dict) or not grid:
            raise ValueError('参数网格必须是非空对象，例如 {"fast":[5,10],"slow":[20,30]}')
        allowed = {'fast', 'slow', 'period', 'band', 'oversold', 'overbought'}
        if not set(grid).issubset(allowed) or any(not isinstance(v, list) or not v for v in grid.values()):
            raise ValueError('网格字段只能是策略参数，且每项必须为非空列表')
        count = 1
        for v in grid.values():
            count *= len(v)
        if count > 2000:
            raise ValueError('单次网格最多 2,000 组')
        candidates = []
        for values in itertools.product(*grid.values()):
            definition = {**strategy, **dict(zip(grid, values))}
            candidates.append(validate(definition))
        rows = self.store.bars(dataset_id)
        begin = max(warmup(s) for s in candidates)
        if begin >= len(rows)-1:
            raise ValueError('数据不足以满足最大预热周期')
        aligned = config(settings)
        aligned['start'] = max(aligned['start'] or rows[begin]['date'], rows[begin]['date'])
        results = []
        for i, candidate in enumerate(candidates):
            if cancel and cancel():
                raise InterruptedError('参数研究已取消，已完成的实验保留')
            result = self.backtest(dataset_id, candidate, aligned,
                                   f'{candidate["name"]} · '+', '.join(f'{k}={candidate[k]}' for k in grid), cancel)
            results.append(result)
            if progress:
                progress(i+1, len(candidates))
        return results

    def compare(self, dataset_id, strategies, settings, cancel=None, progress=None):
        if not strategies or len(strategies) > 50:
            raise ValueError('请选择 1–50 个策略')
        candidates = [validate(s) for s in strategies]
        rows = self.store.bars(dataset_id)
        index = max(warmup(s) for s in candidates)
        if index >= len(rows)-1:
            raise ValueError('对比数据不足')
        aligned = config(settings)
        aligned['start'] = max(aligned['start'] or rows[index]['date'], rows[index]['date'])
        results = []
        for i, s in enumerate(candidates):
            results.append(self.backtest(dataset_id, s, aligned, cancel=cancel))
            if progress:
                progress(i+1, len(candidates))
        return results


def export_result(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    sections = {'summary': [result['summary']], 'trades': result['trades'], 'orders': result['orders'],
                'round_trips': result['round_trips'], 'equity': result['curve']}
    for name, rows in sections.items():
        with (directory / f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            if rows:
                fields = list(dict.fromkeys(k for r in rows for k in r))
                writer = csv.DictWriter(stream, fields)
                writer.writeheader()
                writer.writerows(rows)
            else:
                stream.write('no_records\n')
    return str(directory)

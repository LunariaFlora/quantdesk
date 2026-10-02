"""透明的日线回测：收盘判断趋势，下一根日线开盘执行。仅使用 Python 标准库。"""
import csv
import io
import math
from datetime import date


def parse_csv(text):
    """统一 CSV 字段，拒绝重复日期、无穷值和不合理 OHLC。"""
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames:
        raise ValueError('CSV 为空，需要 date,open,high,low,close,volume 列')
    names = {n: n.strip().lower().replace('aapl.', '') for n in reader.fieldnames}
    required = {'date', 'open', 'high', 'low', 'close', 'volume'}
    if not required.issubset(set(names.values())):
        raise ValueError('CSV 缺少列：date,open,high,low,close,volume')
    rows, seen = [], set()
    for number, raw in enumerate(reader, 2):
        if number > 20001:
            raise ValueError('最多支持 20,000 根日线')
        try:
            row = {names[k]: v for k, v in raw.items() if k in names}
            d = date.fromisoformat(row['date']).isoformat()
            values = {k: float(row[k]) for k in required - {'date'}}
            if d in seen or not all(math.isfinite(x) for x in values.values()):
                raise ValueError()
            o, h, l, c = [values[k] for k in ('open', 'high', 'low', 'close')]
            if not (1e-8 <= l <= min(o, c) <= max(o, c) <= h <= 1e12) or not 0 <= values['volume'] <= 1e18:
                raise ValueError()
            seen.add(d)
            rows.append({'date': d, **values})
        except (ValueError, TypeError, KeyError):
            raise ValueError(f'CSV 第 {number} 行无效：请检查日期、重复日期、价格和成交量') from None
    if len(rows) < 3:
        raise ValueError('至少需要 3 根有效日线')
    return sorted(rows, key=lambda r: r['date'])


def number(params, key, default, low, high, integer=False):
    try:
        value = float(params.get(key, default))
        if not math.isfinite(value) or not low <= value <= high or (integer and not value.is_integer()):
            raise ValueError()
        return int(value) if integer else value
    except (ValueError, TypeError):
        raise ValueError(f'{key} 必须在 {low}–{high} 之间' + ('，且为整数' if integer else '')) from None


def backtest(rows, params):
    fast = number(params, 'fast', 10, 1, 250, True)
    slow = number(params, 'slow', 30, 2, 500, True)
    if fast >= slow:
        raise ValueError('短均线周期必须小于长均线周期')
    initial = number(params, 'capital', 100000, 1, 1e9)
    fee = number(params, 'fee_bps', 5, 0, 1000) / 10000
    slip = number(params, 'slippage_bps', 5, 0, 1000) / 10000
    start, end = params.get('start') or rows[0]['date'], params.get('end') or rows[-1]['date']
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError('日期必须使用 YYYY-MM-DD 格式') from None
    if start > end:
        raise ValueError('开始日期不能晚于结束日期')
    # 仅使用选中区间的数据进行预热，让基准与策略在同一天开始投资。
    bars = [r for r in rows if start <= r['date'] <= end]
    if len(bars) <= slow:
        raise ValueError(f'所选区间需要至少 {slow + 1} 根日线（含 {slow} 根预热）')
    cash, shares, benchmark_cash, benchmark_shares = initial, 0, initial, 0
    peak, benchmark_peak, max_dd, benchmark_dd, fees = initial, initial, 0, 0, 0
    trades, curve, closes = [], [], []
    previous_target, signal_date, entry_cost = False, None, 0
    completed, wins, benchmark_started = 0, 0, False
    for i, bar in enumerate(bars):
        # 此处 previous_target 只来自昨天收盘，尚未读取今天收盘价。
        if i >= slow:
            if not benchmark_started and bar['volume'] > 0:
                p = bar['open'] * (1 + slip)
                benchmark_shares = math.floor(initial / (p * (1 + fee)))
                benchmark_cash -= benchmark_shares * p * (1 + fee)
                benchmark_started = True
            side, qty, price, cost = None, 0, 0, 0
            if previous_target and shares == 0 and bar['volume'] > 0:
                price = bar['open'] * (1 + slip)
                qty = math.floor(cash / (price * (1 + fee)))
                if qty:
                    cost = qty * price * fee
                    entry_cost = qty * price + cost
                    cash -= entry_cost
                    shares = qty
                    side = '买入'
            elif not previous_target and shares > 0 and bar['volume'] > 0:
                price = bar['open'] * (1 - slip)
                qty = shares
                cost = qty * price * fee
                proceeds = qty * price - cost
                cash += proceeds
                shares = 0
                completed += 1
                wins += proceeds > entry_cost
                side = '卖出'
            if side:
                fees += cost
                trades.append({'signal_date': signal_date, 'date': bar['date'], 'side': side,
                               'price': price, 'quantity': qty, 'fee': cost, 'cash': cash,
                               'reason': '短均线高于长均线' if side == '买入' else '短均线不高于长均线'})
        closes.append(bar['close'])
        short_ma = sum(closes[-fast:]) / fast if len(closes) >= fast else None
        long_ma = sum(closes[-slow:]) / slow if len(closes) >= slow else None
        previous_target = long_ma is not None and short_ma > long_ma
        signal_date = bar['date']
        equity = cash + shares * bar['close']
        benchmark = benchmark_cash + benchmark_shares * bar['close']
        peak, benchmark_peak = max(peak, equity), max(benchmark_peak, benchmark)
        dd = equity / peak - 1
        max_dd, benchmark_dd = min(max_dd, dd), min(benchmark_dd, benchmark / benchmark_peak - 1)
        curve.append({**bar, 'fast': short_ma, 'slow': long_ma, 'equity': equity,
                      'benchmark': benchmark, 'drawdown': dd * 100, 'shares': shares})
    return {'params': {'fast': fast, 'slow': slow, 'capital': initial, 'fee_bps': fee * 10000,
                       'slippage_bps': slip * 10000, 'start': start, 'end': end},
            'summary': {'return_pct': (equity / initial - 1) * 100,
                        'benchmark_pct': (benchmark / initial - 1) * 100,
                        'max_drawdown_pct': max_dd * 100, 'benchmark_drawdown_pct': benchmark_dd * 100,
                        'equity': equity, 'cash': cash, 'shares': shares, 'fees': fees,
                        'trades': len(trades), 'closed_trades': completed,
                        'win_rate_pct': wins / completed * 100 if completed else None,
                        'trading_start': bars[slow]['date'], 'bars': len(bars)},
            'curve': curve, 'trades': trades}


if __name__ == '__main__':
    import json
    from pathlib import Path
    sample = Path(__file__).resolve().parent / 'data' / 'aapl.csv'
    if not sample.exists():
        raise SystemExit('请先运行 python download_data.py')
    result = backtest(parse_csv(sample.read_text(encoding='utf-8-sig')), {})
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))

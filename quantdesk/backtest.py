"""Event-based daily long-only broker with explicit orders, fills and accounting."""
import math
import statistics
from datetime import date
from .indicators import series
from .strategies import validate, warmup, target

VERSION = 'daily-event-2.0'


def config(raw):
    defaults = {'capital': 100000, 'fee_bps': 5, 'slippage_bps': 5, 'allocation_pct': 100,
                'stop_loss_pct': 0, 'take_profit_pct': 0, 'risk_free_pct': 0, 'lot_size': 1,
                'volume_limit_pct': 100, 'annual_days': 252, 'start': '', 'end': ''}
    if not isinstance(raw, dict):
        raise ValueError('回测配置必须为对象')
    c = {**defaults, **raw}
    for key, low, high, integer in [('capital', 1, 1e9, False), ('fee_bps', 0, 1000, False), ('slippage_bps', 0, 1000, False),
                                   ('allocation_pct', .1, 100, False), ('stop_loss_pct', 0, 99, False), ('take_profit_pct', 0, 1000, False),
                                   ('risk_free_pct', -10, 100, False), ('lot_size', 1, 100000, True), ('volume_limit_pct', .01, 100, False),
                                   ('annual_days', 1, 366, True)]:
        try:
            v = float(c[key])
            if not math.isfinite(v) or not low <= v <= high or (integer and not v.is_integer()):
                raise ValueError()
            c[key] = int(v) if integer else v
        except (ValueError, TypeError):
            raise ValueError(f'回测参数 {key} 无效，范围 {low}–{high}') from None
    for key in ('start', 'end'):
        if c[key]:
            c[key] = date.fromisoformat(c[key]).isoformat()
    if c['start'] and c['end'] and c['start'] > c['end']:
        raise ValueError('开始日期晚于结束日期')
    return c


def run(rows, definition, raw_config, cancel=None):
    s, c = validate(definition), config(raw_config)
    if not rows or len(rows) < 3:
        raise ValueError('至少需要 3 根日线')
    for i, r in enumerate(rows):
        o, h, l, close, vol = (r[k] for k in ('open', 'high', 'low', 'close', 'volume'))
        if not all(math.isfinite(v) for v in (o, h, l, close, vol)) or not 0 < l <= min(o, close) <= max(o, close) <= h or vol < 0:
            raise ValueError('行情价格或成交量无效')
        if i and rows[i-1]['date'] >= r['date']:
            raise ValueError('行情必须按日期升序且无重复')
    indicators = series(rows, s['fast'], s['slow'], s['period'], s['band'])
    first = next((i for i, r in enumerate(rows) if r['date'] >= (c['start'] or rows[0]['date'])), len(rows))
    first = max(first, warmup(s))
    selected = [i for i in range(first, len(rows)) if rows[i]['date'] <= (c['end'] or rows[-1]['date'])]
    if len(selected) < 2:
        raise ValueError(f'区间不足；需要至少 {warmup(s)} 根区间之前的预热行情和 2 根交易日线')
    if c['start'] and rows[first]['date'] > c['start']:
        # Insufficient warmup must not silently shift comparison periods.
        in_range_before = [r for r in rows[:first] if r['date'] >= c['start']]
        if in_range_before:
            raise ValueError('开始日期之前的预热数据不足，请将开始日期后移或补充更早行情')
    cash, shares, entry_price, entry_cost, entry_date = c['capital'], 0, 0, 0, ''
    realized, fees, peak = 0.0, 0.0, c['capital']
    benchmark_cash, benchmark_shares = c['capital'], 0
    pending, fills, orders, rounds, curve = None, [], [], [], []
    fee, slip, lot = c['fee_bps']/10000, c['slippage_bps']/10000, c['lot_size']
    desired = target(s, indicators, first-1, False)

    def make_order(side, signal_date, reason):
        order = {'id': len(orders)+1, 'side': side, 'signal_date': signal_date,
                 'status': 'submitted', 'reason': reason, 'date': None, 'quantity': 0, 'price': None}
        orders.append(order)
        return order

    def execute(order, bar, reference):
        nonlocal cash, shares, entry_price, entry_cost, entry_date, realized, fees
        price = reference*(1+slip if order['side'] == '买入' else 1-slip)
        if order['side'] == '买入':
            budget = min(cash, (cash+shares*bar['open'])*c['allocation_pct']/100)
            qty = math.floor(budget/(price*(1+fee))/lot)*lot
            if qty < lot:
                order.update(status='rejected', date=bar['date'], reason='资金不足一个交易单位')
                return
        else:
            qty = shares
        capacity = math.floor(bar['volume']*c['volume_limit_pct']/100/lot)*lot
        # All-or-none model is explicit: reject capacity shortfalls, no fictional fills.
        if qty > capacity:
            order.update(status='rejected', date=bar['date'], reason='成交量容量不足；本模型整笔拒绝')
            return
        if qty <= 0:
            order.update(status='canceled', date=bar['date'], reason='没有可卖持仓')
            return
        commission = qty*price*fee
        pnl = None
        if order['side'] == '买入':
            entry_price, entry_cost, entry_date = price, qty*price+commission, bar['date']
            cash -= entry_cost
            shares = qty
        else:
            proceeds = qty*price-commission
            pnl = proceeds-entry_cost
            realized += pnl
            cash += proceeds
            rounds.append({'entry_date': entry_date, 'exit_date': bar['date'], 'quantity': qty,
                           'entry_price': entry_price, 'exit_price': price, 'pnl': pnl,
                           'return_pct': pnl/entry_cost*100, 'holding_days': (date.fromisoformat(bar['date'])-date.fromisoformat(entry_date)).days})
            shares, entry_cost = 0, 0
        fees += commission
        order.update(status='filled', date=bar['date'], price=price, quantity=qty)
        fills.append({**order, 'fee': commission, 'cash': cash, 'realized_pnl': pnl})

    for offset, i in enumerate(selected):
        if cancel and cancel():
            raise InterruptedError('任务已取消')
        bar = rows[i]
        if not benchmark_shares and benchmark_cash == c['capital'] and bar['volume'] > 0:
            bp = bar['open']*(1+slip)
            benchmark_shares = math.floor(benchmark_cash/(bp*(1+fee))/lot)*lot
            benchmark_cash -= benchmark_shares*bp*(1+fee)
        if pending:
            if bar['volume'] > 0:
                execute(pending, bar, bar['open'])
                pending = None
        elif desired != bool(shares):
            pending = make_order('买入' if desired else '卖出', rows[i-1]['date'], '策略信号')
            if bar['volume'] > 0:
                execute(pending, bar, bar['open'])
                pending = None
        if shares and bar['volume'] > 0:
            stop = entry_price*(1-c['stop_loss_pct']/100) if c['stop_loss_pct'] else None
            take = entry_price*(1+c['take_profit_pct']/100) if c['take_profit_pct'] else None
            reason, reference = None, None
            if stop is not None and bar['low'] <= stop:
                reason, reference = '止损（同日双触发时优先）', min(bar['open'], stop)
            elif take is not None and bar['high'] >= take:
                reason, reference = '止盈', max(bar['open'], take)
            if reason:
                execute(make_order('卖出', bar['date'], reason), bar, reference)
        equity = cash+shares*bar['close']
        peak = max(peak, equity)
        unrealized = shares*bar['close']-entry_cost if shares else 0
        curve.append({**bar, **{key: value[i] for key, value in indicators.items()},
                      'equity': equity, 'benchmark': benchmark_cash+benchmark_shares*bar['close'],
                      'cash': cash, 'shares': shares, 'market_value': shares*bar['close'],
                      'realized_pnl': realized, 'unrealized_pnl': unrealized, 'pnl': equity-c['capital'],
                      'drawdown': (equity/peak-1)*100, 'return_pct': (equity/c['capital']-1)*100})
        # Reconcile a deferred signal at today's close; expired signals cannot fill later.
        desired = target(s, indicators, i, bool(shares))
        if pending and ((pending['side'] == '买入') != desired):
            pending.update(status='canceled', date=bar['date'], reason='信号失效')
            pending = None
    if pending:
        pending.update(status='canceled', date=curve[-1]['date'], reason='区间结束，未成交')
    ending = curve[-1]['equity']
    days = (date.fromisoformat(curve[-1]['date'])-date.fromisoformat(curve[0]['date'])).days+1
    returns, previous = [], c['capital']
    for row in curve:
        returns.append(row['equity']/previous-1)
        previous = row['equity']
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0
    sharpe = (statistics.mean(returns)-c['risk_free_pct']/100/c['annual_days'])/stdev*math.sqrt(c['annual_days']) if stdev > 1e-12 else None
    winners, losers = [r['pnl'] for r in rounds if r['pnl'] > 0], [-r['pnl'] for r in rounds if r['pnl'] < 0]
    annualized = math.expm1(math.log(ending/c['capital'])*365.25/days)*100 if ending > 0 and math.log(ending/c['capital'])*365.25/days < 700 else None
    summary = {'return_pct': (ending/c['capital']-1)*100, 'annualized_return_pct': annualized,
               'max_drawdown_pct': min(r['drawdown'] for r in curve), 'sharpe': sharpe,
               'win_rate_pct': len(winners)/len(rounds)*100 if rounds else None,
               'profit_loss_ratio': statistics.mean(winners)/statistics.mean(losers) if winners and losers else None,
               'profit_factor': sum(winners)/sum(losers) if losers else None,
               'trade_frequency_year': len(fills)*365.25/days, 'closed_trades': len(rounds), 'trades': len(fills),
               'fees': fees, 'equity': ending, 'cash': cash, 'shares': shares,
               'realized_pnl': realized, 'unrealized_pnl': curve[-1]['unrealized_pnl'], 'pnl': ending-c['capital'],
               'benchmark_pct': (curve[-1]['benchmark']/c['capital']-1)*100,
               'exposure_pct': sum(r['shares'] > 0 for r in curve)/len(curve)*100,
               'volatility_pct': stdev*math.sqrt(c['annual_days'])*100,
               'start': curve[0]['date'], 'end': curve[-1]['date'], 'bars': len(curve)}
    return {'engine_version': VERSION, 'strategy': s, 'config': c, 'summary': summary,
            'curve': curve, 'trades': fills, 'orders': orders, 'round_trips': rounds,
            'assumptions': {'execution': '收盘信号下一日开盘；预热使用交易区间之前的数据',
                            'stops': '日线触发；跳空按开盘；同 bar 双触发止损优先；买入当天保护单生效',
                            'capacity': '按成交量百分比，整笔成交或拒绝，无部分成交',
                            'account': '仅做多无杠杆，期末按收盘估值不强平，无企业行动/税费/涨跌停模型',
                            'annualization': '年化收益按自然日 CAGR；夏普按指定年交易日数、日收益样本标准差'}}

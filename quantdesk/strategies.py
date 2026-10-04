"""Declarative strategy definitions; user rules are data, never evaluated Python."""
from copy import deepcopy
import math

TEMPLATES = {
    'sma': {'name': '双均线趋势', 'kind': 'sma', 'fast': 10, 'slow': 30},
    'ema': {'name': '双 EMA 趋势', 'kind': 'ema', 'fast': 10, 'slow': 30},
    'rsi': {'name': 'RSI 均值回归', 'kind': 'rsi', 'fast': 10, 'slow': 30, 'period': 14, 'oversold': 30, 'overbought': 70},
    'bollinger': {'name': '布林带回归', 'kind': 'bollinger', 'fast': 10, 'slow': 20, 'band': 2},
    'breakout': {'name': '通道突破', 'kind': 'breakout', 'fast': 10, 'slow': 30},
    'macd': {'name': 'MACD 趋势', 'kind': 'macd', 'fast': 12, 'slow': 26},
    'buy_hold': {'name': '买入持有', 'kind': 'buy_hold', 'fast': 10, 'slow': 30},
    'custom': {'name': '自定义规则', 'kind': 'custom', 'fast': 10, 'slow': 30, 'period': 14,
               'entry': [{'left': 'rsi', 'op': '<', 'right': 30}], 'exit': [{'left': 'rsi', 'op': '>', 'right': 65}]}}
KEYS = {'close', 'sma_fast', 'sma_slow', 'ema_fast', 'ema_slow', 'rsi', 'bb_upper', 'bb_lower', 'macd', 'macd_signal', 'atr', 'high_channel', 'low_channel'}


def validate(definition):
    if not isinstance(definition, dict) or definition.get('kind') not in TEMPLATES:
        raise ValueError('策略类型无效')
    s = {**deepcopy(TEMPLATES[definition['kind']]), **definition}
    if not isinstance(s.get('name'), str) or not s['name'].strip():
        raise ValueError('策略名称不能为空')
    for key, default, low, high, integer in [('fast', 10, 1, 500, True), ('slow', 30, 2, 1000, True),
                                          ('period', 14, 2, 500, True), ('band', 2, .1, 10, False),
                                          ('oversold', 30, 0, 100, False), ('overbought', 70, 0, 100, False)]:
        try:
            value = float(s.get(key, default))
            if not math.isfinite(value) or not low <= value <= high or (integer and not value.is_integer()):
                raise ValueError()
            s[key] = int(value) if integer else value
        except (TypeError, ValueError):
            raise ValueError(f'策略参数 {key} 无效，范围 {low}–{high}') from None
    if s['fast'] >= s['slow']:
        raise ValueError('fast 必须小于 slow')
    if s['oversold'] >= s['overbought']:
        raise ValueError('RSI 买入阈值必须小于卖出阈值')
    if s['kind'] == 'custom':
        for field in ('entry', 'exit'):
            rules = s.get(field)
            if not isinstance(rules, list) or not 1 <= len(rules) <= 10:
                raise ValueError('entry 和 exit 各需要 1–10 条规则；同组条件全部满足时触发')
            for rule in rules:
                if not isinstance(rule, dict) or rule.get('left') not in KEYS or rule.get('op') not in ('>', '<', '>=', '<=', 'cross_above', 'cross_below'):
                    raise ValueError('规则字段或比较符无效')
                right = rule.get('right')
                if isinstance(right, str):
                    if right not in KEYS:
                        raise ValueError('right 必须为指标名或数值')
                elif not isinstance(right, (int, float)) or not math.isfinite(right):
                    raise ValueError('right 必须为指标名或有限数值')
    return s


def warmup(s):
    return max(s['slow'], s['period']+1, 35 if s['kind'] in ('macd', 'custom') else 0)


def condition(rule, values, i):
    a = values[rule['left']][i]
    right = rule['right']
    b = values[right][i] if isinstance(right, str) else right
    if a is None or b is None:
        return False
    op = rule['op']
    if op in ('cross_above', 'cross_below'):
        if i == 0:
            return False
        pa = values[rule['left']][i-1]
        pb = values[right][i-1] if isinstance(right, str) else right
        return pa is not None and pb is not None and (pa <= pb and a > b if op == 'cross_above' else pa >= pb and a < b)
    return {'>': a > b, '<': a < b, '>=': a >= b, '<=': a <= b}[op]


def target(s, values, i, holding):
    kind = s['kind']
    if kind in ('sma', 'ema'):
        a, b = values[kind+'_fast'][i], values[kind+'_slow'][i]
        return a is not None and b is not None and a > b
    if kind == 'buy_hold':
        return True
    if kind == 'rsi':
        v = values['rsi'][i]
        return holding if v is None else (v < s['overbought'] if holding else v < s['oversold'])
    if kind == 'bollinger':
        threshold = values['sma_slow'][i] if holding else values['bb_lower'][i]
        return holding if threshold is None else values['close'][i] < threshold
    if kind == 'macd':
        a, b = values['macd'][i], values['macd_signal'][i]
        return a is not None and b is not None and a > b
    if kind == 'breakout':
        if i == 0:
            return holding
        threshold = values['low_channel'][i-1] if holding else values['high_channel'][i-1]
        return holding if threshold is None else values['close'][i] > threshold
    rules = s['exit'] if holding else s['entry']
    trigger = all(condition(r, values, i) for r in rules)
    return not trigger if holding else trigger

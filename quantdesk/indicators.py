"""Causal indicator series. Null means insufficient history, never future filling."""
import math
from collections import deque


def sma(values, period):
    result, window, total = [], deque(), 0.0
    for value in values:
        window.append(value)
        total += value
        if len(window) > period:
            total -= window.popleft()
        result.append(total / period if len(window) == period else None)
    return result


def ema(values, period):
    result, total, current = [], 0.0, None
    for i, value in enumerate(values):
        if i < period:
            total += value
        if i == period-1:
            current = total/period
        elif i >= period:
            current += (value-current)*2/(period+1)
        result.append(current)
    return result


def rsi(values, period=14):
    result = [None] * len(values)
    gain = loss = 0.0
    for i in range(1, len(values)):
        delta = values[i] - values[i-1]
        up, down = max(delta, 0), max(-delta, 0)
        if i <= period:
            gain += up/period
            loss += down/period
        else:
            gain = (gain*(period-1)+up)/period
            loss = (loss*(period-1)+down)/period
        if i >= period:
            result[i] = 50.0 if gain == loss == 0 else (100.0 if loss == 0 else 100-100/(1+gain/loss))
    return result


def rolling_extreme(values, period, maximum=True):
    queue, result = deque(), []
    for i, value in enumerate(values):
        while queue and queue[0][0] <= i-period:
            queue.popleft()
        while queue and (queue[-1][1] <= value if maximum else queue[-1][1] >= value):
            queue.pop()
        queue.append((i, value))
        result.append(queue[0][1] if i >= period-1 else None)
    return result


def series(bars, fast=10, slow=30, period=14, band=2):
    closes = [r['close'] for r in bars]
    middle = sma(closes, slow)
    square = sma([x*x for x in closes], slow)
    std = [math.sqrt(max(0, sq-m*m)) if m is not None else None for m, sq in zip(middle, square)]
    macd_fast, macd_slow = ema(closes, 12), ema(closes, 26)
    macd = [a-b if a is not None and b is not None else None for a, b in zip(macd_fast, macd_slow)]
    valid = [v for v in macd if v is not None]
    signal = [None]*(len(macd)-len(valid)) + ema(valid, 9)
    tr = [r['high']-r['low'] if i == 0 else max(r['high']-r['low'], abs(r['high']-closes[i-1]), abs(r['low']-closes[i-1])) for i, r in enumerate(bars)]
    atr, value = [], None
    for i, t in enumerate(tr):
        if i == period-1:
            value = sum(tr[:period])/period
        elif i >= period:
            value = (value*(period-1)+t)/period
        atr.append(value)
    return {'close': closes, 'sma_fast': sma(closes, fast), 'sma_slow': middle,
            'ema_fast': ema(closes, fast), 'ema_slow': ema(closes, slow), 'rsi': rsi(closes, period),
            'bb_upper': [m+band*s if m is not None else None for m, s in zip(middle, std)],
            'bb_lower': [m-band*s if m is not None else None for m, s in zip(middle, std)],
            'macd': macd, 'macd_signal': signal, 'atr': atr,
            'high_channel': rolling_extreme([r['high'] for r in bars], slow),
            'low_channel': rolling_extreme([r['low'] for r in bars], fast)}

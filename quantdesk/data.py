"""Historical data adapters and explicit, audited CSV cleaning."""
import csv
import io
import json
import math
import re
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

ALIASES = {'日期': 'date', '时间': 'date', '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close', '成交量': 'volume', 'datetime': 'date'}
FIELDS = ('date', 'open', 'high', 'low', 'close', 'volume')


def clean_csv(text, drop_invalid=False, duplicates='error'):
    if duplicates not in ('error', 'first', 'last'):
        raise ValueError('重复日期规则必须为 error、first 或 last')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    names = {}
    for key in reader.fieldnames or []:
        field = key.strip().lower().split('.')[-1]
        names[key] = ALIASES.get(field, field)
    if not set(FIELDS).issubset(names.values()):
        raise ValueError('需要 date/open/high/low/close/volume 列，也支持日期/开盘/最高/最低/收盘/成交量')
    issues, rows, input_rows, duplicate_count = [], {}, 0, 0
    for line, raw in enumerate(reader, 2):
        input_rows += 1
        if input_rows > 250000:
            raise ValueError('单次最多导入 250,000 根日线')
        try:
            row = {names[k]: v for k, v in raw.items() if k in names}
            d = date.fromisoformat(row['date'].strip().replace('/', '-')).isoformat()
            nums = {k: float(row[k]) for k in FIELDS[1:]}
            o, h, l, c, vol = (nums[k] for k in FIELDS[1:])
            if not all(math.isfinite(v) for v in nums.values()) or not (1e-8 <= l <= min(o, c) <= max(o, c) <= h <= 1e12) or not 0 <= vol <= 1e18:
                raise ValueError('OHLC 或成交量无效')
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            issue = f'第 {line} 行无效：{exc}'
            if not drop_invalid:
                raise ValueError(issue) from None
            issues.append(issue)
            continue
        if d in rows:
            duplicate_count += 1
            if duplicates == 'error':
                raise ValueError(f'第 {line} 行日期重复：{d}')
            issues.append(f'第 {line} 行日期重复 {d}；保留{duplicates}')
            if duplicates == 'first':
                continue
        rows[d] = {'date': d, **nums}
    ordered = [rows[d] for d in sorted(rows)]
    if len(ordered) < 3:
        raise ValueError('清洗后至少需要 3 根日线')
    gaps = [(a['date'], b['date']) for a, b in zip(ordered, ordered[1:]) if (date.fromisoformat(b['date']) - date.fromisoformat(a['date'])).days > 7]
    report = {'input_rows': input_rows, 'output_rows': len(ordered), 'removed': input_rows-len(ordered),
              'duplicate_rows': duplicate_count, 'issues': issues[:100], 'long_gaps': gaps,
              'policy': {'drop_invalid': drop_invalid, 'duplicates': duplicates, 'missing_dates': '不插入缺失交易日，不前向填充价格'}}
    return ordered, report


def to_csv(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def request(url):
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0 QuantDesk/0.2'}), timeout=25) as response:
            raw = response.read(30_000_001)
        if len(raw) > 30_000_000:
            raise ValueError('数据响应超过 30 MB')
        return raw.decode('utf-8-sig')
    except Exception as exc:
        raise ValueError(f'数据请求失败：{type(exc).__name__}: {exc}') from None


def fetch(provider, symbol, start, end):
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    if begin > finish:
        raise ValueError('开始日期晚于结束日期')
    symbol = symbol.strip().upper()
    if not re.fullmatch(r'[A-Z0-9.^=_-]{1,30}', symbol):
        raise ValueError('股票代码格式无效')
    if provider == 'plotly':
        if symbol != 'AAPL':
            raise ValueError('公开固定样本仅支持 AAPL；其他代码请选择 Yahoo 或 Stooq')
        url = 'https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv'
        rows, report = clean_csv(request(url))
        basis = '原始 OHLC，未计分红'
    elif provider == 'stooq':
        ticker = symbol.lower() if '.' in symbol else symbol.lower()+'.us'
        url = 'https://stooq.com/q/d/l/?' + urlencode({'s': ticker, 'i': 'd', 'd1': begin.strftime('%Y%m%d'), 'd2': finish.strftime('%Y%m%d')})
        rows, report = clean_csv(request(url))
        basis = '供应商 OHLC；供应商复权口径需用户核对'
    elif provider == 'yahoo':
        first = int(datetime.combine(begin, datetime.min.time(), timezone.utc).timestamp())
        last = int(datetime.combine(finish+timedelta(days=1), datetime.min.time(), timezone.utc).timestamp())
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?' + urlencode({'period1': first, 'period2': last, 'interval': '1d', 'events': 'history'})
        payload = json.loads(request(url))
        chart = payload.get('chart', {})
        if chart.get('error') or not chart.get('result'):
            raise ValueError(f'Yahoo 无行情：{chart.get("error")}')
        item = chart['result'][0]
        q = item['indicators']['quote'][0]
        offset = item.get('meta', {}).get('gmtoffset', 0)
        raw_rows = [{**{k: q[k][i] for k in FIELDS[1:]}, 'date': datetime.fromtimestamp(t+offset, timezone.utc).date().isoformat()} for i, t in enumerate(item.get('timestamp', []))]
        rows, report = clean_csv(to_csv(raw_rows), drop_invalid=True)
        basis = 'Yahoo 原始 OHLC；不使用 adjusted close，未计分红/拆股现金调整'
    else:
        raise ValueError('未知的数据源')
    rows = [r for r in rows if start <= r['date'] <= end]
    if len(rows) < 3:
        raise ValueError('该代码和日期区间返回不足 3 根日线，请调整日期或数据源')
    return rows, {'provider': provider, 'source': url, 'symbol': symbol, 'interval': '1d', 'price_basis': basis,
                  'currency': 'USD' if not symbol.endswith(('.SS', '.SZ')) else 'CNY',
                  'fetched_at': datetime.now(timezone.utc).isoformat(), 'cleaning': report}

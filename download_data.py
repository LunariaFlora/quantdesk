"""下载公开历史样本到被 Git 忽略的 data/，记录来源和校验值。"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from engine import parse_csv

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv'


def download():
    raw = urlopen(SOURCE, timeout=30).read()
    rows = parse_csv(raw.decode('utf-8-sig'))
    folder = ROOT / 'data'
    folder.mkdir(exist_ok=True)
    (folder / 'aapl.csv').write_bytes(raw)
    meta = {'symbol': 'AAPL', 'name': 'Apple 历史样本', 'source': SOURCE,
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(raw).hexdigest(), 'rows': len(rows),
            'start': rows[0]['date'], 'end': rows[-1]['date'],
            'price_basis': '原始 OHLC；不使用 Adjusted 列；未计股息，非总回报。', 'currency': 'USD'}
    (folder / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    download()

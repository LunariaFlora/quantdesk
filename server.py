"""仅监听本机的回测服务，不需要账户、API 密钥或第三方依赖。"""
import json
import hashlib
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from engine import parse_csv, backtest

ROOT = Path(__file__).resolve().parent
STATIC = {'/': ('web/index.html', 'text/html'), '/app.js': ('web/app.js', 'text/javascript'),
          '/style.css': ('web/style.css', 'text/css'), '/learning': ('学习清单.txt', 'text/plain')}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, mime='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in STATIC:
            name, mime = STATIC[path]
            self.send(200, (ROOT / name).read_bytes(), mime)
        elif path == '/api/data':
            try:
                raw = (ROOT / 'data/aapl.csv').read_text(encoding='utf-8-sig')
                meta = json.loads((ROOT / 'data/metadata.json').read_text(encoding='utf-8'))
                self.send(200, {'csv': raw, 'meta': meta})
            except FileNotFoundError:
                self.send(404, {'error': '尚未下载样本。运行 python download_data.py，或导入自己的 CSV。'})
        else:
            self.send(404, {'error': '页面不存在'})

    def do_POST(self):
        if self.path != '/api/backtest':
            self.send(404, {'error': '接口不存在'})
            return
        # 同源请求；不允许其他网页替用户提交数据。
        origin = self.headers.get('Origin')
        expected = f'http://{self.headers.get("Host")}'
        if origin and origin != expected:
            self.send(403, {'error': '仅允许同源访问'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 4_000_000:
                raise ValueError('请求为空或超过 4 MB')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get('csv'), str) or not isinstance(payload.get('params', {}), dict):
                raise ValueError('请求必须包含 CSV 文本和参数对象')
            rows = parse_csv(payload['csv'])
            result = backtest(rows, payload.get('params', {}))
            result['data_summary'] = {'rows': len(rows), 'start': rows[0]['date'], 'end': rows[-1]['date']}
            result['data_sha256'] = hashlib.sha256(payload['csv'].encode('utf-8')).hexdigest()
            self.send(200, result)
        except (ValueError, TypeError, UnicodeError) as exc:
            self.send(400, {'error': str(exc)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    print(f'Quant Desk: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

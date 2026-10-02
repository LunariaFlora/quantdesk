import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from server import Handler

CSV = 'date,open,high,low,close,volume\n' + '\n'.join(f'2020-01-{i:02d},{i+10},{i+10},{i+10},{i+10},100' for i in range(1, 10))


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, payload, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        return urlopen(Request(self.url + '/api/backtest', json.dumps(payload).encode(), headers), timeout=5)

    def test_import_and_run(self):
        with self.post({'csv': CSV, 'params': {'fast': 1, 'slow': 3}}) as response:
            data = json.load(response)
        self.assertEqual(data['summary']['bars'], 9)
        self.assertEqual(len(data['data_sha256']), 64)
        self.assertEqual(data['summary']['trades'], 1)

    def test_validation_error_is_400(self):
        for payload in [[], {'csv': CSV, 'params': []}, {'csv': 'bad'}, {'csv': CSV, 'params': {'capital': 'Infinity'}}]:
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as error:
                self.post(payload)
            self.assertEqual(error.exception.code, 400)
            self.assertIn('error', json.load(error.exception))

    def test_cross_origin_blocked(self):
        with self.assertRaises(HTTPError) as error:
            self.post({'csv': CSV}, 'https://example.com')
        self.assertEqual(error.exception.code, 403)

    def test_static_and_no_directory_exposure(self):
        with urlopen(self.url) as response:
            self.assertIn('运行回测', response.read().decode())
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + '/engine.py')
        self.assertEqual(error.exception.code, 404)

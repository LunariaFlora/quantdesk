import unittest
from datetime import date, timedelta
from engine import backtest, parse_csv


def bars(prices):
    return [dict(date=(date(2020, 1, 1) + timedelta(days=i)).isoformat(),
                 open=p, high=p, low=p, close=p, volume=10000) for i, p in enumerate(prices)]


class EngineTests(unittest.TestCase):
    def test_next_open_and_hand_calculation(self):
        # 第三天收盘才得到第一条有效信号，第四天以 20 买入；第六天以 8 卖出。
        r = backtest(bars([10, 11, 12, 20, 9, 8]), dict(fast=1, slow=3, capital=100, fee_bps=0, slippage_bps=0))
        self.assertEqual([(t['date'], t['price']) for t in r['trades']], [('2020-01-04', 20), ('2020-01-06', 8)])
        self.assertEqual(r['summary']['equity'], 40)
        self.assertAlmostEqual(r['summary']['max_drawdown_pct'], -60)

    def test_future_does_not_change_past(self):
        p = dict(fast=2, slow=3)
        a = backtest(bars([10, 11, 12, 14, 8, 7, 9]), p)
        b = backtest(bars([10, 11, 12, 14, 8, 700, 900]), p)
        self.assertEqual(a['curve'][:5], b['curve'][:5])

    def test_cost_and_integer_shares(self):
        r = backtest(bars([10, 11, 12, 20]), dict(fast=1, slow=3, capital=100, fee_bps=100, slippage_bps=100))
        t = r['trades'][0]
        self.assertEqual(t['quantity'], 4)
        self.assertAlmostEqual(t['price'], 20.2)
        self.assertAlmostEqual(t['fee'], .808)
        self.assertAlmostEqual(r['summary']['cash'], 18.392)
        self.assertIsNone(r['summary']['win_rate_pct'])

    def test_no_trade(self):
        r = backtest(bars([10] * 10), dict(fast=2, slow=3))
        self.assertEqual(r['summary']['trades'], 0)
        self.assertEqual(r['summary']['return_pct'], 0)

    def test_invalid_parameters(self):
        for p in [dict(fast=30, slow=10), dict(capital='nan'), dict(fast=1.5), dict(start='2030-01-01'), dict(start='oops')]:
            with self.subTest(p=p), self.assertRaises(ValueError):
                backtest(bars([10] * 50), p)

    def test_bad_csv(self):
        for row in ['2020-01-01,10,9,8,10,100', '2020-01-01,nan,10,10,10,100', 'bad,10,10,10,10,100']:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_csv('date,open,high,low,close,volume\n' + row)

    def test_duplicates(self):
        with self.assertRaises(ValueError):
            parse_csv('date,open,high,low,close,volume\n' + '2020-01-01,10,10,10,10,100\n' * 3)

    def test_warmup_and_final_position(self):
        r = backtest(bars(list(range(10, 20))), dict(fast=2, slow=3))
        self.assertEqual(r['summary']['trading_start'], '2020-01-04')
        self.assertTrue(all(x['equity'] == 100000 for x in r['curve'][:3]))
        self.assertGreater(r['summary']['shares'], 0)
        self.assertEqual(r['summary']['closed_trades'], 0)


if __name__ == '__main__':
    unittest.main()

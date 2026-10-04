import tempfile
import unittest
import math
from datetime import date, timedelta
from copy import deepcopy
from quantdesk.backtest import run
from quantdesk.indicators import sma, ema, rsi
from quantdesk.strategies import TEMPLATES, validate
from quantdesk.service import Service, export_result


def bars(prices):
    return [dict(date=(date(2020,1,1)+timedelta(days=i)).isoformat(), open=p, high=p, low=p, close=p, volume=1e7) for i,p in enumerate(prices)]


class ResearchTests(unittest.TestCase):
    def test_indicators(self):
        self.assertEqual(sma([1,2,3,4], 3), [None,None,2,3])
        self.assertEqual(ema([1,2,3,4], 3), [None,None,2,3])
        self.assertEqual(rsi([1,2,3,4], 2)[-1], 100)
        self.assertEqual(rsi([1]*5, 2)[-1], 50)

    def test_accounting_identity_and_causality(self):
        values = list(range(10, 45))+list(range(45, 10, -1))+list(range(10, 45))
        rows = bars(values)
        s = TEMPLATES['sma']
        result = run(rows, s, {})
        for r in result['curve']:
            self.assertAlmostEqual(r['cash']+r['market_value'], r['equity'])
            self.assertAlmostEqual(r['realized_pnl']+r['unrealized_pnl'], r['pnl'])
        changed = deepcopy(rows)
        for row in changed[60:]:
            for k in ('open','high','low','close'):
                row[k] *= 2
        later = run(changed, s, {})
        self.assertEqual(result['curve'][:30], later['curve'][:30])
        self.assertTrue(all(t['signal_date'] < t['date'] for t in result['trades']))

    def test_stop_both_trigger_stop_first(self):
        rows = bars([10]*40)
        rows[30].update(open=10,high=12,low=8,close=10)
        result = run(rows,TEMPLATES['buy_hold'],dict(fee_bps=0,slippage_bps=0,stop_loss_pct=10,take_profit_pct=10))
        sell = next(t for t in result['trades'] if t['side']=='卖出')
        self.assertEqual(sell['price'],9)
        self.assertIn('止损',sell['reason'])
        self.assertAlmostEqual(result['round_trips'][0]['pnl'],-10000)

    def test_gap_stop_and_allocation(self):
        rows=bars([10]*40)
        rows[31].update(open=7,high=8,low=6,close=7)
        result=run(rows,TEMPLATES['buy_hold'],dict(fee_bps=0,slippage_bps=0,allocation_pct=50,stop_loss_pct=10))
        self.assertEqual(result['trades'][0]['quantity'],5000)
        self.assertEqual(result['trades'][1]['price'],7)
        self.assertEqual(result['trades'][1]['realized_pnl'],-15000)

    def test_capacity_and_invalid_strategy(self):
        rows=bars([10]*40)
        for r in rows: r['volume']=1
        result=run(rows,TEMPLATES['buy_hold'],{})
        self.assertEqual(result['trades'],[])
        self.assertTrue(all(o['status']=='rejected' for o in result['orders']))
        with self.assertRaises(ValueError):
            validate({**TEMPLATES['custom'],'entry':[{'left':'rsi','op':'exec','right':30}]})

    def test_metrics_reference(self):
        rows=bars([10]*31+[11]*9)
        result=run(rows,TEMPLATES['buy_hold'],dict(capital=100,fee_bps=0,slippage_bps=0))
        self.assertAlmostEqual(result['summary']['return_pct'],10)
        self.assertAlmostEqual(result['summary']['annualized_return_pct'],(1.1**(365.25/10)-1)*100)
        self.assertEqual(result['summary']['max_drawdown_pct'],0)
        self.assertIsNone(result['summary']['win_rate_pct'])
        self.assertAlmostEqual(result['summary']['equity'],110)

    def test_all_strategies_and_custom(self):
        rows=bars([100+i%20 for i in range(140)])
        for s in TEMPLATES.values():
            with self.subTest(s=s['kind']):
                result=run(rows,s,{})
                self.assertTrue(math.isfinite(result['summary']['equity']))
        with self.assertRaises(InterruptedError):
            run(rows,TEMPLATES['sma'],{},lambda:True)

    def test_grid_common_period_persistence_exports(self):
        rows=bars([100+i%20 for i in range(140)])
        with tempfile.TemporaryDirectory() as home:
            service=Service(home)
            ds=service.store.add_dataset('market','TEST',rows,{})
            results=service.tune(ds,TEMPLATES['sma'],{}, {'fast':[5,10],'slow':[20,40]})
            self.assertEqual(len(results),4)
            self.assertEqual(len({r['summary']['start'] for r in results}),1)
            self.assertEqual(len(service.store.documents('experiment')),4)
            self.assertEqual(service.store.load(results[0]['id'])['body']['summary'],results[0]['summary'])
            export_result(results[0],service.store.home/'export')
            self.assertTrue((service.store.home/'export/report.json').exists())

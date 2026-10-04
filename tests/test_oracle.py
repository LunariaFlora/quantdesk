"""Independent Backtrader broker/indicator oracle on real OHLC history."""
import math
import unittest
from datetime import datetime
from pathlib import Path
try:
    import backtrader as bt
except ImportError:
    bt = None
from quantdesk.data import clean_csv
from quantdesk.backtest import run
from quantdesk.strategies import TEMPLATES


@unittest.skipUnless(bt is not None, 'Install requirements-dev.txt for the independent oracle')
class OracleTests(unittest.TestCase):
    def test_real_data_cash_position_fills_and_daily_equity(self):
        rows,_=clean_csv(Path('data/aapl.csv').read_text(encoding='utf-8-sig'))
        class Feed(bt.feeds.DataBase):
            def start(self):
                super().start()
                self.iterator=iter(rows)
            def _load(self):
                row=next(self.iterator,None)
                if row is None:return False
                self.lines.datetime[0]=bt.date2num(datetime.fromisoformat(row['date']))
                for name in ('open','high','low','close','volume'):getattr(self.lines,name)[0]=row[name]
                return True
        class Strategy(bt.Strategy):
            def __init__(self):
                self.fast=bt.ind.SMA(period=10)
                self.slow=bt.ind.SMA(period=30)
                self.records=[]
                self.fills=[]
            def next_open(self):
                if len(self.data)<=30:return
                if self.fast[0]>self.slow[0] and not self.position:
                    qty=math.floor(self.broker.getcash()*.8/(self.data.open[0]*1.0005))
                    if qty:self.buy(size=qty)
                elif self.fast[0]<=self.slow[0] and self.position:
                    self.close()
            def next(self):
                if len(self.data)>30:
                    self.records.append((self.data.datetime.date(0).isoformat(),self.broker.getvalue(),self.broker.getcash(),self.position.size))
            def notify_order(self,order):
                if order.status==order.Completed:
                    self.fills.append((bt.num2date(order.executed.dt).date().isoformat(),order.executed.price,abs(order.executed.size),order.executed.comm))
        cerebro=bt.Cerebro(cheat_on_open=True,stdstats=False)
        cerebro.broker.setcash(100000)
        cerebro.broker.setcommission(commission=.0005)
        cerebro.adddata(Feed())
        cerebro.addstrategy(Strategy)
        reference=cerebro.run()[0]
        actual=run(rows,TEMPLATES['sma'],{'allocation_pct':80,'fee_bps':5,'slippage_bps':0})
        self.assertEqual(len(reference.records),len(actual['curve']))
        self.assertEqual(len(reference.fills),len(actual['trades']))
        for expected,row in zip(reference.records,actual['curve']):
            self.assertEqual(expected[0],row['date'])
            self.assertAlmostEqual(expected[1],row['equity'],places=6)
            self.assertAlmostEqual(expected[2],row['cash'],places=6)
            self.assertEqual(expected[3],row['shares'])
        for expected,trade in zip(reference.fills,actual['trades']):
            self.assertEqual(expected[0],trade['date'])
            self.assertAlmostEqual(expected[1],trade['price'],places=8)
            self.assertEqual(expected[2],trade['quantity'])
            self.assertAlmostEqual(expected[3],trade['fee'],places=8)


if __name__=='__main__':unittest.main()

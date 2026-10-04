import tempfile
import unittest
from quantdesk.data import clean_csv, to_csv
from quantdesk.storage import Store

SAMPLE = '日期,开盘,最高,最低,收盘,成交量\n2020-01-03,10,11,9,10,100\n2020-01-01,10,11,9,10,100\n2020-01-02,10,11,9,10,100\n'


class LibraryTests(unittest.TestCase):
    def test_explicit_cleaning(self):
        bad = SAMPLE + '2020-01-02,10,11,9,10,100\nbad,NaN,0,0,0,0\n'
        with self.assertRaises(ValueError):
            clean_csv(bad)
        rows, report = clean_csv(bad, drop_invalid=True, duplicates='last')
        self.assertEqual(len(rows), 3)
        self.assertEqual(report['removed'], 2)
        self.assertEqual(report['duplicate_rows'], 1)
        self.assertEqual(rows[0]['date'], '2020-01-01')
        self.assertEqual(clean_csv(to_csv(rows))[0], rows)

    def test_persistence_and_query(self):
        rows, report = clean_csv(SAMPLE)
        with tempfile.TemporaryDirectory() as home:
            store = Store(home)
            ident = store.add_dataset('测试行情', 'abc', rows, {'cleaning': report})
            reopened = Store(home)
            self.assertEqual(len(reopened.datasets('ABC')), 1)
            self.assertEqual(len(reopened.dataset(ident)['metadata']['sha256']), 64)
            self.assertEqual(len(reopened.bars(ident, '2020-01-02', '2020-01-03')), 2)
            strategy = reopened.save('strategy', '策略', {'kind': 'sma'})
            self.assertEqual(reopened.load(strategy)['body']['kind'], 'sma')
            reopened.save('strategy', '新名字', {'kind': 'rsi'}, strategy)
            self.assertEqual(reopened.documents('strategy')[0]['name'], '新名字')
            reopened.log('INFO', '导入成功')
            self.assertEqual(reopened.logs()[0]['message'], '导入成功')
            reopened.delete_dataset(ident)
            with reopened.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM bars').fetchone()[0], 0)

    def test_failed_import_transaction_rolls_back(self):
        rows, _ = clean_csv(SAMPLE)
        with tempfile.TemporaryDirectory() as home:
            store = Store(home)
            with self.assertRaises(Exception):
                store.add_dataset('duplicate', 'ABC', rows+rows[:1], {})
            self.assertEqual(store.datasets(), [])

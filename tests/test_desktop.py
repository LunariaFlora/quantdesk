import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6 import QtWidgets, QtGui, QtCore
from quantdesk.ui import Window
from quantdesk.service import Service


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        font = Path('C:/Windows/Fonts/msyh.ttc')
        if font.exists():
            QtGui.QFontDatabase.addApplicationFont(str(font))

    def test_native_worker_charts_persistence_without_listening_socket(self):
        with tempfile.TemporaryDirectory() as home, patch('socket.socket.bind', side_effect=AssertionError('Desktop must not bind a port')):
            window = Window(Service(home))
            failures = []
            window.error = lambda message, detail='': (failures.append(message), window.finish_job())
            window.show()
            self.app.processEvents()
            self.assertGreater(len(window.service.store.datasets()), 0)
            ident = window.service.store.datasets()[0]['id']
            window.select_dataset(ident)
            callback_threads = []
            def completed(result):
                callback_threads.append(QtCore.QThread.currentThread())
                window.show_result(result)
            window.start_job('test', lambda cancel, progress: window.service.backtest(ident, window.definition(), {}, cancel=cancel), completed)
            deadline = time.monotonic()+20
            ticks = 0
            while window.active_job and time.monotonic() < deadline:
                self.app.processEvents()
                ticks += 1
                time.sleep(.01)
            self.assertIsNone(window.active_job, 'Worker did not finish')
            self.assertFalse(failures, failures)
            self.assertEqual(callback_threads, [self.app.thread()])
            self.assertGreater(ticks, 0)
            self.assertIsNotNone(window.result)
            for name in ['SMA', 'EMA', '布林带', 'MACD', 'RSI', 'ATR']:
                window.charts.indicator.setCurrentText(name)
                self.app.processEvents()
                self.assertGreater(window.charts.price.viewRange()[0][0], 1e9)
            window.service.store.save('strategy', '测试保存', window.definition())
            saved = window.result['id']
            window.close()
            self.app.processEvents()
            reopened = Service(home)
            self.assertEqual(reopened.store.load(saved)['body']['summary'], window.result['summary'])
            self.assertTrue(reopened.store.documents('strategy'))


if __name__ == '__main__':
    unittest.main()

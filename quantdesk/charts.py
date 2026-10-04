"""Native charts, with real OHLC candles, indicators and execution markers."""
from datetime import datetime, timezone
import bisect
import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

pg.setConfigOptions(antialias=True, background='w', foreground='#52667d')
COLORS = ['#2563eb', '#d18a32', '#109887', '#9066c4', '#bd5165', '#5a93a0']


def timestamp(d):
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()


def plot(title):
    widget = pg.PlotWidget(title=title, axisItems={'bottom': pg.DateAxisItem(utcOffset=0)})
    widget.showGrid(x=True, y=True, alpha=.12)
    widget.setMinimumHeight(180)
    widget.addLegend(offset=(10, 8))
    return widget


class Candles(pg.GraphicsObject):
    def __init__(self, rows):
        super().__init__()
        self.picture = QtGui.QPicture()
        painter = QtGui.QPainter(self.picture)
        width = 86400*.28
        self.setToolTip('拖动平移；滚轮缩放；买卖标记位于实际成交价格')
        for row in rows:
            x, o, h, l, c = timestamp(row['date']), row['open'], row['high'], row['low'], row['close']
            color = '#159584' if c >= o else '#c35c69'
            painter.setPen(pg.mkPen(color, width=1))
            painter.setBrush(pg.mkBrush(color))
            painter.drawLine(QtCore.QPointF(x, l), QtCore.QPointF(x, h))
            if c == o:
                painter.drawLine(QtCore.QPointF(x-width, c), QtCore.QPointF(x+width, c))
            else:
                painter.drawRect(QtCore.QRectF(x-width, min(o,c), width*2, abs(c-o)))
        painter.end()

    def paint(self, painter, option, widget):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class Charts(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        controls = QtWidgets.QHBoxLayout()
        self.indicator = QtWidgets.QComboBox()
        self.indicator.addItems(['SMA', 'EMA', '布林带', 'MACD', 'RSI', 'ATR'])
        self.indicator.currentTextChanged.connect(lambda: self.show_result(self.result) if self.result else None)
        controls.addWidget(QtWidgets.QLabel('价格指标'))
        controls.addWidget(self.indicator)
        controls.addStretch()
        self.readout = QtWidgets.QLabel('')
        controls.addWidget(self.readout)
        layout.addLayout(controls)
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.price = plot('行情与成交')
        self.secondary = plot('指标')
        self.equity = plot('账户总资产')
        self.drawdown = plot('回撤 / %')
        for w in (self.price, self.secondary, self.equity, self.drawdown):
            split.addWidget(w)
        self.secondary.setMinimumHeight(110)
        self.drawdown.setMinimumHeight(110)
        self.secondary.setXLink(self.price)
        self.equity.setXLink(self.price)
        self.drawdown.setXLink(self.price)
        split.setSizes([340, 150, 200, 140])
        layout.addWidget(split)
        self.result = None
        self.line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#9aa8b8'))
        self.proxy = pg.SignalProxy(self.price.scene().sigMouseMoved, rateLimit=30, slot=self.hover)

    def hover(self, signal):
        if not self.result or not self.price.sceneBoundingRect().contains(signal[0]):
            return
        x = self.price.plotItem.vb.mapSceneToView(signal[0]).x()
        times = self.times
        i = min(len(times)-1, bisect.bisect_left(times, x))
        row = self.result['curve'][i]
        self.line.setPos(times[i])
        self.readout.setText(f'{row["date"]}  O {row["open"]:.2f}  H {row["high"]:.2f}  L {row["low"]:.2f}  C {row["close"]:.2f}  资产 {row["equity"]:,.2f}')

    def show_result(self, result):
        self.result = result
        rows = result['curve']
        self.times = [timestamp(r['date']) for r in rows]
        for chart in (self.price, self.secondary, self.equity, self.drawdown):
            chart.clear()
            chart.plotItem.legend.clear()
        self.price.addItem(Candles(rows))
        self.line.setPos(self.times[0])
        self.price.addItem(self.line, ignoreBounds=True)
        chosen = self.indicator.currentText()
        overlays = {'SMA':['sma_fast','sma_slow'], 'EMA':['ema_fast','ema_slow'], '布林带':['bb_upper','sma_slow','bb_lower']}.get(chosen, [])
        for j, key in enumerate(overlays):
            self.price.plot(self.times, [r[key] if r[key] is not None else np.nan for r in rows], pen=pg.mkPen(COLORS[j],width=1.5), name=key)
        keys = {'MACD':['macd','macd_signal'], 'RSI':['rsi'], 'ATR':['atr']}.get(chosen, ['rsi'])
        self.secondary.setTitle(' / '.join(keys))
        for j, key in enumerate(keys):
            self.secondary.plot(self.times, [r[key] if r[key] is not None else np.nan for r in rows], pen=pg.mkPen(COLORS[j],width=1.5), name=key)
        for side, shape, color in [('买入','t1','#2563eb'),('卖出','t','#d18a32')]:
            trades = [t for t in result['trades'] if t['side']==side]
            self.price.addItem(pg.ScatterPlotItem([timestamp(t['date']) for t in trades], [t['price'] for t in trades], symbol=shape, size=11, brush=color, pen='w', name=side))
        self.equity.plot(self.times,[r['equity'] for r in rows],pen=pg.mkPen(COLORS[0],width=2),name='策略资产')
        self.equity.plot(self.times,[r['benchmark'] for r in rows],pen=pg.mkPen('#94a3b8',style=QtCore.Qt.PenStyle.DashLine),name='买入持有')
        self.drawdown.plot(self.times,[r['drawdown'] for r in rows],pen=pg.mkPen('#c35c69'),fillLevel=0,brush=(195,92,105,30),name='回撤')
        self.price.enableAutoRange()
        self.readout.setText(f'{len(rows)} 根日线 · 滚轮缩放 / 拖动平移')

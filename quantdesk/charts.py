"""Native charts, with real OHLC candles, indicators and execution markers."""
from datetime import datetime, timezone
import bisect
import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

pg.setConfigOptions(antialias=True, background='#172131', foreground='#a0afc4')
LIGHT_COLORS = ['#2158ba', '#955a00', '#08745a', '#7840ad', '#b62f44', '#087985']
COLORS = ['#7da6ff', '#f1ba65', '#50d2aa', '#b59af6', '#ff8793', '#69cadd']


def timestamp(d):
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()


def plot(title):
    widget = pg.PlotWidget(title=title, axisItems={'bottom': pg.DateAxisItem(utcOffset=0)})
    widget.showGrid(x=True, y=True, alpha=.12)
    widget.setMinimumHeight(100)
    widget.addLegend(offset=(10, 8), labelTextColor='#e3ebf7', brush=pg.mkBrush(23,33,49,215), pen=None)
    widget.setMenuEnabled(False)
    widget.getAxis('left').setWidth(68)
    return widget


class Candles(pg.GraphicsObject):
    def __init__(self, rows, colors=None):
        super().__init__()
        self.picture = QtGui.QPicture()
        painter = QtGui.QPainter(self.picture)
        width = 86400*.28
        self.setToolTip('拖动平移；滚轮缩放；买卖标记位于实际成交价格')
        for row in rows:
            x, o, h, l, c = timestamp(row['date']), row['open'], row['high'], row['low'], row['close']
            color = (colors or {'positive':'#50b99d','negative':'#e67785'})['positive' if c >= o else 'negative']
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
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(6)
        controls = QtWidgets.QHBoxLayout()
        self.indicator = QtWidgets.QComboBox()
        self.indicator.addItems(['SMA', 'EMA', '布林带', 'MACD', 'RSI', 'ATR'])
        self.indicator.currentTextChanged.connect(lambda: self.show_result(self.result) if self.result else None)
        controls.addWidget(QtWidgets.QLabel('价格指标'))
        controls.addWidget(self.indicator)
        reset=QtWidgets.QPushButton('重置视图')
        reset.clicked.connect(self.reset_view)
        controls.addWidget(reset)
        controls.addStretch()
        self.readout = QtWidgets.QLabel('')
        controls.addWidget(self.readout)
        layout.addLayout(controls)
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.split=split
        self.price = plot('行情与成交')
        self.price.plotItem.legend.setColumnCount(4)
        self.price.hideAxis('bottom')
        self.secondary = plot('指标')
        self.equity = plot('账户总资产')
        self.equity.plotItem.legend.setColumnCount(2)
        self.drawdown = plot('回撤 / %')
        split.addWidget(self.price)
        split.addWidget(self.secondary)
        bottom=QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        bottom.addWidget(self.equity)
        bottom.addWidget(self.drawdown)
        split.addWidget(bottom)
        # Total minimum must fit the chart area at the 1060×680 window minimum.
        # QSplitter otherwise assigns less than a child's minimum and it overlaps.
        self.price.setMinimumHeight(120)
        self.secondary.setMinimumHeight(80)
        bottom.setMinimumHeight(115)
        self.secondary.setXLink(self.price)
        # XLink follows screen geometry; half-width plots need exact date-domain sync.
        self.syncing_range = False
        for chart in (self.price, self.equity, self.drawdown):
            chart.getViewBox().sigXRangeChanged.connect(self.sync_range)
        split.setSizes([300, 85, 160])
        layout.addWidget(split)
        self.result = None
        self.line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#9aa8b8'))
        self.proxy = pg.SignalProxy(self.price.scene().sigMouseMoved, rateLimit=30, slot=self.hover)

    def sync_range(self, source, bounds):
        if self.syncing_range:return
        self.syncing_range=True
        try:
            for chart in (self.price,self.equity,self.drawdown):
                if chart.getViewBox() is not source:chart.setXRange(*bounds,padding=0)
        finally:self.syncing_range=False

    def reset_view(self):
        for chart in (self.price,self.secondary,self.equity,self.drawdown):
            chart.enableAutoRange(axis='y')
        if self.result:
            self.price.setXRange(self.times[0],self.times[-1],padding=.02)

    def focus_date(self,day):
        if not self.result:return
        x=timestamp(day)
        self.price.setXRange(x-86400*30,x+86400*30,padding=0)
        self.hover_date(day)

    def hover_date(self,day):
        i=min(len(self.times)-1,bisect.bisect_left(self.times,timestamp(day)))
        row=self.result['curve'][i]
        self.line.setPos(self.times[i])
        self.readout.setText(f"{row['date']}  收盘 {row['close']:.2f}  资产 {row['equity']:,.2f}")

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
        preserve=self.result is result
        prior=self.price.viewRange()[0] if preserve else None
        self.result = result
        rows = result['curve']
        self.times = [timestamp(r['date']) for r in rows]
        for chart in (self.price, self.secondary, self.equity, self.drawdown):
            chart.clear()
            chart.plotItem.legend.clear()
        palette=getattr(self,'theme_colors',None)
        colors=LIGHT_COLORS if palette and palette['panel']=='#ffffff' else COLORS
        self.price.addItem(Candles(rows,palette))
        self.line.setPos(self.times[0])
        self.price.addItem(self.line, ignoreBounds=True)
        chosen = self.indicator.currentText()
        overlays = {'SMA':['sma_fast','sma_slow'], 'EMA':['ema_fast','ema_slow'], '布林带':['bb_upper','sma_slow','bb_lower']}.get(chosen, [])
        for j, key in enumerate(overlays):
            self.price.plot(self.times, [r[key] if r[key] is not None else np.nan for r in rows], pen=pg.mkPen(colors[j],width=1.5), name={'sma_fast':'短均线','sma_slow':'长均线','ema_fast':'短 EMA','ema_slow':'长 EMA','bb_upper':'布林上轨','bb_lower':'布林下轨'}.get(key,key))
        keys = {'MACD':['macd','macd_signal'], 'RSI':['rsi'], 'ATR':['atr']}.get(chosen, [])
        self.secondary.setTitle(' / '.join(keys) if keys else '成交量',color=self.theme_colors['muted'] if hasattr(self,'theme_colors') else '#a0afc4')
        if not keys:
            self.secondary.addItem(pg.BarGraphItem(x=self.times,height=[r['volume'] for r in rows],width=86400*.65,brush=pg.mkBrush('#58749a'),pen=None))
        for j, key in enumerate(keys):
            self.secondary.plot(self.times, [r[key] if r[key] is not None else np.nan for r in rows], pen=pg.mkPen(colors[j],width=1.5), name={'sma_fast':'短均线','sma_slow':'长均线','ema_fast':'短 EMA','ema_slow':'长 EMA','bb_upper':'布林上轨','bb_lower':'布林下轨'}.get(key,key))
        for side, shape, color in [('买入','t1',colors[0]),('卖出','t',colors[1])]:
            trades = [t for t in result['trades'] if t['side']==side]
            self.price.addItem(pg.ScatterPlotItem([timestamp(t['date']) for t in trades], [t['price'] for t in trades], symbol=shape, size=11, brush=color, pen='w', name=side))
        self.equity.plot(self.times,[r['equity'] for r in rows],pen=pg.mkPen(colors[0],width=2),name='策略资产')
        self.equity.plot(self.times,[r['benchmark'] for r in rows],pen=pg.mkPen('#94a3b8',style=QtCore.Qt.PenStyle.DashLine),name='买入持有')
        self.drawdown.plot(self.times,[r['drawdown'] for r in rows],pen=pg.mkPen(palette['negative'] if palette else '#e67785'),fillLevel=0,brush=pg.mkBrush(182,47,68,30),name='回撤')
        if prior:self.price.setXRange(*prior,padding=0)
        else:self.reset_view()
        self.readout.setText(f'{len(rows)} 根日线 · 滚轮缩放 / 拖动平移')

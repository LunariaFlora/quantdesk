"""Market context before a backtest: actual prices, never synthetic performance."""
import bisect
import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets as W
from .charts import plot, Candles, timestamp, COLORS, LIGHT_COLORS
from .theme import DARK


class MarketPreview(W.QWidget):
    def __init__(self):
        super().__init__()
        self.rows=[]
        self.dataset=None
        self.colors=DARK
        layout=W.QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(6)
        self.context=W.QLabel('选择数据集查看历史行情')
        self.context.setProperty('muted',True)
        self.context.setWordWrap(True)
        layout.addWidget(self.context)
        cards=W.QHBoxLayout()
        self.metrics={}
        for key,title in [('close','最新历史收盘'),('change','当日涨跌 / %'),('range','可见区间涨跌 / %'),('volume','当日成交量')]:
            cell=W.QWidget();cell.setProperty('panel',True)
            column=W.QVBoxLayout(cell);column.setContentsMargins(8,6,8,6);column.setSpacing(2)
            label=W.QLabel(title);label.setProperty('muted',True);column.addWidget(label)
            value=W.QLabel('—');value.setStyleSheet('font-family:Consolas;font-size:18px;')
            column.addWidget(value);self.metrics[key]=value;cards.addWidget(cell,1)
        layout.addLayout(cards)
        controls=W.QHBoxLayout()
        self.scope=W.QComboBox()
        for text,bars in [('近一年',252),('近半年',126),('近三个月',63),('全部数据',0)]:self.scope.addItem(text,bars)
        self.scope.currentIndexChanged.connect(self.render)
        controls.addWidget(self.scope)
        reset=W.QPushButton('重置视图');reset.clicked.connect(self.render);controls.addWidget(reset)
        controls.addStretch()
        self.readout=W.QLabel('');self.readout.setProperty('muted',True)
        self.readout.setSizePolicy(W.QSizePolicy.Policy.Ignored,W.QSizePolicy.Policy.Preferred)
        controls.addWidget(self.readout)
        layout.addLayout(controls)
        split=W.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.price=plot('历史价格 · MA20 / MA60')
        self.price.setMinimumHeight(120)
        self.price.hideAxis('bottom')
        self.price.plotItem.legend.setColumnCount(2)
        self.volume=plot('成交量')
        self.volume.setMinimumHeight(80)
        self.volume.getAxis('left').setTickDensity(.4)
        self.volume.setXLink(self.price)
        split.addWidget(self.price);split.addWidget(self.volume)
        split.setSizes([320,100]);split.setStretchFactor(0,3);split.setStretchFactor(1,1)
        layout.addWidget(split,1)
        self.proxy=pg.SignalProxy(self.price.scene().sigMouseMoved,rateLimit=25,slot=self.hover)

    def show_dataset(self,dataset,rows,colors=None):
        self.dataset=dataset;self.rows=rows
        if colors:self.colors=colors
        self.render()

    def clear(self):
        self.dataset=None;self.rows=[];self.render()

    def render(self,*args):
        for chart in (self.price,self.volume):
            chart.clear();chart.plotItem.legend.clear()
            chart.setBackground(self.colors['panel'])
            chart.plotItem.legend.setLabelTextColor(self.colors['text'])
            chart.plotItem.legend.setBrush(pg.mkBrush(self.colors['panel']))
        if not self.rows:
            self.context.setText('没有该区间的行情，请选择其他数据或日期')
            self.readout.clear()
            for label in self.metrics.values():label.setText('—')
            return
        count=self.scope.currentData()
        visible=self.rows[-count:] if count else self.rows
        self.visible_rows=visible
        latest=self.rows[-1]
        previous=self.rows[-2]['close'] if len(self.rows)>1 else latest['close']
        values={'close':latest['close'],'change':(latest['close']/previous-1)*100,
                'range':(visible[-1]['close']/visible[0]['close']-1)*100,'volume':latest['volume']}
        for key,value in values.items():
            text=f'{value/1e8:.2f} 亿' if key=='volume' and value>=1e8 else f'{value/1e4:.2f} 万' if key=='volume' and value>=1e4 else f'{value:,.2f}'
            label=self.metrics[key];label.setText(text)
            color=self.colors['positive' if value>=0 else 'negative'] if key in ('change','range') else self.colors['text']
            label.setStyleSheet(f'font-family:Consolas;font-size:18px;color:{color};')
        meta=self.dataset['metadata']
        self.context.setText(f"{self.dataset['symbol']} · 历史行情截至 {latest['date']} · {meta.get('provider','CSV')} · {len(self.rows):,} 根日线")
        self.price.addItem(Candles(visible,self.colors))
        self.times=[timestamp(r['date']) for r in visible]
        closes=np.asarray([r['close'] for r in self.rows])
        colors=LIGHT_COLORS if self.colors['panel']=='#ffffff' else COLORS
        for i,period in enumerate((20,60)):
            if len(closes)>=period:
                averages=np.concatenate((np.full(period-1,np.nan),np.convolve(closes,np.ones(period)/period,mode='valid')))
                self.price.plot(self.times,averages[-len(visible):],pen=pg.mkPen(colors[i],width=1.6),name=f'MA{period}')
        self.volume.addItem(pg.BarGraphItem(x=self.times,height=[r['volume'] for r in visible],width=86400*.7,brush=pg.mkBrush(colors[0]),pen=None))
        self.price.enableAutoRange(axis='y');self.volume.enableAutoRange(axis='y')
        if len(self.times)>1:self.price.setXRange(self.times[0],self.times[-1],padding=.02)
        self.readout.setText(f"{visible[0]['date']} — {visible[-1]['date']}")

    def hover(self,signal):
        if not self.rows or not self.price.sceneBoundingRect().contains(signal[0]):return
        x=self.price.plotItem.vb.mapSceneToView(signal[0]).x()
        i=min(len(self.times)-1,bisect.bisect_left(self.times,x))
        row=self.visible_rows[i]
        self.readout.setText(f"{row['date']}  O {row['open']:.2f}  H {row['high']:.2f}  L {row['low']:.2f}  C {row['close']:.2f}")

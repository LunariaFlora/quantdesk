"""Ordinary strategy inputs with an advanced JSON editor sharing one definition."""
import json
from PySide6 import QtCore, QtGui, QtWidgets as W
from .strategies import TEMPLATES


class StrategyForm(W.QTabWidget):
    changed=QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.syncing=False
        self.fields={}
        self.labels={}
        page=W.QWidget()
        layout=W.QVBoxLayout(page)
        layout.setContentsMargins(16,16,16,16)
        self.description=W.QLabel()
        self.description.setWordWrap(True)
        self.description.setProperty('muted',True)
        layout.addWidget(self.description)
        group=W.QGroupBox('策略参数')
        group.setMaximumWidth(620)
        form=W.QFormLayout(group)
        form.setVerticalSpacing(12)
        for key,label in [('name','名称'),('fast','短周期 / 日'),('slow','长周期 / 日'),('period','指标周期 / 日'),('band','标准差倍数'),('oversold','买入 RSI 阈值'),('overbought','卖出 RSI 阈值')]:
            field=W.QLineEdit()
            field.setObjectName('strategy_'+key)
            self.fields[key]=field
            self.labels[key]=W.QLabel(label)
            form.addRow(self.labels[key],field)
            field.textChanged.connect(self.to_json)
        layout.addWidget(group)
        self.custom_hint=W.QLabel('自定义条件在“规则 JSON”中设置；同组条件全部满足时触发。')
        self.custom_hint.setWordWrap(True)
        layout.addWidget(self.custom_hint)
        self.preview=W.QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        layout.addStretch()
        self.addTab(page,'参数')
        advanced=W.QWidget()
        column=W.QVBoxLayout(advanced)
        self.editor=W.QPlainTextEdit()
        self.editor.setFont(QtGui.QFont('Consolas',11))
        self.editor.textChanged.connect(self.from_json)
        column.addWidget(self.editor,1)
        helptext=W.QLabel('指标：close、sma_fast/slow、ema_fast/slow、rsi、bb_upper/lower、macd、macd_signal、atr、high_channel、low_channel。\n比较：>、<、>=、<=、cross_above、cross_below；right 可为数值或指标。')
        helptext.setWordWrap(True)
        helptext.setProperty('muted',True)
        column.addWidget(helptext)
        self.addTab(advanced,'规则 JSON')
        self.editor.setPlainText(json.dumps(TEMPLATES['sma'],ensure_ascii=False,indent=2))

    def from_json(self):
        if self.syncing:return
        try:
            raw=json.loads(self.editor.toPlainText())
            if not isinstance(raw,dict) or raw.get('kind') not in TEMPLATES:
                self.changed.emit()
                return
            definition={**TEMPLATES[raw['kind']],**raw}
        except (ValueError,TypeError):
            self.changed.emit()
            return
        self.syncing=True
        kind=raw['kind']
        relevant={'name','fast','slow'}
        if kind in ('rsi','custom'):relevant|={'period','oversold','overbought'}
        if kind=='bollinger':relevant.add('band')
        if kind=='buy_hold':relevant={'name'}
        for key,field in self.fields.items():
            field.setText(str(definition.get(key,{'period':14,'band':2,'oversold':30,'overbought':70}.get(key,''))))
            field.setVisible(key in relevant)
            self.labels[key].setVisible(key in relevant)
        descriptions={'sma':'收盘短均线高于长均线时持仓，下一日开盘执行。','ema':'使用指数移动平均判断趋势，下一日开盘执行。','rsi':'低于买入阈值进入，高于卖出阈值退出。','bollinger':'收盘跌破下轨买入，回到均线退出。','breakout':'突破历史高点进入，跌破通道低点退出。','macd':'MACD 高于信号线时持仓。','buy_hold':'交易起点买入，期末按收盘估值。','custom':'用指标比较或交叉条件定义进入和退出规则。'}
        self.description.setText(descriptions[kind])
        self.custom_hint.setVisible(kind=='custom')
        self.preview.setText(f"{definition['name']}  ·  {TEMPLATES[kind]['name']}")
        self.syncing=False
        self.changed.emit()

    def to_json(self):
        if self.syncing:return
        try:raw=json.loads(self.editor.toPlainText())
        except ValueError:return
        for key,field in self.fields.items():
            if field.isHidden():continue
            value=field.text()
            if key!='name':
                try:
                    number=float(value)
                    value=int(number) if number.is_integer() else number
                except ValueError:pass
            raw[key]=value
        self.syncing=True
        self.editor.setPlainText(json.dumps(raw,ensure_ascii=False,indent=2))
        self.syncing=False
        self.changed.emit()

"""Native Qt application. No server, web view or local listening port."""
import json
import sys
import threading
import traceback
from pathlib import Path
from functools import partial
from PySide6 import QtCore, QtGui, QtWidgets as W
import pyqtgraph as pg
from .service import Service, export_result
from .strategies import TEMPLATES, validate
from .backtest import config
from .data import to_csv
from .charts import Charts, plot, timestamp, COLORS, Candles

LABELS = {'date':'日期','open':'开盘','high':'最高','low':'最低','close':'收盘','volume':'成交量',
          'return_pct':'累计收益 %','annualized_return_pct':'年化收益 %','max_drawdown_pct':'最大回撤 %','sharpe':'夏普',
          'win_rate_pct':'胜率 %','profit_loss_ratio':'盈亏比','profit_factor':'盈利因子','trade_frequency_year':'成交频率 / 年',
          'equity':'资产','cash':'现金','shares':'持仓数量','pnl':'总盈亏','realized_pnl':'已实现盈亏','unrealized_pnl':'未实现盈亏',
          'fees':'手续费','trades':'成交笔数','start':'交易开始','end':'交易结束','side':'方向','price':'成交价','quantity':'数量',
          'fee':'手续费','signal_date':'信号日期','status':'状态','reason':'原因','entry_date':'买入日期','exit_date':'卖出日期',
          'entry_price':'买入价','exit_price':'卖出价','market_value':'市值','drawdown':'回撤 %','name':'名称',
          'symbol':'代码','provider':'来源','rows':'日线数','updated_at':'保存时间','level':'级别','message':'信息',
          'detail':'详情','created_at':'时间','fast':'短周期','slow':'长周期','period':'RSI/ATR 周期','band':'布林倍数',
          'oversold':'RSI 买入阈值','overbought':'RSI 卖出阈值','id':'编号','closed_trades':'已平仓次数',
          'exposure_pct':'持仓时间 %','volatility_pct':'年化波动 %','bars':'交易日线数'}


def formatted(value):
    if value is None:
        return '—'
    if isinstance(value,float):
        return f'{value:,.4f}' if abs(value)<10 else f'{value:,.2f}'
    return str(value)


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, rows, keys):
        super().__init__()
        self.rows, self.keys = rows, keys

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.keys)

    def data(self,index,role=QtCore.Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return formatted(self.rows[index.row()].get(self.keys[index.column()]))
        if index.isValid() and role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)

    def headerData(self,section,orientation,role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return LABELS.get(self.keys[section],self.keys[section]) if orientation == QtCore.Qt.Orientation.Horizontal else str(section+1)


def table():
    t=W.QTableView()
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(W.QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setDefaultSectionSize(29)
    return t


def populate(widget,rows,keys):
    widget.setModel(TableModel(rows,keys))
    for i in range(len(keys)):
        widget.setColumnWidth(i,145 if keys[i] in ('name','created_at','updated_at','reason') else 112)


class Signals(QtCore.QObject):
    done=QtCore.Signal(object)
    failed=QtCore.Signal(str,str)
    progress=QtCore.Signal(int,int)


class Job(QtCore.QRunnable):
    def __init__(self,function):
        super().__init__()
        self.function=function
        self.signals=Signals()
        self.cancel=threading.Event()

    def run(self):
        try:
            result=self.function(self.cancel.is_set,self.signals.progress.emit)
            self.signals.done.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc),traceback.format_exc())


STYLE='''
QWidget {font-family:"Microsoft YaHei";font-size:12px;color:#243b53;}
QMainWindow,QStackedWidget {background:#f4f7fb;}
QGroupBox {background:white;border:1px solid #dbe4ee;border-radius:7px;margin-top:12px;padding:15px;}
QGroupBox::title {subcontrol-origin:margin;left:12px;padding:0 5px;color:#536e87;}
QPushButton {background:white;border:1px solid #cdd9e5;border-radius:5px;padding:8px 13px;min-height:18px;}
QPushButton:hover {background:#edf4fc;}
QPushButton:disabled {color:#a0aec0;}
QPushButton[primary="true"] {background:#2563eb;color:white;border:0;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit {background:white;border:1px solid #cdd9e5;border-radius:4px;padding:6px;selection-background-color:#2563eb;}
QTableView {background:white;alternate-background-color:#f8fafc;border:1px solid #dbe4ee;gridline-color:#edf2f7;selection-background-color:#dceaff;selection-color:#173c66;}
QHeaderView::section {background:#f0f5fa;padding:8px;border:0;border-bottom:1px solid #dbe4ee;}
QTabWidget::pane {border:1px solid #dbe4ee;background:white;}
QTabBar::tab {padding:9px 16px;background:#eef3f8;}
QTabBar::tab:selected {background:white;color:#2563eb;}
QListWidget {background:#152d45;border:0;color:#d8e5f1;outline:0;padding:10px;}
QListWidget::item {padding:14px 12px;border-radius:5px;}
QListWidget::item:selected {background:#2563eb;color:white;}
QLabel[metric="true"] {font-size:23px;font-weight:600;color:#2563eb;}
QLabel[title="true"] {font-size:23px;font-weight:600;}
QStatusBar {background:white;border-top:1px solid #dbe4ee;}
'''


class Window(W.QMainWindow):
    def __init__(self,service=None):
        super().__init__()
        self.service=service or Service()
        self.setWindowTitle('观澜 · 量化研究工作台')
        self.resize(1500,1000)
        self.setMinimumSize(1060,760)
        self.setStyleSheet(STYLE)
        self.result=None
        self.active_job=None
        self.job_refs=[]
        self.saved_strategy_id=None
        self.saved_config_id=None
        central=W.QWidget()
        layout=W.QHBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        self.nav=W.QListWidget()
        self.nav.addItems(['观澜  QUANT DESK','行情数据','策略管理','回测研究','实验与比较','任务日志'])
        self.nav.item(0).setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.nav.setFixedWidth(176)
        self.pages=W.QStackedWidget()
        layout.addWidget(self.nav)
        layout.addWidget(self.pages)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(lambda i:self.pages.setCurrentIndex(max(0,i-1)))
        self.status=W.QLabel('就绪')
        self.statusBar().addWidget(self.status,1)
        self.progress=W.QProgressBar()
        self.progress.setMaximumWidth(190)
        self.progress.hide()
        self.cancel_button=W.QPushButton('取消任务')
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.cancel_task)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().addPermanentWidget(self.cancel_button)
        self.build_data()
        self.build_strategies()
        self.build_backtest()
        self.build_experiments()
        self.build_logs()
        self.seed_sample()
        self.refresh()
        self.nav.setCurrentRow(1)

    def page(self,title,subtitle):
        p=W.QWidget()
        layout=W.QVBoxLayout(p)
        layout.setContentsMargins(24,20,24,18)
        heading=W.QLabel(title)
        heading.setProperty('title',True)
        layout.addWidget(heading)
        label=W.QLabel(subtitle)
        label.setWordWrap(True)
        label.setStyleSheet('color:#688097;margin-bottom:10px;')
        layout.addWidget(label)
        self.pages.addWidget(p)
        return layout

    def button(self,text,fn,primary=False):
        b=W.QPushButton(text)
        b.setProperty('primary',primary)
        b.clicked.connect(lambda: self.guard(fn))
        return b

    def guard(self,fn):
        try:
            return fn()
        except Exception as exc:
            self.error(str(exc),traceback.format_exc())

    def error(self,message,detail=''):
        self.service.store.log('ERROR',message,detail)
        self.status.setText('失败：'+message)
        self.status.setStyleSheet('color:#b94052;')
        self.finish_job()
        self.refresh_logs()
        dialog=W.QMessageBox(self)
        dialog.setIcon(W.QMessageBox.Icon.Warning)
        dialog.setWindowTitle('操作未完成')
        dialog.setText(message)
        dialog.setDetailedText(detail)
        dialog.exec()

    def start_job(self,label,fn,done):
        if self.active_job:
            raise ValueError('已有任务正在运行，请等待或取消')
        job=Job(fn)
        self.active_job=job
        self.job_refs.append(job)
        self.progress.setRange(0,0)
        self.progress.show()
        self.cancel_button.show()
        self.status.setStyleSheet('')
        self.status.setText(label)
        job.signals.failed.connect(self.error,QtCore.Qt.ConnectionType.QueuedConnection)
        job.signals.progress.connect(self.task_progress,QtCore.Qt.ConnectionType.QueuedConnection)
        job.signals.done.connect(partial(self.job_done,done),QtCore.Qt.ConnectionType.QueuedConnection)
        QtCore.QThreadPool.globalInstance().start(job)

    def task_progress(self,value,total):
        self.progress.setRange(0,total)
        self.progress.setValue(value)
        self.status.setText(f'参数研究：{value}/{total}')

    def job_done(self,callback,value):
        self.finish_job()
        self.refresh()
        try:
            callback(value)
        except Exception as exc:
            self.error(str(exc),traceback.format_exc())
        else:
            self.status.setText('已完成并保存')

    def finish_job(self):
        if self.active_job in self.job_refs:
            self.job_refs.remove(self.active_job)
        self.active_job=None
        self.progress.hide()
        self.cancel_button.hide()

    def cancel_task(self):
        if self.active_job:
            self.active_job.cancel.set()
            self.status.setText('正在取消；网络请求会在超时或返回后结束')

    def closeEvent(self,event):
        if self.active_job:
            self.active_job.cancel.set()
            self.status.setText('等待当前任务结束后再关闭')
            event.ignore()
        else:
            event.accept()

    def seed_sample(self):
        if self.service.store.datasets():
            return
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        sample=root/'data/aapl.csv'
        if sample.exists():
            self.service.import_csv(sample,'AAPL 历史样本','AAPL')

    def build_data(self):
        layout=self.page('行情数据','获取或导入日线行情，查询存储记录和清洗报告。数据在本机持久保存。')
        bar=W.QHBoxLayout()
        self.provider=W.QComboBox()
        for label,key in [('Yahoo 日线','yahoo'),('Stooq 日线','stooq'),('公开 AAPL 固定样本','plotly')]: self.provider.addItem(label,key)
        self.symbol=W.QLineEdit('AAPL')
        self.symbol.setMaximumWidth(130)
        self.fetch_start=W.QLineEdit('2020-01-01')
        self.fetch_end=W.QLineEdit('2025-12-31')
        for w in [self.provider,self.symbol,self.fetch_start,self.fetch_end]: bar.addWidget(w)
        bar.addWidget(self.button('获取行情',self.fetch_data,True))
        bar.addWidget(self.button('导入 CSV',self.import_data))
        layout.addLayout(bar)
        clean=W.QHBoxLayout()
        self.drop_invalid=W.QCheckBox('清洗：删除无效行')
        self.duplicates=W.QComboBox()
        self.duplicates.addItems(['重复日期报错','重复日期保留第一行','重复日期保留最后一行'])
        self.search=W.QLineEdit()
        self.search.setPlaceholderText('查询数据集名称 / 股票代码')
        self.search.textChanged.connect(self.refresh_datasets)
        clean.addWidget(self.drop_invalid)
        clean.addWidget(self.duplicates)
        clean.addWidget(self.search,1)
        clean.addWidget(self.button('导出当前数据',self.export_data))
        clean.addWidget(self.button('删除数据集',self.delete_data))
        layout.addLayout(clean)
        split=W.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.datasets_table=table()
        self.datasets_table.clicked.connect(self.load_data_selection)
        split.addWidget(self.datasets_table)
        self.data_meta=W.QPlainTextEdit()
        self.data_meta.setReadOnly(True)
        self.data_meta.setMaximumHeight(120)
        split.addWidget(self.data_meta)
        tabs=W.QTabWidget()
        self.data_table=table()
        tabs.addTab(self.data_table,'行情明细')
        self.data_chart=plot('日线 OHLC')
        tabs.addTab(self.data_chart,'K线预览')
        split.addWidget(tabs)
        split.setSizes([160,100,500])
        layout.addWidget(split,1)
        query=W.QHBoxLayout()
        self.query_start=W.QLineEdit()
        self.query_start.setPlaceholderText('查询开始 YYYY-MM-DD（空为全部）')
        self.query_end=W.QLineEdit()
        self.query_end.setPlaceholderText('查询结束 YYYY-MM-DD（空为全部）')
        query.addWidget(self.query_start)
        query.addWidget(self.query_end)
        query.addWidget(self.button('查询区间',self.load_data_selection))
        layout.addLayout(query)

    def current_dataset(self):
        ids=self.datasets_table.selectionModel().selectedRows() if self.datasets_table.model() else []
        if not ids:
            raise ValueError('请先选择一个数据集')
        return self.datasets_table.model().rows[ids[0].row()]['id']

    def refresh_datasets(self):
        selected=self.datasets_table.selectionModel().selectedRows() if self.datasets_table.model() else []
        ident=self.datasets_table.model().rows[selected[0].row()]['id'] if selected else None
        records=self.service.store.datasets(self.search.text())
        flat=[{**r,**r['metadata'],'provider':r['metadata'].get('provider','csv')} for r in records]
        populate(self.datasets_table,flat,['name','symbol','provider','rows','start','end'])
        for i,row in enumerate(flat):
            if row['id']==ident:self.datasets_table.selectRow(i)

    def load_data_selection(self,*args):
        def load():
            ident=self.current_dataset()
            ds=self.service.store.dataset(ident)
            start=self.query_start.text().strip()
            end=self.query_end.text().strip()
            if start or end: config({'start':start,'end':end})
            rows=self.service.store.bars(ident,start,end or '9999-12-31')
            populate(self.data_table,rows,['date','open','high','low','close','volume'])
            self.data_meta.setPlainText(json.dumps(ds['metadata'],ensure_ascii=False,indent=2))
            self.data_chart.clear()
            # Preview cost is bounded; full records remain queryable/exportable.
            if rows: self.data_chart.addItem(Candles(rows[-5000:]))
            self.data_chart.enableAutoRange()
            self.status.setText(f'查询 {len(rows)} 根日线；K线预览显示最近最多 5,000 根')
        self.guard(load)

    def fetch_data(self):
        provider,symbol,start,end=self.provider.currentData(),self.symbol.text(),self.fetch_start.text(),self.fetch_end.text()
        self.start_job('正在获取历史行情…',lambda cancel,progress:self.service.fetch(provider,symbol,start,end),self.select_dataset)

    def import_data(self):
        path,_=W.QFileDialog.getOpenFileName(self,'导入历史日线','','CSV (*.csv);;所有文件 (*)')
        if not path:return
        policy=['error','first','last'][self.duplicates.currentIndex()]
        invalid=self.drop_invalid.isChecked()
        symbol=self.symbol.text() or 'CUSTOM'
        self.start_job('正在导入并校验…',lambda cancel,progress:self.service.import_csv(path,symbol=symbol,drop_invalid=invalid,duplicates=policy),self.select_dataset)

    def select_dataset(self,ident):
        self.refresh_datasets()
        for i,row in enumerate(self.datasets_table.model().rows):
            if row['id']==ident:
                self.datasets_table.selectRow(i)
                self.load_data_selection()
                break

    def export_data(self):
        rows=self.service.store.bars(self.current_dataset(),self.query_start.text().strip(),self.query_end.text().strip() or '9999-12-31')
        path,_=W.QFileDialog.getSaveFileName(self,'导出行情','market.csv','CSV (*.csv)')
        if path: Path(path).write_text('\ufeff'+to_csv(rows),encoding='utf-8')

    def delete_data(self):
        ident=self.current_dataset()
        if W.QMessageBox.question(self,'删除数据集','删除选中的行情数据？已保存的实验结果仍保留。')==W.QMessageBox.StandardButton.Yes:
            self.service.store.delete_dataset(ident)
            self.refresh()

    def build_strategies(self):
        layout=self.page('策略管理','编辑策略模板或自定义条件，保存为可重复载入的策略。自定义规则同组采用 AND。')
        bar=W.QHBoxLayout()
        self.strategy_list=W.QComboBox()
        self.strategy_list.currentIndexChanged.connect(self.load_saved_strategy)
        self.template=W.QComboBox()
        for k,v in TEMPLATES.items(): self.template.addItem(v['name'],k)
        self.template.currentIndexChanged.connect(self.load_template)
        bar.addWidget(self.strategy_list,1)
        bar.addWidget(self.template,1)
        bar.addWidget(self.button('新建模板',self.load_template))
        bar.addWidget(self.button('保存策略',self.save_strategy,True))
        bar.addWidget(self.button('另存策略',lambda:self.save_strategy(True)))
        bar.addWidget(self.button('删除',self.delete_strategy))
        layout.addLayout(bar)
        self.strategy_editor=W.QPlainTextEdit()
        self.strategy_editor.setFont(QtGui.QFont('Consolas',12))
        self.strategy_editor.setPlainText(json.dumps(TEMPLATES['sma'],ensure_ascii=False,indent=2))
        layout.addWidget(self.strategy_editor,1)
        helptext=W.QLabel('可用指标：close、sma_fast、sma_slow、ema_fast、ema_slow、rsi、bb_upper、bb_lower、macd、macd_signal、atr、high_channel、low_channel。\n比较符：>、<、>=、<=、cross_above、cross_below；right 可以是数值或另一个指标名称。')
        helptext.setWordWrap(True)
        layout.addWidget(helptext)
        layout.addWidget(self.button('使用当前策略进行回测',self.use_strategy))

    def definition(self):
        try:return validate(json.loads(self.strategy_editor.toPlainText()))
        except json.JSONDecodeError as exc:raise ValueError(f'策略 JSON 第 {exc.lineno} 行：{exc.msg}') from None

    def load_template(self,*args):
        self.saved_strategy_id=None
        self.strategy_editor.setPlainText(json.dumps(TEMPLATES[self.template.currentData()],ensure_ascii=False,indent=2))

    def save_strategy(self,new=False):
        s=self.definition()
        self.saved_strategy_id=self.service.store.save('strategy',s['name'],s,None if new else self.saved_strategy_id)
        self.refresh_strategy_list()
        self.status.setText('策略已保存')

    def refresh_strategy_list(self):
        self.strategy_list.blockSignals(True)
        self.strategy_list.clear()
        self.strategy_list.addItem('选择已保存策略',None)
        for doc in self.service.store.documents('strategy'):self.strategy_list.addItem(doc['name'],doc['id'])
        self.strategy_list.blockSignals(False)

    def load_saved_strategy(self,*args):
        ident=self.strategy_list.currentData()
        if ident:
            self.saved_strategy_id=ident
            self.strategy_editor.setPlainText(json.dumps(self.service.store.load(ident)['body'],ensure_ascii=False,indent=2))

    def delete_strategy(self):
        if not self.saved_strategy_id:raise ValueError('请选择已保存策略')
        if W.QMessageBox.question(self,'删除策略','删除当前策略定义？')==W.QMessageBox.StandardButton.Yes:
            self.service.store.delete(self.saved_strategy_id)
            self.saved_strategy_id=None
            self.refresh_strategy_list()

    def use_strategy(self):
        self.definition()
        self.strategy_label.setText(self.definition()['name'])
        self.nav.setCurrentRow(3)

    def build_backtest(self):
        layout=self.page('回测研究','设定交易区间与成本。预热使用开始日期之前的数据；回测结果自动保存到实验库。')
        outer=W.QSplitter()
        controls=W.QWidget()
        column=W.QVBoxLayout(controls)
        box=W.QGroupBox('数据与配置')
        form=W.QFormLayout(box)
        self.backtest_data=W.QComboBox()
        form.addRow('数据集',self.backtest_data)
        self.strategy_label=W.QLabel('双均线趋势')
        form.addRow('当前编辑策略',self.strategy_label)
        form.addRow(self.button('编辑策略',lambda:self.nav.setCurrentRow(2)))
        self.settings={}
        specs=[('start','开始 YYYY-MM-DD',''),('end','结束 YYYY-MM-DD',''),('capital','初始资金',100000),
               ('fee_bps','单边手续费 / bps',5),('slippage_bps','滑点 / bps',5),('allocation_pct','仓位比例 / %',100),
               ('stop_loss_pct','止损 / %（0 关闭）',0),('take_profit_pct','止盈 / %（0 关闭）',0),
               ('lot_size','交易单位 / 股',1),('volume_limit_pct','成交量上限 / %',100),('risk_free_pct','无风险年利率 / %',0),('annual_days','年交易日数',252)]
        for key,label,default in specs:
            w=W.QLineEdit(str(default))
            w.setObjectName(key)
            self.settings[key]=w
            form.addRow(label,w)
        self.config_list=W.QComboBox()
        self.config_list.currentIndexChanged.connect(self.load_config)
        form.addRow('保存的配置',self.config_list)
        form.addRow(self.button('保存当前配置',self.save_config))
        column.addWidget(box)
        runbar=W.QHBoxLayout()
        runbar.addWidget(self.button('运行回测',self.run_backtest,True))
        runbar.addWidget(self.button('导出结果',self.export_current))
        column.addLayout(runbar)
        column.addStretch()
        scroll=W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(290)
        scroll.setMaximumWidth(360)
        outer.addWidget(scroll)
        right=W.QWidget()
        result_layout=W.QVBoxLayout(right)
        self.result_title=W.QLabel('尚无回测结果')
        result_layout.addWidget(self.result_title)
        self.metric_labels={}
        metric_grid=W.QGridLayout()
        for i,key in enumerate(['return_pct','annualized_return_pct','max_drawdown_pct','sharpe','win_rate_pct','profit_loss_ratio','equity','pnl']):
            cell=W.QWidget()
            v=W.QVBoxLayout(cell)
            v.addWidget(W.QLabel(LABELS[key]))
            label=W.QLabel('—')
            label.setProperty('metric',True)
            v.addWidget(label)
            self.metric_labels[key]=label
            metric_grid.addWidget(cell,i//4,i%4)
        result_layout.addLayout(metric_grid)
        self.result_tabs=W.QTabWidget()
        self.charts=Charts()
        self.result_tabs.addTab(self.charts,'图表')
        self.result_tables={}
        for key,label in [('trades','成交'),('orders','订单'),('curve','现金 / 持仓 / 盈亏'),('round_trips','已平仓交易'),('summary','全部绩效')]:
            t=table()
            self.result_tables[key]=t
            self.result_tabs.addTab(t,label)
        self.assumptions=W.QPlainTextEdit()
        self.assumptions.setReadOnly(True)
        self.result_tabs.addTab(self.assumptions,'口径与来源')
        result_layout.addWidget(self.result_tabs,1)
        outer.addWidget(right)
        outer.setStretchFactor(1,1)
        layout.addWidget(outer,1)

    def current_config(self):
        return config({k:w.text().strip() for k,w in self.settings.items()})

    def run_backtest(self):
        ds=self.backtest_data.currentData()
        if not ds:raise ValueError('请先导入或获取行情')
        strategy=self.definition()
        settings=self.current_config()
        self.strategy_label.setText(strategy['name'])
        self.start_job('正在回测…',lambda cancel,progress:self.service.backtest(ds,strategy,settings,cancel=cancel),self.show_result)

    def show_result(self,result):
        self.result=result
        s=result['summary']
        self.result_title.setText(f'{result["strategy"]["name"]} · {result["dataset"]["symbol"]} · {s["start"]} — {s["end"]} · {s["trades"]} 笔成交')
        for key,label in self.metric_labels.items():label.setText(formatted(s[key]))
        self.charts.show_result(result)
        populate(self.result_tables['trades'],result['trades'],['signal_date','date','side','price','quantity','fee','cash','realized_pnl','reason'])
        populate(self.result_tables['orders'],result['orders'],['id','signal_date','date','side','status','quantity','price','reason'])
        populate(self.result_tables['curve'],result['curve'],['date','shares','cash','market_value','equity','realized_pnl','unrealized_pnl','pnl','drawdown'])
        populate(self.result_tables['round_trips'],result['round_trips'],['entry_date','exit_date','quantity','entry_price','exit_price','pnl','return_pct','holding_days'])
        populate(self.result_tables['summary'],[{'metric':LABELS.get(k,k),'value':v} for k,v in s.items()],['metric','value'])
        self.assumptions.setPlainText(json.dumps({'dataset':result['dataset'],'config':result['config'],'strategy':result['strategy'],'assumptions':result['assumptions'],'engine_version':result['engine_version']},ensure_ascii=False,indent=2))
        self.nav.setCurrentRow(3)

    def save_config(self):
        name,ok=W.QInputDialog.getText(self,'保存配置','配置名称')
        if ok and name.strip():
            self.service.store.save('config',name,{'dataset_id':self.backtest_data.currentData(),'strategy':self.definition(),'config':self.current_config()})
            self.refresh_configs()

    def load_config(self,*args):
        ident=self.config_list.currentData()
        if not ident:return
        body=self.service.store.load(ident)['body']
        for key,value in body['config'].items():
            if key in self.settings:self.settings[key].setText(str(value))
        idx=self.backtest_data.findData(body['dataset_id'])
        if idx >= 0:self.backtest_data.setCurrentIndex(idx)
        self.strategy_editor.setPlainText(json.dumps(body['strategy'],ensure_ascii=False,indent=2))
        self.strategy_label.setText(body['strategy']['name'])

    def refresh_configs(self):
        self.config_list.blockSignals(True)
        self.config_list.clear()
        self.config_list.addItem('选择保存的配置',None)
        for doc in self.service.store.documents('config'):self.config_list.addItem(doc['name'],doc['id'])
        self.config_list.blockSignals(False)

    def export_current(self):
        if not self.result:raise ValueError('请先运行或载入实验')
        folder=W.QFileDialog.getExistingDirectory(self,'导出完整报告到目录')
        if folder:
            export_result(self.result,Path(folder)/('experiment-'+self.result.get('id','export')[:12]))
            self.status.setText('已导出 JSON 报告、绩效、成交、订单、已平仓交易和资产 CSV')

    def build_experiments(self):
        layout=self.page('实验与比较','保存的结果可重新载入。参数研究在相同区间执行；收益排序只用于历史研究。')
        top=W.QHBoxLayout()
        self.grid=W.QLineEdit('{"fast":[5,10,15],"slow":[20,30,60]}')
        top.addWidget(W.QLabel('参数网格'))
        top.addWidget(self.grid,1)
        top.addWidget(self.button('研究当前策略',self.tune,True))
        top.addWidget(self.button('比较所有保存策略',self.compare_saved))
        layout.addLayout(top)
        actions=W.QHBoxLayout()
        for text,fn in [('刷新',self.refresh_experiments),('载入选中实验',self.load_experiment),('叠加选中曲线',self.overlay),('导出比较表',self.export_comparison),('导入报告',self.import_report),('删除选中实验',self.delete_experiments)]:actions.addWidget(self.button(text,fn))
        actions.addStretch()
        layout.addLayout(actions)
        self.experiments=table()
        self.experiments.doubleClicked.connect(lambda:self.guard(self.load_experiment))
        self.comparison=plot('选中实验的累计收益 / %')
        split=W.QSplitter(QtCore.Qt.Orientation.Vertical)
        split.addWidget(self.experiments)
        split.addWidget(self.comparison)
        split.setSizes([420,320])
        layout.addWidget(split,1)

    def refresh_experiments(self):
        records=self.service.store.documents('experiment')
        rows=[{'id':r['id'],'name':r['name'],'symbol':r['body']['dataset']['symbol'],**r['body']['summary'],
               'fast':r['body']['strategy']['fast'],'slow':r['body']['strategy']['slow'],'updated_at':r['updated_at']} for r in records]
        rows.sort(key=lambda r:r['return_pct'],reverse=True)
        populate(self.experiments,rows,['name','symbol','start','end','fast','slow','return_pct','annualized_return_pct','max_drawdown_pct','sharpe','win_rate_pct','profit_loss_ratio','trades','updated_at'])

    def selected_experiments(self):
        selected=self.experiments.selectionModel().selectedRows() if self.experiments.model() else []
        if not selected:raise ValueError('请先选择实验；按 Ctrl 可多选')
        return [self.experiments.model().rows[i.row()]['id'] for i in selected]

    def load_experiment(self):
        ident=self.selected_experiments()[0]
        self.show_result({'id':ident,**self.service.store.load(ident)['body']})

    def overlay(self):
        results=[self.service.store.load(i) for i in self.selected_experiments()]
        if len(results)>20:raise ValueError('一次最多叠加 20 个实验')
        signatures={(r['body']['dataset']['metadata']['sha256'],r['body']['summary']['start'],r['body']['summary']['end']) for r in results}
        if len(signatures)>1:raise ValueError('所选实验的数据或交易区间不同。请使用参数研究或策略比较生成同区间实验。')
        self.comparison.clear()
        self.comparison.plotItem.legend.clear()
        for i,doc in enumerate(results):
            curve=doc['body']['curve']
            self.comparison.plot([timestamp(r['date']) for r in curve],[r['return_pct'] for r in curve],pen=pg.mkPen(COLORS[i%len(COLORS)],width=1.7),name=doc['name'])
        self.comparison.enableAutoRange()

    def tune(self):
        ds=self.backtest_data.currentData()
        strategy,settings,grid=self.definition(),self.current_config(),json.loads(self.grid.text())
        self.start_job('正在运行参数网格…',lambda cancel,progress:self.service.tune(ds,strategy,settings,grid,cancel,progress),lambda _:self.refresh_experiments())

    def compare_saved(self):
        ds=self.backtest_data.currentData()
        settings=self.current_config()
        strategies=[d['body'] for d in self.service.store.documents('strategy')]
        self.start_job('正在比较策略…',lambda cancel,progress:self.service.compare(ds,strategies,settings,cancel,progress),lambda _:self.refresh_experiments())

    def export_comparison(self):
        import csv
        path,_=W.QFileDialog.getSaveFileName(self,'导出比较','comparison.csv','CSV (*.csv)')
        if path:
            model=self.experiments.model()
            with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,model.keys,extrasaction='ignore')
                writer.writeheader()
                writer.writerows(model.rows)

    def import_report(self):
        path,_=W.QFileDialog.getOpenFileName(self,'导入实验报告','','JSON (*.json)')
        if not path:return
        body=json.loads(Path(path).read_text(encoding='utf-8'))
        required={'strategy','config','dataset','summary','curve','orders','trades','round_trips','engine_version','assumptions'}
        if not isinstance(body,dict) or not required.issubset(body):raise ValueError('不是完整的桌面版报告')
        validate(body['strategy'])
        config(body['config'])
        if not body['curve']:raise ValueError('报告缺少资产曲线')
        self.service.store.save('experiment',Path(path).stem+' · 导入',body)
        self.refresh_experiments()

    def delete_experiments(self):
        ids=self.selected_experiments()
        if W.QMessageBox.question(self,'删除实验',f'删除 {len(ids)} 个实验？')==W.QMessageBox.StandardButton.Yes:
            for ident in ids:self.service.store.delete(ident)
            self.refresh_experiments()

    def build_logs(self):
        layout=self.page('任务日志','查看数据请求、清洗、回测和失败详情。记录保存在本机数据库。')
        layout.addWidget(self.button('刷新日志',self.refresh_logs))
        self.logs_table=table()
        layout.addWidget(self.logs_table,1)
        self.log_detail=W.QPlainTextEdit()
        self.log_detail.setReadOnly(True)
        self.log_detail.setMaximumHeight(230)
        layout.addWidget(self.log_detail)
        self.logs_table.clicked.connect(lambda index:self.log_detail.setPlainText(self.logs_table.model().rows[index.row()].get('detail','')))
        layout.addWidget(W.QLabel(f'本机数据目录：{self.service.store.home}'))

    def refresh_logs(self):populate(self.logs_table,self.service.store.logs(),['created_at','level','message','detail'])

    def refresh(self):
        self.refresh_datasets()
        current=self.backtest_data.currentData()
        self.backtest_data.blockSignals(True)
        self.backtest_data.clear()
        for ds in self.service.store.datasets():self.backtest_data.addItem(ds['name'],ds['id'])
        index=self.backtest_data.findData(current)
        if index>=0:self.backtest_data.setCurrentIndex(index)
        self.backtest_data.blockSignals(False)
        self.refresh_strategy_list()
        self.refresh_configs()
        self.refresh_experiments()
        self.refresh_logs()


def main():
    app=W.QApplication(sys.argv)
    app.setApplicationName('QuantDesk')
    app.setOrganizationName('QuantDesk')
    window=Window()
    window.show()
    return app.exec()

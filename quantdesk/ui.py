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
from .charts import Charts, plot, timestamp, COLORS, LIGHT_COLORS, Candles
from .theme import DARK, LIGHT, stylesheet
from .strategy_form import StrategyForm
from .market_preview import MarketPreview

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
          'holding_days':'持仓天数','metric':'指标','value':'数值','benchmark_pct':'买入持有收益 %','benchmark':'买入持有资产',
          'exposure_pct':'持仓时间 %','volatility_pct':'年化波动 %','bars':'交易日线数'}


def formatted(value):
    if value is None:
        return '—'
    if isinstance(value,float):
        return f'{value:,.2f}'
    if isinstance(value,int):return f'{value:,}'
    return str(value)


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, rows, keys, colors=None):
        super().__init__()
        self.rows, self.keys = rows, keys
        self.colors=colors or DARK

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.keys)

    def data(self,index,role=QtCore.Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return formatted(self.rows[index.row()].get(self.keys[index.column()]))
        if index.isValid() and role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            value=self.rows[index.row()].get(self.keys[index.column()])
            return int(QtCore.Qt.AlignmentFlag.AlignVCenter | (QtCore.Qt.AlignmentFlag.AlignRight if isinstance(value,(int,float)) else QtCore.Qt.AlignmentFlag.AlignLeft))
        if index.isValid() and role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return str(self.rows[index.row()].get(self.keys[index.column()],'—'))
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DecorationRole and self.keys[index.column()]=='name':
            color=self.rows[index.row()].get('_curve_color')
            if color:return QtGui.QColor(color)
        if index.isValid() and role == QtCore.Qt.ItemDataRole.FontRole and isinstance(self.rows[index.row()].get(self.keys[index.column()]),(int,float)):
            return QtGui.QFont('Consolas',10)
        if index.isValid() and role == QtCore.Qt.ItemDataRole.ForegroundRole:
            key=self.keys[index.column()]
            value=self.rows[index.row()].get(key)
            if key in {'pnl','return_pct','annualized_return_pct','realized_pnl','unrealized_pnl','max_drawdown_pct','drawdown'} and isinstance(value,(int,float)) and value:
                return QtGui.QColor(self.colors['positive'] if value>0 else self.colors['negative'])

    def headerData(self,section,orientation,role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return LABELS.get(self.keys[section],self.keys[section]) if orientation == QtCore.Qt.Orientation.Horizontal else str(section+1)

    def sort(self,column,order):
        self.beginResetModel()
        key=self.keys[column]
        self.rows.sort(key=lambda r:(r.get(key) is not None,r.get(key) or 0),reverse=order==QtCore.Qt.SortOrder.DescendingOrder)
        self.endResetModel()


def table():
    t=W.QTableView()
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(W.QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setStretchLastSection(False)
    t.verticalHeader().setDefaultSectionSize(26)
    t.verticalHeader().hide()
    t.setShowGrid(False)
    return t


def populate(widget,rows,keys):
    widget.setModel(TableModel(rows,keys,getattr(widget.window(),'colors',DARK)))
    widget.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeMode.Stretch if len(keys)<=8 else W.QHeaderView.ResizeMode.Interactive)
    for i in range(len(keys)):
        widget.setColumnWidth(i,210 if keys[i]=='name' else 145 if keys[i] in ('created_at','updated_at','reason') else 95 if keys[i] in ('start','end','date','signal_date') else 88)


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




class Window(W.QMainWindow):
    def __init__(self,service=None):
        super().__init__()
        self.service=service or Service()
        self.setWindowTitle('观澜 · 量化研究工作台')
        screen=W.QApplication.primaryScreen()
        available=screen.availableGeometry() if screen else QtCore.QRect(0,0,1600,1000)
        self.resize(max(1060,min(1280,int(available.width()*.85))),max(680,min(800,int(available.height()*.85))))
        self.move(available.center()-self.rect().center())
        self.setMinimumSize(1060,680)
        self.preferences=QtCore.QSettings(str(self.service.store.home/'ui.ini'),QtCore.QSettings.Format.IniFormat)
        self.colors=LIGHT if self.preferences.value('theme','dark')=='light' else DARK
        self.setStyleSheet(stylesheet(self.colors))
        self.task_buttons=[]
        self.restoring=False
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
        self.nav.setFixedWidth(152)
        self.pages=W.QStackedWidget()
        layout.addWidget(self.nav)
        layout.addWidget(self.pages)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self.navigate)
        self.status=W.QLabel('就绪')
        self.statusBar().addWidget(self.status,1)
        self.progress=W.QProgressBar()
        self.progress.setMaximumWidth(190)
        self.progress.setMaximumHeight(18)
        self.progress.hide()
        self.cancel_button=W.QPushButton('取消任务')
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.cancel_task)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().addPermanentWidget(self.cancel_button)
        self.theme_button=W.QPushButton('深色' if self.colors is LIGHT else '浅色')
        self.theme_button.clicked.connect(self.toggle_theme)
        for button in (self.cancel_button,self.theme_button):
            button.setStyleSheet('QPushButton {min-height:0;padding:2px 8px;}')
            button.setFixedHeight(22)
        self.statusBar().addPermanentWidget(self.theme_button)
        self.build_data()
        self.build_strategies()
        self.build_backtest()
        self.build_experiments()
        self.build_logs()
        self.seed_sample()
        self.refresh()
        self.apply_chart_theme()
        self.nav.setCurrentRow(1)
        if self.service.store.datasets():self.select_dataset(self.service.store.datasets()[0]['id'])

    def navigate(self,index):
        self.pages.setCurrentIndex(max(0,index-1))

    def apply_chart_theme(self):
        self.charts.theme_colors=self.colors
        for chart in self.findChildren(pg.PlotWidget):
            chart.setBackground(self.colors['panel'])
            for axis in ('left','bottom'):
                chart.getAxis(axis).setTextPen(self.colors['muted'])
                chart.getAxis(axis).setPen(self.colors['border'])
            doc=QtGui.QTextDocument()
            doc.setHtml(chart.plotItem.titleLabel.text)
            chart.setTitle(doc.toPlainText(),color=self.colors['muted'],size='10pt')
            if chart.plotItem.legend:
                chart.plotItem.legend.setLabelTextColor(self.colors['text'])
                chart.plotItem.legend.setBrush(pg.mkBrush(self.colors['panel']))
                for sample,label in chart.plotItem.legend.items:label.setText(label.text,color=self.colors['text'])
        for t in self.findChildren(W.QTableView):
            if t.model():
                t.model().colors=self.colors
                t.viewport().update()

    def toggle_theme(self):
        self.colors=LIGHT if self.colors is DARK else DARK
        self.preferences.setValue('theme','light' if self.colors is LIGHT else 'dark')
        self.setStyleSheet(stylesheet(self.colors))
        self.theme_button.setText('深色' if self.colors is LIGHT else '浅色')
        self.apply_chart_theme()
        if self.result:
            self.update_metrics()
            self.charts.show_result(self.result)
            self.mark_dirty()
        self.dataset_context_changed()
        if self.data_preview.dataset:self.data_preview.show_dataset(self.data_preview.dataset,self.data_preview.rows,self.colors)
        if hasattr(self,'comparison_ids') and self.comparison_ids:self.draw_overlay(self.comparison_ids)

    def mark_dirty(self):
        if self.result and not self.restoring:
            try:
                changed=self.current_config()!=self.result['config'] or self.definition()!=self.result['strategy'] or self.backtest_data.currentData()!=self.result['dataset']['id']
            except ValueError:changed=True
            self.result_state.setText('参数已修改 · 结果尚未更新' if changed else '已保存 · 双击成交可定位图表')
            self.result_state.setStyleSheet('color:'+self.colors['negative'] if changed else '')

    def page(self,title,subtitle):
        p=W.QWidget()
        layout=W.QVBoxLayout(p)
        layout.setContentsMargins(16,12,16,12)
        layout.setSpacing(8)
        heading=W.QLabel(title)
        heading.setProperty('title',True)
        layout.addWidget(heading)
        label=W.QLabel(subtitle)
        label.setWordWrap(True)
        label.setProperty('muted',True)
        layout.addWidget(label)
        self.pages.addWidget(p)
        return layout

    def button(self,text,fn,primary=False):
        b=W.QPushButton(text)
        b.setProperty('primary',primary)
        b.clicked.connect(lambda: self.guard(fn))
        if getattr(fn,'__name__','') in {'run_backtest','tune','compare_saved','fetch_data','import_data'}:self.task_buttons.append(b)
        if '删除' in text:b.setProperty('danger',True)
        return b

    def guard(self,fn):
        try:
            return fn()
        except Exception as exc:
            self.error(str(exc),traceback.format_exc())

    def error(self,message,detail=''):
        self.service.store.log('ERROR',message,detail)
        self.status.setText('失败：'+message)
        self.status.setStyleSheet('color:'+self.colors['negative'])
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
        for button in self.task_buttons:button.setEnabled(False)
        self.job_refs.append(job)
        self.progress.setRange(0,0)
        self.progress.show()
        self.cancel_button.show()
        self.status.setStyleSheet('')
        self.status.setText(label)
        job.signals.failed.connect(self.job_failed,QtCore.Qt.ConnectionType.QueuedConnection)
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
        self.status.setText('已完成并保存')
        try:
            callback(value)
        except Exception as exc:
            self.error(str(exc),traceback.format_exc())

    def finish_job(self):
        if self.active_job in self.job_refs:
            self.job_refs.remove(self.active_job)
        self.active_job=None
        self.progress.hide()
        self.cancel_button.hide()
        for button in self.task_buttons:button.setEnabled(True)
        self.run_button.setEnabled(bool(self.backtest_data.currentData()))
        self.update_scan_context()

    def job_failed(self,message,detail):
        self.finish_job()
        self.refresh()
        if '已取消' in message:
            self.status.setText(message);self.status.setStyleSheet('')
        else:self.error(message,detail)

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
        layout=self.page('行情数据','选择来源和日期后获取日线，或导入 CSV；已保存数据可离线查看。')
        bar=W.QHBoxLayout()
        self.provider=W.QComboBox()
        for label,key in [('Yahoo 日线','yahoo'),('Stooq 日线','stooq'),('AAPL 固定样本','plotly')]:self.provider.addItem(label,key)
        self.provider.setMaximumWidth(155)
        self.symbol=W.QLineEdit('AAPL')
        self.symbol.setMaximumWidth(100)
        self.fetch_start=W.QLineEdit('2020-01-01')
        self.fetch_end=W.QLineEdit('2025-12-31')
        for label,widget in [('来源',self.provider),('代码',self.symbol),('从',self.fetch_start),('至',self.fetch_end)]:
            bar.addWidget(W.QLabel(label));bar.addWidget(widget)
        for field in (self.fetch_start,self.fetch_end):field.setMaximumWidth(130)
        self.provider.currentIndexChanged.connect(self.provider_changed)
        bar.addWidget(self.button('获取行情',self.fetch_data,True))
        bar.addWidget(self.button('导入 CSV',self.import_data))
        bar.addStretch()
        layout.addLayout(bar)
        self.drop_invalid=W.QCheckBox('丢弃无效行')
        self.duplicates=W.QComboBox()
        self.duplicates.addItems(['重复日期报错','保留第一行','保留最后一行'])
        import_options=W.QHBoxLayout()
        import_options.addWidget(W.QLabel('CSV 导入规则'))
        import_options.addWidget(self.drop_invalid)
        import_options.addWidget(self.duplicates)
        import_options.addStretch()
        layout.addLayout(import_options)
        split=W.QSplitter(QtCore.Qt.Orientation.Horizontal)
        library=W.QWidget()
        left=W.QVBoxLayout(library)
        left.setContentsMargins(0,0,8,0)
        left.addWidget(W.QLabel('数据集'))
        self.search=W.QLineEdit()
        self.search.setPlaceholderText('搜索代码或数据集')
        self.search.textChanged.connect(self.refresh_datasets)
        left.addWidget(self.search)
        self.datasets_table=table()
        self.datasets_table.clicked.connect(self.load_data_selection)
        left.addWidget(self.datasets_table,1)
        left.addWidget(self.button('使用此数据回测',self.use_dataset,True))
        actions=W.QHBoxLayout()
        actions.addWidget(self.button('导出 CSV',self.export_data))
        actions.addWidget(self.button('删除',self.delete_data))
        left.addLayout(actions)
        library.setMinimumWidth(240)
        library.setMaximumWidth(360)
        split.addWidget(library)
        details=W.QWidget()
        right=W.QVBoxLayout(details)
        right.setContentsMargins(0,0,0,0)
        self.data_context=W.QLabel('尚无数据集 · 获取行情或导入 CSV')
        self.data_context.setWordWrap(True)
        right.addWidget(self.data_context)
        query=W.QHBoxLayout()
        self.query_start=W.QLineEdit()
        self.query_start.setPlaceholderText('开始 YYYY-MM-DD')
        self.query_end=W.QLineEdit()
        self.query_end.setPlaceholderText('结束 YYYY-MM-DD')
        for field in (self.query_start,self.query_end):field.setMaximumWidth(150)
        query.addWidget(W.QLabel('查看区间'))
        query.addWidget(self.query_start);query.addWidget(self.query_end)
        query.addWidget(self.button('筛选',self.load_data_selection))
        query.addWidget(self.button('全部',self.clear_data_filter))
        query.addStretch()
        right.addLayout(query)
        self.data_tabs=W.QTabWidget()
        self.data_preview=MarketPreview()
        self.data_chart=self.data_preview.price
        self.data_tabs.addTab(self.data_preview,'行情概览')
        self.data_table=table()
        self.data_tabs.addTab(self.data_table,'行情明细')
        self.data_meta=W.QPlainTextEdit()
        self.data_meta.setReadOnly(True)
        self.data_tabs.addTab(self.data_meta,'来源与清洗')
        right.addWidget(self.data_tabs,1)
        split.addWidget(details)
        split.setSizes([270,950]);split.setStretchFactor(1,1)
        layout.addWidget(split,1)

    def provider_changed(self):
        if self.provider.currentData()=='plotly':
            self.symbol.setText('AAPL')
            self.fetch_start.setText('2015-02-17');self.fetch_end.setText('2017-02-16')

    def clear_data_filter(self):
        self.query_start.clear();self.query_end.clear();self.load_data_selection()

    def use_dataset(self):
        ident=self.current_dataset()
        self.backtest_data.setCurrentIndex(self.backtest_data.findData(ident))
        self.nav.setCurrentRow(3)

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
        populate(self.datasets_table,flat,['name','rows'])
        for i,row in enumerate(flat):
            if row['id']==ident:self.datasets_table.selectRow(i)
        if not self.datasets_table.selectionModel().selectedRows():
            self.data_context.setText('没有匹配的数据集' if self.search.text() else '选择左侧数据集查看行情')
            self.data_preview.clear();self.data_preview_rows=[];self.data_meta.clear()
            populate(self.data_table,[],['date','open','high','low','close','volume'])

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
            m=ds['metadata']
            self.data_context.setText(f"{ds['symbol']}  ·  {m['rows']:,} 根日线  ·  {m['start']} — {m['end']}  ·  {m.get('provider','CSV')}")
            self.backtest_data.setCurrentIndex(self.backtest_data.findData(ident))
            self.data_chart.clear()
            # Preview cost is bounded; full records remain queryable/exportable.
            self.data_preview_rows=rows[-5000:]
            self.data_preview.show_dataset(ds,self.data_preview_rows,self.colors)
            self.status.setText(f'查询 {len(rows)} 根日线；K线预览显示最近最多 5,000 根')
        self.guard(load)

    def fetch_data(self):
        provider,symbol,start,end=self.provider.currentData(),self.symbol.text(),self.fetch_start.text(),self.fetch_end.text()
        self.start_job('正在获取历史行情…',lambda cancel,progress:self.service.fetch(provider,symbol,start,end,cancel),self.select_dataset)

    def import_data(self):
        path,_=W.QFileDialog.getOpenFileName(self,'导入历史日线','','CSV (*.csv);;所有文件 (*)')
        if not path:return
        policy=['error','first','last'][self.duplicates.currentIndex()]
        invalid=self.drop_invalid.isChecked()
        symbol=self.symbol.text() or 'CUSTOM'
        self.start_job('正在导入并校验…',lambda cancel,progress:self.service.import_csv(path,symbol=symbol,drop_invalid=invalid,duplicates=policy),self.select_dataset)

    def select_dataset(self,ident):
        self.search.clear()
        self.refresh_datasets()
        for i,row in enumerate(self.datasets_table.model().rows):
            if row['id']==ident:
                self.datasets_table.selectRow(i)
                self.query_start.clear();self.query_end.clear()
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
        self.strategy_form=StrategyForm()
        self.strategy_editor=self.strategy_form.editor
        self.strategy_form.changed.connect(self.sync_quick_strategy)
        layout.addWidget(self.strategy_form,1)
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
        self.strategy_list.setCurrentIndex(max(0,self.strategy_list.findData(self.saved_strategy_id)))
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
        layout=self.page('回测研究','历史模拟 · 收盘信号在下一日开盘执行')
        outer=W.QSplitter()
        left=W.QWidget()
        left.setMinimumWidth(265);left.setMaximumWidth(300)
        column=W.QVBoxLayout(left)
        column.setContentsMargins(0,0,6,0)
        controls=W.QWidget()
        formcolumn=W.QVBoxLayout(controls)
        formcolumn.setContentsMargins(0,0,0,0)
        box=W.QGroupBox('研究配置')
        form=W.QFormLayout(box)
        form.setVerticalSpacing(7)
        self.backtest_data=W.QComboBox()
        form.addRow(W.QLabel('数据集'))
        form.addRow(self.backtest_data)
        self.backtest_context=W.QLabel()
        self.backtest_context.setWordWrap(True)
        self.backtest_context.setProperty('muted',True)
        form.addRow(self.backtest_context)
        self.quick_template=W.QComboBox()
        for key,value in TEMPLATES.items():self.quick_template.addItem(value['name'],key)
        form.addRow('策略',self.quick_template)
        self.quick_template.currentIndexChanged.connect(self.quick_template_changed)
        self.strategy_label=W.QLabel('双均线趋势')
        self.strategy_label.setWordWrap(True)
        form.addRow(self.strategy_label)
        self.quick_fields={}
        quick=W.QHBoxLayout()
        for key,label in [('fast','短周期'),('slow','长周期')]:
            quick.addWidget(W.QLabel(label))
            field=W.QLineEdit('10' if key=='fast' else '30')
            field.setMaximumWidth(60)
            field.setObjectName('quick_'+key)
            field.textChanged.connect(lambda value,k=key:self.edit_quick_strategy(k,value))
            self.quick_fields[key]=field;quick.addWidget(field)
        self.quick_row=W.QWidget();self.quick_row.setLayout(quick)
        quick.setContentsMargins(0,0,0,0)
        form.addRow(self.quick_row)
        form.addRow(self.button('编辑其他参数 / 规则',lambda:self.nav.setCurrentRow(2)))
        self.settings={}
        basic=[('start','开始日期',''),('end','结束日期',''),('capital','初始资金',100000),('fee_bps','手续费 / bps',5),('slippage_bps','滑点 / bps',5),('allocation_pct','仓位 / %',100)]
        advanced=[('stop_loss_pct','止损 / %',0),('take_profit_pct','止盈 / %',0),('lot_size','交易单位 / 股',1),('volume_limit_pct','成交量上限 / %',100),('risk_free_pct','无风险利率 / %',0),('annual_days','年交易日数',252)]
        for key,label,default in basic:
            field=W.QLineEdit(str(default))
            field.setObjectName(key);self.settings[key]=field
            field.setPlaceholderText('自动' if key in ('start','end') else '')
            field.textChanged.connect(self.mark_dirty)
            form.addRow(label,field)
        formcolumn.addWidget(box)
        more=W.QToolButton()
        more.setText('风控与估值设置');more.setCheckable(True)
        more.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        more.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        more.toggled.connect(lambda checked:more.setArrowType(QtCore.Qt.ArrowType.DownArrow if checked else QtCore.Qt.ArrowType.RightArrow))
        formcolumn.addWidget(more)
        advanced_box=W.QWidget()
        advanced_form=W.QFormLayout(advanced_box)
        advanced_form.setContentsMargins(10,4,10,4)
        for key,label,default in advanced:
            field=W.QLineEdit(str(default))
            field.setObjectName(key);self.settings[key]=field
            field.setToolTip('0 表示关闭保护规则' if key in ('stop_loss_pct','take_profit_pct') else label)
            field.textChanged.connect(self.mark_dirty)
            advanced_form.addRow(label,field)
        advanced_box.hide()
        more.toggled.connect(advanced_box.setVisible)
        formcolumn.addWidget(advanced_box)
        self.advanced_settings=advanced_box
        self.config_list=W.QComboBox()
        self.config_list.currentIndexChanged.connect(self.load_config)
        formcolumn.addWidget(self.config_list)
        formcolumn.addWidget(self.button('保存配置',self.save_config))
        formcolumn.addStretch()
        scroll=W.QScrollArea()
        scroll.setWidgetResizable(True);scroll.setWidget(controls)
        column.addWidget(scroll,1)
        self.run_button=self.button('运行回测',self.run_backtest,True)
        self.run_button.setToolTip('Ctrl+Enter')
        column.addWidget(self.run_button)
        self.export_button=self.button('导出当前结果',self.export_current)
        self.export_button.setEnabled(False)
        column.addWidget(self.export_button)
        outer.addWidget(left)
        self.result_stack=W.QStackedWidget()
        empty=W.QWidget()
        empty_layout=W.QVBoxLayout(empty)
        self.preview_hint=W.QLabel('尚未回测 · 左侧设定参数后运行')
        self.preview_hint.setProperty('muted',True)
        empty_layout.addWidget(self.preview_hint)
        self.market_preview=MarketPreview()
        self.preview_chart=self.market_preview.price
        empty_layout.addWidget(self.market_preview,1)
        self.result_stack.addWidget(empty)
        right=W.QWidget()
        result_layout=W.QVBoxLayout(right)
        result_layout.setContentsMargins(6,0,0,0);result_layout.setSpacing(8)
        self.result_title=W.QLabel('')
        self.result_title.setWordWrap(True)
        result_layout.addWidget(self.result_title)
        self.result_state=W.QLabel('')
        self.result_state.setProperty('muted',True)
        result_layout.addWidget(self.result_state)
        self.metric_labels={}
        metric_grid=W.QHBoxLayout()
        for key in ['return_pct','annualized_return_pct','max_drawdown_pct','sharpe','win_rate_pct','pnl']:
            cell=W.QWidget();cell.setProperty('panel',True)
            v=W.QVBoxLayout(cell);v.setContentsMargins(10,8,10,8);v.setSpacing(3)
            title=W.QLabel(LABELS[key]);title.setProperty('muted',True)
            v.addWidget(title)
            label=W.QLabel('—');label.setProperty('metric',True)
            v.addWidget(label);self.metric_labels[key]=label
            metric_grid.addWidget(cell,1)
        result_layout.addLayout(metric_grid)
        self.account_line=W.QLabel('')
        self.account_line.setProperty('muted',True)
        result_layout.addWidget(self.account_line)
        self.result_tabs=W.QTabWidget()
        self.charts=Charts()
        self.result_tabs.addTab(self.charts,'图表')
        self.result_tables={}
        for key,label in [('trades','成交'),('orders','订单'),('curve','账户账本'),('round_trips','已平仓交易'),('summary','全部绩效')]:
            t=table();self.result_tables[key]=t;self.result_tabs.addTab(t,label)
        self.result_tables['trades'].doubleClicked.connect(self.focus_trade)
        self.result_tables['trades'].setToolTip('双击成交记录，定位图表中的交易日')
        self.assumptions=W.QPlainTextEdit();self.assumptions.setReadOnly(True)
        self.result_tabs.addTab(self.assumptions,'来源与口径')
        result_layout.addWidget(self.result_tabs,1)
        self.result_stack.addWidget(right)
        outer.addWidget(self.result_stack);outer.setStretchFactor(1,1)
        layout.addWidget(outer,1)
        self.backtest_data.currentIndexChanged.connect(self.dataset_context_changed)
        shortcut=QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Return'),self)
        shortcut.activated.connect(lambda:self.guard(self.run_backtest) if self.pages.currentIndex()==2 and not self.active_job else None)

    def dataset_context_changed(self):
        ident=self.backtest_data.currentData()
        self.run_button.setEnabled(bool(ident) and not self.active_job)
        if not ident:
            self.backtest_context.setText('请先导入行情')
            self.market_preview.clear()
            self.mark_dirty()
            self.update_scan_context()
            return
        ds=self.service.store.dataset(ident);m=ds['metadata']
        self.backtest_context.setText(f"{ds['symbol']} · {m['start']} — {m['end']}\n{m['rows']:,} 根日线")
        self.market_preview.show_dataset(ds,self.service.store.bars(ident),self.colors)
        self.mark_dirty()
        self.update_scan_context()

    def sync_quick_strategy(self):
        if not hasattr(self,'quick_template'):return
        self.mark_dirty()
        try:s=self.definition()
        except ValueError:return
        self.quick_template.blockSignals(True)
        self.quick_template.setCurrentIndex(self.quick_template.findData(s['kind']))
        self.quick_template.blockSignals(False)
        self.template.blockSignals(True)
        self.template.setCurrentIndex(self.template.findData(s['kind']))
        self.template.blockSignals(False)
        self.quick_row.setVisible(s['kind']!='buy_hold')
        for key,field in self.quick_fields.items():
            field.blockSignals(True);field.setText(str(s[key]));field.blockSignals(False)
        self.strategy_label.setText(s['name'])
        self.update_scan_context()

    def quick_template_changed(self):
        self.saved_strategy_id=None
        self.strategy_editor.setPlainText(json.dumps(TEMPLATES[self.quick_template.currentData()],ensure_ascii=False,indent=2))

    def edit_quick_strategy(self,key,value):
        self.strategy_form.fields[key].setText(value)

    def focus_trade(self,index):
        trade=self.result_tables['trades'].model().rows[index.row()]
        self.result_tabs.setCurrentIndex(0)
        self.charts.focus_date(trade['date'])
        self.status.setText(f"{trade['date']} · {trade['side']} {trade['quantity']} 股 · {trade['price']:.2f} · {trade['reason']}")

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
        self.restoring=True
        self.backtest_data.setCurrentIndex(self.backtest_data.findData(result['dataset']['id']))
        for key,value in result['config'].items():
            if key in self.settings:self.settings[key].setText(str(value))
        self.saved_strategy_id=None
        self.strategy_editor.setPlainText(json.dumps(result['strategy'],ensure_ascii=False,indent=2))
        self.restoring=False
        self.result=result
        s=result['summary']
        self.result_title.setText(f'{result["strategy"]["name"]} · {result["dataset"]["symbol"]} · {s["start"]} — {s["end"]} · {s["trades"]} 笔成交')
        self.result_stack.setCurrentIndex(1)
        self.export_button.setEnabled(True)
        self.result_state.setText('已保存 · 双击成交可定位图表' if self.backtest_data.currentData() else '历史结果 · 原数据集已移除，请选择数据再运行')
        self.result_state.setStyleSheet('')
        self.account_line.setText(f"资产 {s['equity']:,.2f}   现金 {s['cash']:,.2f}   持仓 {s['shares']:,} 股   手续费 {s['fees']:,.2f}   盈亏比 {formatted(s['profit_loss_ratio'])}")
        self.update_metrics()
        self.charts.show_result(result)
        populate(self.result_tables['trades'],result['trades'],['signal_date','date','side','price','quantity','fee','cash','realized_pnl','reason'])
        populate(self.result_tables['orders'],result['orders'],['id','signal_date','date','side','status','quantity','price','reason'])
        populate(self.result_tables['curve'],result['curve'],['date','shares','cash','market_value','equity','realized_pnl','unrealized_pnl','pnl','drawdown'])
        populate(self.result_tables['round_trips'],result['round_trips'],['entry_date','exit_date','quantity','entry_price','exit_price','pnl','return_pct','holding_days'])
        populate(self.result_tables['summary'],[{'metric':LABELS.get(k,k),'value':v} for k,v in s.items()],['metric','value'])
        self.assumptions.setPlainText(json.dumps({'dataset':result['dataset'],'config':result['config'],'strategy':result['strategy'],'assumptions':result['assumptions'],'engine_version':result['engine_version']},ensure_ascii=False,indent=2))
        self.nav.setCurrentRow(3)

    def update_metrics(self):
        s=self.result['summary']
        for key,label in self.metric_labels.items():
            label.setText(formatted(s[key]))
            color=self.colors['positive'] if s[key] is not None and s[key]>0 else self.colors['negative'] if s[key] is not None and s[key]<0 else self.colors['text']
            if key in ('win_rate_pct','sharpe'):color=self.colors['text']
            label.setStyleSheet('color:'+color)

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
        self.saved_strategy_id=None
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
        layout=self.page('实验与比较','在相同数据与区间比较参数或策略；点击行可多选，双击载入完整结果。')
        self.grid=W.QLineEdit('{"fast":[5,10,15],"slow":[20,30,60]}')
        self.grid.hide()
        self.grid_override=False
        self.scan_fields=[]
        grid_row=W.QHBoxLayout()
        for key,values in [('fast','5,10,15'),('slow','20,30,60')]:
            choice=W.QComboBox()
            for param in ('fast','slow','period','band','oversold','overbought'):choice.addItem(LABELS[param],param)
            choice.setCurrentIndex(choice.findData(key));choice.setMaximumWidth(125)
            field=W.QLineEdit(values);field.setMaximumWidth(165)
            field.setToolTip('用逗号分隔候选值，例如 5,10,15')
            grid_row.addWidget(choice);grid_row.addWidget(field)
            self.scan_fields.append((choice,field))
            choice.currentIndexChanged.connect(self.reset_grid_override)
            field.textChanged.connect(self.reset_grid_override)
        grid_row.addWidget(self.button('更多参数',self.edit_grid))
        grid_row.addStretch()
        layout.addLayout(grid_row)
        runrow=W.QHBoxLayout()
        self.tune_button=self.button('运行参数研究',self.tune,True)
        runrow.addWidget(self.tune_button)
        runrow.addWidget(self.button('比较已保存策略',self.compare_saved))
        self.scan_context=W.QLabel('');self.scan_context.setProperty('muted',True)
        self.scan_context.setWordWrap(True)
        self.last_scan_kind=None
        runrow.addWidget(self.scan_context,1)
        layout.addLayout(runrow)
        actions=W.QHBoxLayout()
        self.experiment_search=W.QLineEdit();self.experiment_search.setPlaceholderText('筛选名称或代码');self.experiment_search.setMaximumWidth(260)
        self.experiment_search.textChanged.connect(self.refresh_experiments)
        actions.addWidget(self.experiment_search)
        actions.addWidget(self.button('载入结果',self.load_experiment))
        actions.addWidget(self.button('刷新',self.refresh_experiments))
        actions.addStretch()
        more=W.QToolButton();more.setText('更多操作');more.setPopupMode(W.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu=W.QMenu(more)
        for title,fn in [('导出比较表',self.export_comparison),('导入实验报告',self.import_report),('删除选中实验',self.delete_experiments)]:
            menu.addAction(title,lambda checked=False,f=fn:self.guard(f))
        more.setMenu(menu);actions.addWidget(more)
        layout.addLayout(actions)
        self.experiments=table();self.experiments.setSelectionMode(W.QAbstractItemView.SelectionMode.MultiSelection)
        self.experiments.setMinimumHeight(150)
        self.experiments.doubleClicked.connect(lambda:self.guard(self.load_experiment))
        self.comparison=plot('累计收益 / % · 颜色对应上表名称');self.comparison.setMinimumHeight(180)
        self.comparison.plotItem.legend.setColumnCount(2)
        self.comparison_hint=W.QLabel('选择实验即可叠加收益曲线；尚无结果时，先运行回测或参数研究。')
        self.comparison_hint.setWordWrap(True);self.comparison_hint.setProperty('muted',True)
        self.comparison_stack=W.QStackedWidget()
        self.comparison_stack.addWidget(self.comparison_hint);self.comparison_stack.addWidget(self.comparison)
        self.comparison_ids=[]
        split=W.QSplitter(QtCore.Qt.Orientation.Vertical)
        split.addWidget(self.experiments);split.addWidget(self.comparison_stack);split.setSizes([300,260])
        layout.addWidget(split,1)

    def reset_grid_override(self,*args):
        self.grid_override=False
        self.update_scan_context()

    def update_scan_context(self):
        if not hasattr(self,'scan_context'):return
        try:strategy=self.definition()
        except ValueError:
            self.scan_context.setText('当前策略参数无效，请先修正')
            self.tune_button.setEnabled(False)
            return
        kind=strategy['kind']
        if self.last_scan_kind!=kind:
            self.last_scan_kind=kind
            self.grid_override=False
            defaults={
                'rsi':(('period','10,14,20'),('oversold','20,30,40')),
                'bollinger':(('slow','20,30,60'),('band','1.5,2,2.5')),
            }.get(kind,(('fast','5,10,15'),('slow','20,30,60')))
            for (choice,field),(key,values) in zip(self.scan_fields,defaults):
                choice.blockSignals(True);field.blockSignals(True)
                choice.setCurrentIndex(choice.findData(key));field.setText(values)
                choice.blockSignals(False);field.blockSignals(False)
        ident=self.backtest_data.currentData()
        symbol=self.service.store.dataset(ident)['symbol'] if ident else '未选择数据'
        self.scan_context.setText(f"{symbol} · {strategy['name']}"+(' · 自定义参数网格' if self.grid_override else ' · 沿用回测页的日期与资金设置'))
        self.tune_button.setEnabled(bool(ident) and kind!='buy_hold' and not self.active_job)
        self.tune_button.setToolTip('买入持有没有可研究的策略参数' if kind=='buy_hold' else '')

    def parameter_grid(self):
        if self.grid_override:return json.loads(self.grid.text())
        result={}
        for choice,field in self.scan_fields:
            key=choice.currentData()
            if key in result:raise ValueError('请选择两个不同的扫描参数；单参数研究可使用更多参数。')
            try:values=[float(v.strip()) if '.' in v else int(v.strip()) for v in field.text().split(',')]
            except ValueError:raise ValueError('候选值应为逗号分隔的数字，例如 5,10,15') from None
            result[key]=values
        return result

    def edit_grid(self):
        raw=json.dumps(self.parameter_grid(),ensure_ascii=False)
        text,ok=W.QInputDialog.getMultiLineText(self,'更多扫描参数','输入参数名及候选值列表',raw)
        if ok:
            body=json.loads(text)
            if not isinstance(body,dict) or not body:raise ValueError('参数应为非空对象')
            self.grid.setText(text);self.grid_override=True
            self.update_scan_context()

    def refresh_experiments(self,*args):
        selected=self.selected_experiments(required=False)
        records=self.service.store.experiment_summaries()
        query=self.experiment_search.text().casefold()
        rows=[{'id':r['id'],'name':r['name'],'symbol':r['symbol'],**r['summary'],
               'fast':r['strategy']['fast'],'slow':r['strategy']['slow'],'updated_at':r['updated_at']} for r in records
               if query in (r['name']+' '+r['symbol']).casefold()]
        rows.sort(key=lambda r:r['return_pct'],reverse=True)
        self.experiments.setSortingEnabled(False)
        populate(self.experiments,rows,['name','symbol','start','end','return_pct','max_drawdown_pct','sharpe','win_rate_pct','trades'])
        self.experiments.setSortingEnabled(True)
        self.experiments.sortByColumn(4,QtCore.Qt.SortOrder.DescendingOrder)
        self.experiments.horizontalHeader().setSectionResizeMode(0,W.QHeaderView.ResizeMode.Stretch)
        self.experiments.selectionModel().selectionChanged.connect(self.selection_overlay)
        self.select_experiments(selected)

    def select_experiments(self,ids):
        selection=self.experiments.selectionModel()
        selection.blockSignals(True)
        selection.clearSelection()
        for i,row in enumerate(self.experiments.model().rows):
            if row['id'] in ids:
                selection.select(self.experiments.model().index(i,0),QtCore.QItemSelectionModel.SelectionFlag.Select|QtCore.QItemSelectionModel.SelectionFlag.Rows)
        selection.blockSignals(False)
        self.selection_overlay()

    def selected_experiments(self,required=True):
        selected=self.experiments.selectionModel().selectedRows() if self.experiments.model() else []
        if not selected and required:raise ValueError('请先选择实验；点击行可多选')
        return [self.experiments.model().rows[i.row()]['id'] for i in selected]

    def load_experiment(self):
        ids=self.selected_experiments()
        if len(ids)!=1:raise ValueError('载入完整结果时请选择一个实验')
        self.show_result({'id':ids[0],**self.service.store.load(ids[0])['body']})

    def selection_overlay(self,*args):
        ids=self.selected_experiments(required=False)
        if not ids:
            self.comparison_ids=[];self.comparison_stack.setCurrentIndex(0)
            for row in self.experiments.model().rows:row['_curve_color']=None
            self.experiments.viewport().update()
            self.comparison_hint.setText('选择实验即可叠加收益曲线；点击行可多选，双击载入完整结果。')
            return
        try:self.draw_overlay(ids)
        except ValueError as exc:
            self.comparison_ids=[];self.comparison_stack.setCurrentIndex(0)
            self.comparison_hint.setText(str(exc))

    def overlay(self):self.draw_overlay(self.selected_experiments())

    def draw_overlay(self,ids):
        results=[self.service.store.load(i) for i in ids]
        if len(results)>20:raise ValueError('一次最多叠加 20 个实验，请减少选择。')
        signatures={(r['body']['dataset']['metadata']['sha256'],r['body']['summary']['start'],r['body']['summary']['end']) for r in results}
        if len(signatures)>1:raise ValueError('所选实验的数据或区间不同。请使用参数研究或策略比较生成同区间结果。')
        self.comparison_ids=ids;self.comparison_stack.setCurrentIndex(1)
        self.comparison.clear();self.comparison.plotItem.legend.clear()
        colors=LIGHT_COLORS if self.colors is LIGHT else COLORS
        for row in self.experiments.model().rows:
            row['_curve_color']=colors[ids.index(row['id'])%len(colors)] if row['id'] in ids else None
        self.experiments.viewport().update()
        for i,doc in enumerate(results):
            curve=doc['body']['curve']
            style=QtCore.Qt.PenStyle.SolidLine if i<len(colors) else QtCore.Qt.PenStyle.DashLine
            self.comparison.plot([timestamp(r['date']) for r in curve],[r['return_pct'] for r in curve],pen=pg.mkPen(colors[i%len(colors)],width=1.7,style=style))
        self.comparison.enableAutoRange()
        self.status.setText(f'已选择 {len(ids)} 个同区间实验 · {results[0]["body"]["summary"]["start"]} — {results[0]["body"]["summary"]["end"]}')

    def batch_done(self,results):
        self.experiment_search.clear();self.refresh_experiments()
        self.select_experiments([r['id'] for r in results[:20]])
        self.nav.setCurrentRow(4)
        self.status.setText(f'已完成并保存 {len(results)} 个实验；已叠加前 {min(len(results),20)} 条曲线')

    def tune(self):
        ds=self.backtest_data.currentData()
        if not ds:raise ValueError('请先导入行情并在回测页选择数据')
        strategy,settings,grid=self.definition(),self.current_config(),self.parameter_grid()
        self.start_job('正在运行参数网格…',lambda cancel,progress:self.service.tune(ds,strategy,settings,grid,cancel,progress),self.batch_done)

    def compare_saved(self):
        ds=self.backtest_data.currentData()
        if not ds:raise ValueError('请先选择行情数据')
        settings=self.current_config()
        strategies=[d['body'] for d in self.service.store.documents('strategy')]
        if not strategies:raise ValueError('尚无已保存策略。请到策略管理保存需要比较的策略。')
        self.start_job('正在比较策略…',lambda cancel,progress:self.service.compare(ds,strategies,settings,cancel,progress),self.batch_done)

    def export_comparison(self):
        import csv
        path,_=W.QFileDialog.getSaveFileName(self,'导出比较','comparison.csv','CSV (*.csv)')
        if path:
            model=self.experiments.model()
            with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,['name','symbol','start','end','fast','slow','return_pct','annualized_return_pct','max_drawdown_pct','sharpe','win_rate_pct','profit_loss_ratio','trades','updated_at'],extrasaction='ignore')
                writer.writeheader()
                writer.writerows(model.rows)

    def import_report(self):
        path,_=W.QFileDialog.getOpenFileName(self,'导入实验报告','','JSON (*.json)')
        if not path:return
        from .reports import read_report
        body=read_report(path)
        self.service.store.save('experiment',Path(path).stem+' · 导入',body)
        self.refresh_experiments()

    def delete_experiments(self):
        ids=self.selected_experiments()
        if W.QMessageBox.question(self,'删除实验',f'删除 {len(ids)} 个实验？')==W.QMessageBox.StandardButton.Yes:
            for ident in ids:self.service.store.delete(ident)
            self.refresh_experiments()

    def build_logs(self):
        layout=self.page('任务日志','查看数据请求、清洗、回测和失败详情。记录保存在本机数据库。')
        bar=W.QHBoxLayout()
        self.log_filter=W.QComboBox();self.log_filter.addItems(['全部记录','INFO','ERROR'])
        self.log_filter.currentIndexChanged.connect(self.refresh_logs)
        bar.addWidget(self.log_filter);bar.addWidget(self.button('刷新日志',self.refresh_logs));bar.addStretch()
        layout.addLayout(bar)
        self.logs_table=table()
        layout.addWidget(self.logs_table,1)
        self.log_detail=W.QPlainTextEdit()
        self.log_detail.setReadOnly(True)
        self.log_detail.setPlaceholderText('选择一条记录查看详细信息')
        self.log_detail.setMaximumHeight(230)
        layout.addWidget(self.log_detail)
        self.logs_table.clicked.connect(lambda index:self.log_detail.setPlainText(self.logs_table.model().rows[index.row()].get('detail','')))
        layout.addWidget(W.QLabel(f'本机数据目录：{self.service.store.home}'))

    def refresh_logs(self,*args):
        level=self.log_filter.currentText()
        records=[r for r in self.service.store.logs() if level=='全部记录' or r['level']==level]
        populate(self.logs_table,records,['created_at','level','message'])
        self.logs_table.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeMode.Interactive)
        self.logs_table.setColumnWidth(0,165);self.logs_table.setColumnWidth(1,80)
        self.logs_table.horizontalHeader().setSectionResizeMode(2,W.QHeaderView.ResizeMode.Stretch)
        self.log_detail.clear()

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
        self.dataset_context_changed()


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify',metavar='DIRECTORY',help='运行真实样本桌面验收并写入报告后退出')
    args=parser.parse_args()
    app=W.QApplication(sys.argv)
    app.setApplicationName('QuantDesk')
    app.setOrganizationName('QuantDesk')
    window=Window()
    window.showNormal()
    if args.verify:
        from .verify import schedule
        schedule(app,window,args.verify)
    return app.exec()

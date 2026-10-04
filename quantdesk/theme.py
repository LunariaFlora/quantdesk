"""One palette for native widgets and charts, independent of Windows app theme."""
DARK={'bg':'#101722','panel':'#172131','raised':'#1d2a3d','nav':'#0c131d','text':'#e3ebf7','muted':'#a0afc4','border':'#2c3a50','accent':'#7da6ff','positive':'#50d2aa','negative':'#ff8793','selection':'#2c456b'}
LIGHT={'bg':'#eef2f7','panel':'#ffffff','raised':'#f3f6fa','nav':'#e5ebf3','text':'#1a2c43','muted':'#52647a','border':'#cbd5e3','accent':'#2158ba','positive':'#08745a','negative':'#b62f44','selection':'#d9e7fc'}


def stylesheet(p):
    return '''
QWidget {font-family:"Microsoft YaHei";font-size:12px;color:TEXT;background:BG;}
QWidget[panel="true"],QGroupBox {background:PANEL;border:1px solid BORDER;border-radius:5px;}
QGroupBox {margin-top:12px;padding:12px 10px 8px;}
QGroupBox::title {subcontrol-origin:margin;left:10px;padding:0 4px;color:MUTED;}
QLabel {background:transparent;border:none;}
QLabel[title="true"] {font-size:19px;font-weight:600;}
QLabel[muted="true"] {color:MUTED;}
QLabel[metric="true"] {font-family:"Consolas";font-size:22px;font-weight:600;}
QPushButton,QToolButton {background:RAISED;border:1px solid BORDER;border-radius:4px;padding:5px 10px;min-height:19px;}
QPushButton:hover,QToolButton:hover {border-color:ACCENT;background:SELECTION;}
QPushButton:disabled,QToolButton:disabled {color:MUTED;background:PANEL;}
QPushButton[primary="true"] {background:#3665c9;color:#ffffff;border:1px solid #5280e1;font-weight:600;}
QPushButton[primary="true"]:disabled {background:RAISED;color:MUTED;border-color:BORDER;}
QPushButton[danger="true"] {color:NEGATIVE;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit {background:PANEL;border:1px solid BORDER;border-radius:3px;padding:4px 6px;selection-background-color:SELECTION;}
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus {border-color:ACCENT;}
QComboBox::drop-down {border:0;width:18px;}
QComboBox QAbstractItemView {background:PANEL;selection-background-color:SELECTION;color:TEXT;}
QTableView {background:PANEL;alternate-background-color:RAISED;border:1px solid BORDER;gridline-color:BORDER;selection-background-color:SELECTION;selection-color:TEXT;}
QHeaderView {background:RAISED;}
QHeaderView::section {background:RAISED;color:MUTED;padding:5px 6px;border:0;border-bottom:1px solid BORDER;}
QTableView QTableCornerButton::section {background:RAISED;border:0;}
QTabWidget::pane {border:1px solid BORDER;background:PANEL;}
QTabBar::tab {padding:7px 12px;background:BG;color:MUTED;border-bottom:2px solid transparent;}
QTabBar::tab:selected {background:PANEL;color:TEXT;border-bottom-color:ACCENT;}
QListWidget {background:NAV;border:0;border-right:1px solid BORDER;outline:0;padding:8px;}
QListWidget::item {padding:11px 9px;margin:2px 0;border-radius:4px;color:MUTED;}
QListWidget::item:selected {background:SELECTION;color:TEXT;font-weight:600;}
QListWidget::item:hover {background:RAISED;}
QScrollArea {border:0;background:BG;}
QScrollArea>QWidget>QWidget {background:BG;}
QSplitter::handle {background:BG;}
QSplitter::handle:horizontal {width:5px;}
QSplitter::handle:vertical {height:5px;}
QScrollBar:vertical {background:BG;width:9px;margin:0;}
QScrollBar:horizontal {background:BG;height:9px;margin:0;}
QScrollBar::handle {background:BORDER;border-radius:4px;min-height:22px;min-width:22px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QStatusBar {background:NAV;border-top:1px solid BORDER;min-height:30px;}
QStatusBar::item {border:0;}
QProgressBar {border:1px solid BORDER;border-radius:3px;text-align:center;background:PANEL;}
QProgressBar::chunk {background:ACCENT;}
QCheckBox {background:transparent;spacing:6px;}
QToolTip {background:RAISED;color:TEXT;border:1px solid BORDER;padding:5px;}
'''.replace('SELECTION',p['selection']).replace('NEGATIVE',p['negative']).replace('ACCENT',p['accent']).replace('BORDER',p['border']).replace('PANEL',p['panel']).replace('RAISED',p['raised']).replace('MUTED',p['muted']).replace('TEXT',p['text']).replace('NAV',p['nav']).replace('BG',p['bg'])

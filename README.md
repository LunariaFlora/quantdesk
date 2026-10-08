# 观澜 · 量化研究桌面工作台

Windows 原生应用。导入和获取真实历史日线、管理策略、执行事件回测、核对账户账本、研究参数并比较结果。正式应用直接调用 Python 服务和 SQLite，不启动 HTTP 服务，不依赖本地端口。

第一次使用请看 [快速上手](docs/quickstart.md)；给老师或其他电脑发送项目请看 [交付与目录说明](docs/delivery.md)。应用 ZIP 和源码 ZIP 分开生成，不需要发送整个开发目录。

浏览器演示见 [HTML 演示说明](demo/README.md)：单个离线 HTML 展示八组包内历史行情、三个固定策略、六步操作导览和真实报告导出，无需启动 EXE。

## 直接打开

双击 `dist/QuantDesk/QuantDesk.exe`，或运行 `启动.ps1`。保留同目录的 `_internal` 文件夹。打包版本不需要另行安装 Python。

首次启动载入并选中公开 AAPL 历史样本（2015-02-17 至 2017-02-16，506 根真实日线），直接显示 K 线。在“行情数据”中选择 Yahoo、其他来源或导入 CSV；选择固定样本来源会填入其覆盖日期。

未运行回测时，行情页与回测页显示真实价格概览：最近一年 K 线、MA20/MA60、成交量、最新历史收盘及日涨跌/可见区间涨跌。可切换三个月、半年或全部数据；行情数字不代表策略回测结果。启动使用普通居中窗口，首选尺寸不超过 1280×800，并根据显示器可用空间缩小。

数据、策略、配置、实验和日志保存于 `%LOCALAPPDATA%/QuantDesk/library.sqlite3`。环境变量 `QUANTDESK_HOME` 可改用独立目录。备份前关闭程序，再复制该目录。

## 从源码运行与打包

已在 Windows 11 / Python 3.13.9 验证；建议 Python 3.11–3.13。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe download_data.py
.venv/Scripts/python.exe desktop.py
```

打包运行 `powershell -NoProfile -ExecutionPolicy Bypass -File 打包.ps1`。依赖版本固定，dist、build、数据库和行情文件被 Git 忽略。

## 使用顺序

1. 行情数据：获取或导入 CSV，查看来源、哈希、清洗报告；查询日期、查看 K 线、导出行情。
2. 策略管理：选择双均线、EMA、RSI、布林带、MACD、通道突破、买入持有或自定义规则模板。常用参数用表单修改，自定义规则进入“规则 JSON”；支持保存、载入、另存和更新。
3. 回测研究：直接选择策略、修改周期，设置本金、费用、滑点和仓位；展开风控设置可配置止盈止损、交易单位和容量。运行与导出按钮固定在底部。图表显示价格/成交、成交量或指标、资产/基准与回撤；双击成交定位日期。修改参数后提示旧结果尚未更新；载入实验恢复当时配置。
4. 实验与比较：选择扫描参数并填写逗号分隔的候选值；参数研究自动统一交易起点，完成后自动选中并叠加最多 20 条新曲线。保存策略可批量比较。点击列头排序，点击行多选、双击载入；名称前色块对应曲线。数据哈希和区间不同的实验显示原因并停止叠加。
5. 导出结果：生成 report.json 和 summary、trades、orders、round_trips、equity 五份 CSV。报告可重新导入实验库。
6. 任务日志：查看失败和诊断。下载、回测和调参在后台执行，可取消；网络取消需等当前请求返回或超时。

策略编辑使用明确的 JSON 规则。entry/exit 各支持 1–10 条 AND 条件；支持指标/数值比较及交叉，不执行任意用户 Python。参见 `quantdesk/strategies.py` 的 custom 模板。

状态栏可切换深浅色，选择保存在本机 `ui.ini`。最小窗口为 1060×680；1280×720 和最小尺寸均检查运行/导出按钮可见、图表不重叠、日期域一致。普通文本与盈亏文字在对应背景的对比度至少 4.5:1。

## 数据与计算口径

CSV 包含 `date,open,high,low,close,volume`，支持常见中文列名和 AAPL.Open 格式。日期 YYYY-MM-DD，检查 OHLC 范围、有限正价格和非负成交量，最多 250,000 行。重复保留规则和丢弃坏行需明确选择；不补造交易日、不填充价格。

收盘信号下一日开盘执行。预热用开始日期之前的数据，不够时拒绝。仅做多、单标的、无杠杆，整数交易单位。费用按金额比例，买卖分别施加不利滑点；零成交量不成交，容量不足整笔拒绝。期末持仓按收盘估值，不假设清仓。

止盈止损按日线模拟，跳空按开盘，同日双触发优先止损；买入当日保护生效。日线不能恢复日内路径，保护成交仍受容量限制。

账户资产 = 现金 + 持仓 × 收盘价；盈亏 = 已实现 + 未实现。回撤从含本金的历史峰值计算。年化收益为自然日 CAGR；夏普用日收益样本标准差和配置的年交易日数；胜率/盈亏比按已平仓交易计算。无有效分母显示“—”。具体定义写入报告。

不模拟分红、企业行动现金调整、税费、最低佣金、涨跌停、T+1、交易所日历或多资产共享资金。Yahoo 原始 OHLC 和导入 CSV 须核对复权口径；本版不是完整 A 股或实盘经纪商。

## 验证与参考

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
$env:QUANTDESK_HOME="$PWD/outputs/acceptance-home"
dist/QuantDesk/QuantDesk.exe --verify outputs/acceptance
```

验收命令实际运行原生后台回测、8 策略比较、9 组调参、持久化恢复、查询和导出，生成界面截图与 JSON 证据。测试数据目录建议独立。Backtrader 对照测试核对真实样本的成交和逐日现金、持仓、资产；仅对齐双 SMA、无滑点、比例佣金配置，不代表所有保护规则等价。

- `学习清单.txt`：六次独立学习安排和官方教程。
- `docs/desktop-plan.md`：全范围验收账本。
- `docs/platform-comparison.md`：成熟工具对照、改进及差异。
- `docs/ui-review.md`：实际 EXE 的九项界面评审、任务模拟与改进证据。
- `docs/market-data.md`：行情获取方式、当前已导入数据及价格口径。

旧 server.py 与 web 目录仅用于历史网页开发预览，`python server.py` 后使用 127.0.0.1:8765。正式桌面启动和打包不调用它。

# 观澜 · 量化研究桌面工作台

Windows 原生应用。导入和获取真实历史日线、管理策略、执行事件回测、核对账户账本、研究参数并比较结果。正式应用直接调用 Python 服务和 SQLite，不启动 HTTP 服务，不依赖本地端口。

## 直接打开

双击 `dist/QuantDesk/QuantDesk.exe`，或运行 `启动.ps1`。保留同目录的 `_internal` 文件夹。打包版本不需要另行安装 Python。

首次启动载入公开 AAPL 历史样本（2015-02-17 至 2017-02-16，506 根真实日线）。在“行情数据”中选择 Yahoo、其他来源或导入 CSV。固定样本按钮需将日期设在样本覆盖范围内。

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
2. 策略管理：选择双均线、EMA、RSI、布林带、MACD、通道突破、买入持有或自定义规则模板。修改 JSON，保存、载入、复制或更新。
3. 回测研究：设置本金、费用、滑点、仓位、止盈止损、交易单位和容量。查看图表、订单、成交、每日现金/持仓/盈亏、已平仓交易和指标。
4. 实验与比较：参数网格自动统一交易起点；保存策略可批量比较。点击列头排序，Ctrl 多选叠加曲线。数据哈希和区间不同的实验不能叠加。
5. 导出结果：生成 report.json 和 summary、trades、orders、round_trips、equity 五份 CSV。报告可重新导入实验库。
6. 任务日志：查看失败和诊断。下载、回测和调参在后台执行，可取消；网络取消需等当前请求返回或超时。

策略编辑使用明确的 JSON 规则。entry/exit 各支持 1–10 条 AND 条件；支持指标/数值比较及交叉，不执行任意用户 Python。参见 `quantdesk/strategies.py` 的 custom 模板。

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

旧 server.py 与 web 目录仅用于历史网页开发预览，`python server.py` 后使用 127.0.0.1:8765。正式桌面启动和打包不调用它。

# 桌面应用目标与验收账本

2026-10-04。基线 759b00f，原工作树干净。当前请求明确扩大范围，以完整桌面研究应用为目标。

## 结构

原生 Qt Widgets → 直接 Python 应用服务 → 数据适配器 / 策略 / 回测 / SQLite。
正式入口 desktop.py 或打包 EXE，不启动 HTTP，不依赖浏览器或本地端口。
旧 server.py 只保留为历史网页开发预览。
用户数据库、日志、结果位于 LOCALAPPDATA/QuantDesk，可用 QUANTDESK_HOME 指定独立目录。

## 阶段

1. SQLite 数据库、真实历史数据适配器、显式清洗、查询、保存；验证后提交。
2. 多策略、指标、事件账本、止盈止损、仓位与成本、评估指标；验证后提交。
3. 原生数据中心、策略编辑、回测图表、实验库、参数比较、导出、后台任务与日志；验证后提交。
4. Windows EXE、真实数据端到端验收、无端口验证、成熟工具对照与改进；验证后提交。

## 全范围验收

每项必须有代码和运行证据，不能因为 UI 出现一个按钮就判为完成。

| 要求 | 需要的证据 | 当前状态 |
|---|---|---|
| 无本地端口的桌面应用 | 原生窗口运行，进程无 LISTENING socket，打包启动 | 原生测试通过；EXE 验收报告与最终 socket 采样见 outputs |
| 真实行情获取与导入 | 在线获取、CSV 导入、供应商与哈希记录 | Yahoo 1508 根新下载行情与公开 506 行样本通过，Stooq 失败已记录 |
| 清洗、持久化、查询 | 脏数据策略、事务、重启恢复、日期查询 | test_library + 原生/打包验收通过 |
| 定义管理策略 | 多策略模板、自定义规则、保存/更新/载入 | 8 类模板、自定义 AND 条件；test_research + test_desktop |
| 指标与分析 | SMA/EMA/RSI/MACD/ATR/布林带等独立计算 | 指标测试与 6 类图形切换通过 |
| 回测账本 | 信号到成交时序、现金持仓、订单与成交、费用核算 | 手算 + Backtrader 独立对照 + 11,784 条真实账户记录通过 |
| 完整绩效 | 累计/年化/回撤/夏普/胜率/盈亏比/频率可复算 | test_metrics_reference；公式和未定义值写入报告 |
| 图表 | K线、指标、权益、回撤与买卖标记，实际截图 | native-backtest.png、packaged-final/desktop.png 和 comparison.png |
| 风控与配置 | 手续费/滑点/仓位/止盈止损的独立测试 | 手算、双触发、跳空、容量和配置恢复通过 |
| 调参与跨策略比较 | 统一交易期、多个配置结果、指标表与叠加曲线 | 打包 8 策略/9 组；源码 100 组约 3.25s；统一日期测试 |
| 保存/载入/导出 | 数据集、策略、配置、实验恢复，JSON/CSV | tests/test_desktop + 打包验收；JSON 和五份 CSV |
| 状态反馈与日志 | 后台执行、错误展示、持久日志与诊断 | UI 线程回调测试、后台取消、供应商失败日志 |
| 成熟工具对比改进 | 功能/流程/UX/图表/可靠性/性能/架构系统评估 | platform-comparison.md 七维对照、十项已实施改进及实测边界 |

## 初步参考

- [VeighNa](https://github.com/vnpy/vnpy)：参考独立数据管理、回测、风险和原生桌面模块分工。
- [Backtrader](https://www.backtrader.com/docu/)：参考策略/指标/经纪模拟分层及下一根 bar 执行。
- [LEAN](https://github.com/QuantConnect/Lean)：参考事件时间和订单生命周期，避免前视。
- [vectorbt](https://vectorbt.dev/)：参考参数研究与结果比较；后续需实测性能，不能宣称等价速度。
- [Qt Widgets](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/index.html)：正式原生窗口实现。

2026-10-05：各项研究桌面功能已实现并逐项验收。具体运行证据及范围差异见 platform-comparison.md；不把这些结论扩展到实盘、多资产资金共享或完整交易所规则。

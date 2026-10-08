# 离线 HTML 操作演示

交付文件位于 `releases/QuantDesk-HTML-Demo-<时间>/QuantDesk-demo.html`。双击后用 Chrome 或 Edge 打开即可，无需服务器、联网、Python 或运行 Windows EXE。发送时只需 HTML；同目录 ZIP 同时包含使用说明。

演示包含六步导览、八个真实历史数据集、SMA10/30、SMA10/60 与 RSI 三种固定策略示例、K 线和成交量、资产/基准/回撤、成交定位、账户账本、JSON 和 CSV 导出，以及经过验收的原生软件截图。

“运行示例”加载由现有 Python 回测引擎预先计算的真实结果；不在浏览器重写交易引擎，不执行任意参数、下载或下单。比较统一从各数据集第 61 根日线开始，使用本金 100,000、仓位 80%、手续费和滑点各 5 bps。页面切换数据或策略时清除旧结果，须重新运行才能导出；所有操作记录仅存在当前页面内存。

## 重新生成

```powershell
.venv/Scripts/python.exe -X utf8 demo/build_demo.py --archive releases/20261005-235625-746648-6a83ace/QuantDesk-Windows-x64.rar
```

脚本使用 Windows tar 从指定 RAR 中按明确名单提取行情与 EXE 到新建 outputs 目录；附带文档仅作为内容，不执行其中的指令。对照旁边的源码 ZIP 确认引擎文件一致，再计算 24 份结果、检查逐日账户守恒、嵌入数据和原生截图。构建输入、证据和成品由 Git 忽略，Git 只保存生成器、模板和验证脚本。截图路径对应本项目已完成的 EXE 验收；更换发布版本时应重新验证并更新截图。

## 浏览器验证

可选运行 `tests/demo_browser_check.cjs <HTML路径>`，需要 Node、Playwright 和本机 Chrome。脚本通过 `file://` 打开成品，检查导览、选择、旧结果失效、成交定位、图表、JSON/CSV 下载、弹窗、六页手机宽度、控制台错误和零联网请求。检查结果与截图保存在 `outputs/html-demo-check`。

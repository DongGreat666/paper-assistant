# Scripts

- `browser/`：基于 Playwright 的 RIS 下载工具，不属于应用运行流程。
- `dev/`：实验性或旧版开发脚本，不属于应用运行流程；其中部分脚本可能依赖已移除的实验 API。
- `maintenance/`：Markdown 修复、日志维护和受控启动工具。
- `windows/`：Windows 快捷方式等系统辅助脚本。

所有脚本均以项目根目录为基准解析路径，可从项目根目录直接调用。

请勿将浏览器自动化实验依赖安装到 Paper Assistant 的主虚拟环境中。

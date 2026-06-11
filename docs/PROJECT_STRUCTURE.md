# 项目结构与功能映射

本文面向开发者，说明 Paper Assistant 的目录职责、关键文件和应用功能对应关系。

## 目录树

```text
paper-assistant/
├── assets/                         已构建并由应用直接提供的静态资源
│   └── pdf-reader/                 PDF 阅读器生产构建
├── data/                           本地设置、模型配置、历史记录和缓存
│   ├── cache/
│   ├── chat_history/
│   └── vector_db/
├── docs/                           项目文档与开发记录
│   └── notes/                      专项问题分析记录
├── models/                         Marker PDF 解析模型缓存
├── MyPapers/                       本地论文、解析结果、译文和导出文件
├── paper_assistant/                Reflex 应用入口与路由注册
├── pdf-reader/                     React PDF 阅读器前端源码
│   ├── public/                     阅读器公共静态资源
│   └── src/                        阅读器交互逻辑、样式和桥接代码
├── scripts/                        独立工具脚本
│   ├── browser/                    浏览器自动化与 RIS 下载
│   ├── dev/                        实验性或旧版开发脚本
│   ├── maintenance/                Markdown 修复与日志维护
│   └── windows/                    Windows 快捷方式工具
├── src/                            Python 应用源码
│   ├── core/                       与 UI 无关的核心业务逻辑
│   ├── ui/                         Reflex 页面、状态和组件
│   │   ├── components/             通用布局组件
│   │   └── pages/                  各业务页面及其服务
│   └── utils/                      通用辅助模块
├── .env                            本机密钥与运行配置，不提交
├── .env.example                    可公开的环境变量模板
├── config.py                       配置读取、覆盖和本地目录初始化
├── paths.py                        项目根目录与模型缓存路径
├── requirements.txt                Python 依赖
├── rxconfig.py                     Reflex 配置
└── start.bat                       Windows 一键启动入口
```

## 功能与代码对应

| 应用功能 | 页面与状态 | 核心逻辑 | 前端或数据 |
|---|---|---|---|
| 首页聊天与文档问答 | `src/ui/pages/home*.py` | `src/core/chat_engine.py`、`chat_history.py`、`engine.py` | `data/chat_history/` |
| 论文库与 PDF 阅读 | `src/ui/pages/library.py`、`library_ui.py` | `src/core/pdf_annotations.py`、`chat_engine.py` | `pdf-reader/`、`assets/pdf-reader/`、`MyPapers/` |
| PDF 高亮、划线和批注 | `src/ui/pages/library.py` | `src/core/pdf_annotations.py` | `pdf-reader/src/App.tsx` |
| 选区解释、翻译与右侧问答 | `src/ui/pages/library.py`、`library_ui.py` | `src/core/chat_engine.py`、`engine.py` | `pdf-reader/src/App.tsx`、`bridge.ts` |
| PDF 解析为 Markdown | `src/ui/pages/translate.py` | `src/core/document_parser.py`、`markdown_repair.py` | `models/`、`MyPapers/` |
| 整篇翻译 | `src/ui/pages/translate.py` | `src/core/translator.py`、`engine.py` | `data/translation_engines.json` |
| Markdown/PDF/简洁版导出 | `src/ui/pages/translate.py` | `src/core/exporter.py`、`pdf_translation.py` | `MyPapers/` |
| 模型和存储设置 | `src/ui/pages/settings.py`、`home_model_*.py` | `config.py`、`src/core/engine.py` | `.env`、`data/*.json` |

## 关键目录说明

### `paper_assistant/`

Reflex 应用入口。`paper_assistant.py` 注册页面路由、PDF 文件服务和批注读取 API。新增页面或后端 HTTP 路由时，从这里接入。

### `src/core/`

业务能力集中区，不依赖具体页面布局：

- `chat_engine.py`：提取 PDF 文本并构造论文上下文问答。
- `chat_history.py`：保存、读取和删除聊天记录。
- `document_parser.py`：调用 Marker 将 PDF 解析为 Markdown，并保存图片资源。
- `engine.py`：模型接口配置、密钥引用和翻译/问答引擎构造。
- `exporter.py`：Markdown 展示格式、简洁版和 PDF 导出。
- `markdown_repair.py`：解析后 Markdown 的标题层级修复。
- `pdf_annotations.py`：直接读写 PDF 高亮、划线、删除线和批注。
- `pdf_translation.py`：PDF 翻译相关处理。
- `translator.py`：Markdown 分段、模型翻译、结构校验和双语合并。

### `src/ui/`

Reflex 用户界面：

- `components/layout.py`：应用外壳、侧栏和通用布局。
- `pages/home*.py`：首页聊天、上传和模型选择。
- `pages/library.py`：论文库状态、PDF 事件和业务动作。
- `pages/library_ui.py`：论文库、阅读器和右侧功能面板界面。
- `pages/translate.py`：解析、整篇翻译、预览和下载页面。
- `pages/settings.py`：模型、存储和外观设置。

### `pdf-reader/` 与 `assets/pdf-reader/`

`pdf-reader/` 是 React/Vite 源码，负责 PDF 渲染、选区、批注工具栏、问答联动和与 Reflex 的消息桥接。

`assets/pdf-reader/` 是构建后的生产资源，Python 应用实际加载这里的文件。修改阅读器源码后需要执行 `npm run build` 更新生产资源。

### `data/`

本机运行配置和历史数据。可能包含密钥引用或用户内容，不应提交：

- `settings.json`：用户设置。
- `translation_engines.json`、`chat_engines.json`：模型接口配置。
- `secrets.json`：本地密钥数据。
- `chat_history/`：聊天记录。
- `cache/`、`vector_db/`：缓存和向量数据。

### `models/`

Marker 使用的本地模型缓存。体积较大，但 PDF 解析依赖它；删除后需要重新下载模型。

### `MyPapers/`

论文工作区。每篇论文通常拥有独立文件夹，包含原始 PDF、解析 Markdown、图片、译文和导出文件。它是用户数据，不属于可随意清理的构建缓存。

### `scripts/`

不参与应用常规启动流程的独立工具。具体用途见 [`scripts/README.md`](../scripts/README.md)。

## 运行时生成目录

这些目录可能在启动或工具运行后重新出现：

```text
.web/                   Reflex 自动生成前端
.states/                Reflex 本地状态
logs/                   运行日志
artifacts/              调试截图和实验产物
pdf-reader/node_modules 前端依赖
```

它们均可重新生成，但删除 `pdf-reader/node_modules/` 后需要重新执行 `npm ci` 才能构建阅读器。

## 修改功能时从哪里开始

- 修改阅读器交互：先看 `pdf-reader/src/App.tsx`，再看 `src/ui/pages/library.py`。
- 修改论文问答：先看 `src/core/chat_engine.py` 和 `src/ui/pages/library.py`。
- 修改整篇翻译：先看 `src/ui/pages/translate.py` 和 `src/core/translator.py`。
- 修改 PDF 解析：先看 `src/core/document_parser.py` 和 `src/core/markdown_repair.py`。
- 修改导出格式：先看 `src/core/exporter.py`。
- 修改模型配置：先看 `src/core/engine.py`、`config.py` 和设置页面。

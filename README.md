# Paper Assistant

Paper Assistant 是一个本地论文阅读工作台，围绕论文导入、PDF 阅读、批注、问答和整篇翻译组织完整工作流。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Reflex](https://img.shields.io/badge/Framework-Reflex-purple.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

> [!WARNING]
> Paper Assistant 当前设计为单用户本地应用，请勿直接暴露到公网。
> 项目尚未提供登录鉴权、用户数据隔离、上传配额、任务资源隔离和生产级密钥托管。
> 详细说明见 [安全策略](SECURITY.md)。

## 应用功能

- **论文库**：导入、分组、重命名和管理本地 PDF。
- **PDF 阅读器**：缩放、框选、划线、高亮、删除线和文字批注。
- **论文问答**：基于当前论文全文提问，并保留连续对话记录。
- **选区解释与翻译**：框选图片或文字后解释、翻译，并与右侧问答联动。
- **整篇翻译**：将 PDF 解析为 Markdown，修复标题结构，调用模型翻译并预览结果。
- **译文导出**：下载 Markdown、PDF 和去除图表及参考文献的简洁版。
- **多模型配置**：分别配置翻译模型和问答模型，支持 OpenAI 兼容接口。

## 快速启动

### 前置要求

- Python 3.10+
- Node.js 20.19+ 或 22.12+
- Git

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/DongGreat666/paper-assistant.git
cd paper-assistant

# 2. 创建项目专用虚拟环境
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# CMD: .venv\Scripts\activate.bat
# source .venv/bin/activate  # Linux/Mac

# 3. 安装依赖
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd pdf-reader && npm ci && cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API keys

# 5. 启动应用
start.bat
```

应用默认地址为 <http://localhost:3000/>。

项目依赖必须安装在 `.venv` 中。请勿将无关自动化依赖安装到 Paper
Assistant 环境，否则可能破坏 Marker 的依赖版本。

详细安装步骤见 [快速开始指南](docs/QUICKSTART.md)，完整开发文档见 [开发指南](docs/DEVELOPMENT.md)。

## 项目导航

- [项目结构与功能映射](docs/PROJECT_STRUCTURE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [项目设计概要](docs/PROJECT_SUMMARY.md)
- [脚本说明](scripts/README.md)
- [安全策略](SECURITY.md)

## 本地数据

以下目录用于本地运行，不提交到 Git：

- `data/`：设置、模型接口配置、密钥引用和聊天记录。
- `models/`：Marker PDF 解析模型。
- `MyPapers/`：导入的论文、解析结果和译文；每篇论文及其生成文件保存在同一文件夹。
- `.web/`：Reflex 自动生成的前端缓存。

日常清理时不要删除 `models/` 和 `MyPapers/`。

## 第三方 PDF 解析器

整篇 PDF 解析使用第三方开源项目
[Marker](https://github.com/datalab-to/marker)。Marker 源码、安装包和模型权重
均不包含在本仓库中：

- 安装项目依赖时，`marker-pdf` 从 [PyPI](https://pypi.org/project/marker-pdf/) 下载。
- Marker 模型在首次解析时下载到本地 `models/`，该目录已被 Git 忽略。

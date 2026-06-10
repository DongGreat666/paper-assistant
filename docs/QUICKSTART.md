# 快速开始指南

本指南帮助你在 5 分钟内启动 Paper Assistant。

> [!WARNING]
> 本项目仅用于受信任设备上的单用户本地运行。请保持服务监听在本机，
> 不要通过端口转发、反向代理或公网 IP 直接开放访问。

## 前置要求

- **Python 3.10+**
- **Node.js 20.19+ 或 22.12+**（用于 PDF 阅读器）
- **Git**

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/DongGreat666/paper-assistant.git
cd paper-assistant
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Linux/Mac
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

不要将无关自动化包安装到项目虚拟环境中。Marker 对 `openai`、
`anthropic` 和 `Pillow` 有明确的兼容版本要求。

### 3. 安装 PDF 阅读器依赖

```bash
cd pdf-reader
npm ci
cd ..
```

### 4. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，填入你的 API keys
# 至少需要设置 LLM_API_KEY
```

### 5. 启动应用

```bash
# 方式 1: 使用启动脚本（Windows）
start.bat

# 方式 2: Windows 直接运行
.venv\Scripts\reflex.exe run

# Linux/Mac
.venv/bin/reflex run
```

访问 http://localhost:3000/ 开始使用！

如需多人或公网部署，必须先实现登录鉴权、用户数据隔离、上传限制、
SSRF 防护、任务资源限制和安全的密钥托管。详见 [安全策略](../SECURITY.md)。

## 首次使用

1. **导入论文**
   - 点击"导入"按钮
   - 选择 PDF 文件
   - 等待解析完成

2. **阅读论文**
   - 点击论文进入阅读器
   - 使用工具栏进行标注
   - 框选内容进行翻译或解释

3. **论文问答**
   - 在右侧面板提问
   - 支持连续对话
   - 基于论文全文回答

4. **整篇翻译**
   - 点击"翻译"按钮
   - 选择翻译模型
   - 等待翻译完成
   - 导出 Markdown 或 PDF

## 配置说明

### 基础配置

在 `.env` 文件中配置：

```bash
# OpenAI API Key（必需）
LLM_API_KEY=sk-your-api-key-here

# API 基础 URL（可选，默认 OpenAI）
LLM_BASE_URL=https://api.openai.com/v1

# 默认模型
LLM_MODEL=gpt-4o-mini
```

### 多模型配置

支持为不同任务配置不同模型：

```bash
# 翻译模型（轻量快速）
TRANSLATE_API_KEY=
TRANSLATE_MODEL=deepseek-v4-flash

# 问答模型（强力推理）
QA_MODEL=gpt-4o

# 摘要模型（平衡性价比）
SUMMARY_MODEL=gpt-4o-mini
```

### 支持的 API 提供商

| 提供商 | Base URL | 说明 |
|--------|----------|------|
| OpenAI | `https://api.openai.com/v1` | 默认 |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | 免费额度 |
| DeepSeek | `https://api.deepseek.com/v1` | 性价比高 |
| Ollama | `http://localhost:11434/v1` | 本地部署 |

## 常见问题

### Q: 启动失败怎么办？

**A:** 检查以下几点：
1. Python 版本是否 >= 3.10
2. 是否激活了虚拟环境
3. 依赖是否安装完整
4. 端口 3000 是否被占用

### Q: PDF 解析很慢？

**A:** 首次解析会由第三方项目
[Marker](https://github.com/datalab-to/marker) 下载模型到本地 `models/`
目录（约 1GB），请耐心等待。模型不会存储在 Paper Assistant 仓库中，
后续解析会使用本地缓存。

### Q: 翻译报错？

**A:** 检查：
1. API key 是否正确
2. API 余额是否充足
3. 网络连接是否正常

### Q: 如何更换 API 提供商？

**A:** 修改 `.env` 文件中的 `LLM_BASE_URL`：
```bash
# 切换到 DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-deepseek-key
```

## 下一步

- 📖 查看 [项目结构](PROJECT_STRUCTURE.md) 了解详细架构
- 🔧 查看 [开发指南](DEVELOPMENT.md) 参与开发
- 🐛 报告问题请使用 [Issue 模板](/.github/ISSUE_TEMPLATE/)

## 获取帮助

- GitHub Issues: 项目问题讨论
- 文档: `docs/` 目录
- 示例配置: `.env.example`

祝你使用愉快！🎉

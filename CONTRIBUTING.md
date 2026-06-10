# 贡献指南

感谢你对 Paper Assistant 项目的关注！本文档说明如何参与贡献。

## 开发环境

### 前置要求

- Python 3.10+
- Node.js 20.19+ 或 22.12+ (用于 PDF 阅读器)
- Git

### 快速开始

1. **Fork 并克隆项目**
   ```bash
   git clone https://github.com/DongGreat666/paper-assistant.git
   cd paper-assistant
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   ```

3. **安装依赖**
   ```bash
   # Windows
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   # Linux/Mac
   .venv/bin/python -m pip install -r requirements.txt
   cd pdf-reader
   npm ci
   cd ..
   ```

4. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env，填入你的 API keys
   ```

5. **启动开发服务器**
   ```bash
   # Windows
   .venv\Scripts\reflex.exe run
   # Linux/Mac
   .venv/bin/reflex run
   ```

## 提交流范

### Commit 消息格式

使用语义化提交格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type):**
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具链

**示例:**
```
feat(translator): 添加 DeepSeek 翻译支持

- 集成 DeepSeek API
- 支持模型切换
- 更新配置文档

Closes #123
```

### Pull Request 流程

1. **创建特性分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **提交更改**
   ```bash
   git add .
   git commit -m "feat(scope): your message"
   ```

3. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **填写 PR 模板**
   - 说明更改内容
   - 关联相关 Issue
   - 添加截图（如涉及 UI）

## 代码规范

### Python

- 遵循 PEP 8
- 使用 type hints
- 函数/类必须有 docstring
- 使用 Black 格式化

```bash
# 格式化代码
black src/ paper_assistant/

# 检查类型
mypy src/

# 代码检查
flake8 src/
```

### TypeScript (PDF 阅读器)

- 使用 ESLint
- 使用 Prettier 格式化
- 组件使用函数式写法

```bash
cd pdf-reader
npm run lint
npm run format
```

## 报告问题

使用 [Issue 模板](/.github/ISSUE_TEMPLATE/) 报告问题，包含：

- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（OS、Python 版本等）
- 错误日志

## 功能建议

欢迎提出新功能建议！请：

1. 先搜索现有 Issues
2. 使用 Feature Request 模板
3. 说明使用场景
4. 提供实现思路（可选）

## 文档贡献

- 文档位于 `docs/` 目录
- 使用 Markdown 格式
- 保持中英文一致

## 行为准则

- 尊重所有参与者
- 接受建设性批评
- 专注于对社区最有利的事情
- 对他人表示同理心

## 许可证

贡献即表示你同意你的代码在 [MIT 许可证](LICENSE) 下发布。

## 联系方式

- GitHub Issues: 项目问题讨论
- Email: ydh2698277087@163.com

感谢你的贡献！🎉

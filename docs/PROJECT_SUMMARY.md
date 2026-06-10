# Paper Assistant 项目总结

## 一、项目定位

一个基于 AI 的文献阅读助手，核心功能：
- **文献翻译**：中英文对照阅读
- **文献分析**：总结、结构化、要点提取
- **聊天助手**：基于文献的问答和讨论（RAG 增强）

---

## 二、总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户浏览器                              │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │   首页    │ │  文献库   │ │  阅读器   │ │   设置    │     │
│  │  home.py │ │library.py│ │ reader.py│ │settings.py│    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘     │
│       │            │            │            │             │
│       └────────────┼────────────┼────────────┘             │
│                    │                                       │
│         ┌──────────┴──────────┐                           │
│         │    复用组件          │                           │
│         │  聊天框 / PDF预览等  │                           │
│         └──────────┬──────────┘                           │
└────────────────────┼───────────────────────────────────────┘
                     │
              [ Reflex / Streamlit ]
                     │
┌────────────────────┼───────────────────────────────────────┐
│                 Python 后端（同一进程）                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  src/core/                          │  │
│  │  pdf_processor  translator  rag_engine  analyzer    │  │
│  │                                         llm_client  │  │
│  └─────────────────────────────────────────────────────┘  │
│                             │                               │
│        ┌────────────────────┼────────────────────┐         │
│        ▼                    ▼                    ▼         │
│  [ Chroma / LlamaIndex ] [ 文件系统 ]      [ AI 模型 API ]  │
│    data/vector_db/       papers/           OpenAI 兼容接口  │
│                         cache/            NVIDIA NIM 等    │
└─────────────────────────────────────────────────────────────┘
```

> **核心变化**：不再分离前后端，Python 全栈框架统一处理 UI 和业务逻辑。
> 不需要手写 SSE/fetch/REST API，框架内置状态管理和响应式更新。

---

## 三、技术栈

### 框架（二选一，待定）
| 技术 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| **Reflex** | 编译为 React，交互灵活，可做复杂 UI | 生态较新，调试需理解 React | 复杂交互（拖拽、实时流式、多面板） |
| **Streamlit** | 纯 Python，上手极快，原型利器 | 复杂交互受限，布局控制弱 | 快速验证、简单 CRUD |

### 核心依赖（必需）
| 技术 | 用途 |
|------|------|
| **Python 3.10+** | 编程语言 |
| **PyMuPDF (fitz)** | PDF 文本/表格提取 |
| **ChromaDB 或 LlamaIndex** | 本地向量索引（RAG） |
| **httpx / openai** | LLM API 调用（OpenAI 兼容） |

### AI 集成
| 技术 | 用途 |
|------|------|
| **OpenAI 兼容接口** | 通用模型调用（支持 GPT、NVIDIA NIM、本地 Ollama 等） |

---

## 四、目录结构

```
LiteratureAssistant/
├── main.py                     # 程序入口（Reflex/Streamlit 启动）
├── config.py                   # 配置（文献默认文件夹、API Key、模型等）
├── requirements.txt
├── .env                        # API Key 等敏感信息
├── .gitignore
│
├── data/                       # 运行时数据
│   ├── vector_db/              # Chroma 或 LlamaIndex 本地向量索引
│   ├── chat_history/           # 可选 SQLite 存储聊天记录
│   └── cache/                  # PDF 解析缓存（可选）
│
├── src/                        # 核心代码
│   ├── __init__.py
│   │
│   ├── core/                   # 后端逻辑（纯计算，不依赖 UI）
│   │   ├── __init__.py
│   │   ├── pdf_processor.py    # PDF 解析、文本提取、段落分割
│   │   ├── translator.py       # 翻译逻辑（调 LLM）
│   │   ├── rag_engine.py       # RAG 索引构建、检索、问答
│   │   ├── analyzer.py         # 文献分析（总结、结构化、要点提取）
│   │   └── llm_client.py       # LLM 统一调用客户端
│   │
│   ├── ui/                     # 前端界面组件
│   │   ├── __init__.py
│   │   ├── pages/              # 多页面
│   │   │   ├── home.py         # 首页（快速入口、最近文献）
│   │   │   ├── library.py      # 文献库（文件夹浏览器、上传、管理）
│   │   │   ├── reader.py       # 阅读器（PDF 阅读 + 选中翻译 + 聊天）
│   │   │   └── settings.py     # 设置（API Key、模型选择、文件夹路径）
│   │   └── components/         # 复用组件
│   │       ├── chat_box.py     # 聊天框（流式输出）
│   │       ├── pdf_viewer.py   # PDF 预览
│   │       └── sidebar.py      # 侧边栏导航
│   │
│   ├── utils/                  # 工具函数
│   │   ├── prompts.py          # 各场景 Prompt 模板
│   │   └── helpers.py          # 通用辅助函数
│   │
│   └── models/                 # 数据模型（Pydantic 等）
│       └── __init__.py
│
├── papers/                     # 文献存储（用户 PDF 文件）
├── docs/                       # 项目文档
└── tests/                      # 测试代码
```

---

## 五、模块职责划分

| 模块 | 职责 | 对外接口 |
|------|------|----------|
| `main.py` | 启动入口，注册页面/路由 | `reflex.run()` 或 `streamlit run` |
| `config.py` | 从 .env / 配置文件读取所有配置 | `Config` 数据类 |
| `pdf_processor.py` | PDF → 文本/段落/表格 | `extract_text()`, `extract_paragraphs()` |
| `translator.py` | 调用 LLM 翻译 | `translate(text, target_lang)` |
| `rag_engine.py` | 向量索引 + 检索 + RAG 问答 | `index_paper()`, `retrieve()`, `query()` |
| `analyzer.py` | 文献总结/分析 | `summarize()`, `extract_key_points()` |
| `llm_client.py` | 统一 LLM 调用（流式+非流式） | `chat()`, `chat_stream()` |
| `home.py` | 首页 UI 和逻辑 | 页面组件 |
| `library.py` | 文献浏览/上传/管理 | 页面组件 |
| `reader.py` | 阅读+翻译+聊天一体化 | 页面组件 |
| `settings.py` | 配置管理界面 | 页面组件 |

---

## 六、数据流向

```
用户操作（浏览器）
    ↓
UI 组件触发事件（按钮点击/输入等）
    ↓
src/core/ 业务函数（pdf_processor / rag_engine / llm_client）
    ↓
┌─────────────────────────────────┐
│  数据层                         │
│  ├─ papers/     → 用户 PDF 文件  │
│  ├─ data/cache/ → 解析缓存       │
│  ├─ data/vector_db/ → 向量索引   │
│  └─ data/chat_history/ → 聊天记录 │
└─────────────────────────────────┘
    ↓
返回结果 → UI 状态更新 → 界面自动刷新
```

---

## 七、核心模块设计

### 7.1 config.py — 配置中心

```python
# 所有配置集中管理，从环境变量读取敏感信息
from pydantic import BaseSettings
from pathlib import Path
from typing import Optional

class Config(BaseSettings):
    # === 文献存储 ===
    papers_dir: Path = Path("./papers")       # 文献默认文件夹
    
    # === AI 模型 ===
    llm_api_key: str                          # API Key（从 .env 读取）
    llm_base_url: str = "https://api.openai.com/v1"  # API 地址
    llm_model: str = "gpt-4o-mini"           # 默认模型
    llm_temperature: float = 0.3              # 生成温度
    
    # === RAG ===
    embedding_model: str = "text-embedding-3-small"  # 嵌入模型
    chunk_size: int = 500                     # 分块大小
    chunk_overlap: int = 50                   # 分块重叠
    
    # === 应用 ===
    app_title: str = "Literature Assistant"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 全局单例
_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
```

### 7.2 llm_client.py — LLM 统一调用

```python
# 统一封装所有 LLM 调用，支持流式和非流式
import httpx
from typing import List, Dict, AsyncIterator, Optional
from config import get_config

class LLMClient:
    """OpenAI 兼容接口的统一客户端"""
    
    def __init__(self):
        cfg = get_config()
        self.api_key = cfg.llm_api_key
        self.base_url = cfg.llm_base_url
        self.model = cfg.llm_model
        self.temperature = cfg.llm_temperature
    
    async def chat(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """非流式调用，返回完整回复"""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model or self.model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    **kwargs
                }
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    
    async def chat_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式调用，逐 token 返回"""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model or self.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": temperature or self.temperature,
                    **kwargs
                }
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
```

### 7.3 pdf_processor.py — PDF 处理

```python
# PDF → 结构化文本，保留段落信息
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import json

@dataclass
class Paragraph:
    index: int
    text: str
    page: int
    bbox: list  # [x0, y0, x1, y1]

@dataclass
class PaperContent:
    title: str
    paragraphs: List[Paragraph]
    full_text: str
    page_count: int
    source_path: str

class PDFProcessor:
    def extract(self, file_path: str) -> PaperContent:
        """提取 PDF 全部内容"""
        doc = fitz.open(file_path)
        
        paragraphs = []
        full_text = ""
        
        for page_num, page in enumerate(doc, 1):
            blocks = page.get_text("dict")["blocks"]
            page_text = page.get_text()
            full_text += page_text + "\n"
            
            for block in blocks:
                if block["type"] == 0:  # 文本块
                    text = "".join(span["text"] for span in block["lines"] for span in span["spans"])
                    if text.strip():
                        paragraphs.append(Paragraph(
                            index=len(paragraphs),
                            text=text.strip(),
                            page=page_num,
                            bbox=block["bbox"]
                        ))
        
        # 尝试从第一页提取标题
        title = Path(file_path).stem
        if doc.page_count > 0:
            first_page_text = doc[0].get_text()
            first_line = first_page_text.strip().split("\n")[0]
            if first_line:
                title = first_line
        
        doc.close()
        
        return PaperContent(
            title=title,
            paragraphs=paragraphs,
            full_text=full_text.strip(),
            page_count=len(doc),
            source_path=file_path
        )
    
    def save_cache(self, paper_id: str, content: PaperContent, cache_dir: Path):
        """保存解析缓存"""
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{paper_id}.json"
        data = {
            "title": content.title,
            "paragraphs": [
                {"index": p.index, "text": p.text, "page": p.page, "bbox": p.bbox}
                for p in content.paragraphs
            ],
            "full_text": content.full_text,
            "page_count": content.page_count,
            "source_path": content.source_path,
        }
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    
    def load_cache(self, paper_id: str, cache_dir: Path) -> Optional[PaperContent]:
        """加载解析缓存"""
        cache_file = cache_dir / f"{paper_id}.json"
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return PaperContent(
            title=data["title"],
            paragraphs=[Paragraph(**p) for p in data["paragraphs"]],
            full_text=data["full_text"],
            page_count=data["page_count"],
            source_path=data["source_path"],
        )
```

### 7.4 translator.py — 翻译

```python
from typing import Optional
from .llm_client import LLMClient

class Translator:
    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()
    
    async def translate(self, text: str, target_lang: str = "中文") -> str:
        """翻译文本到目标语言"""
        messages = [
            {"role": "system", "content": (
                "你是一个专业的学术文献翻译。要求：\n"
                "1. 准确传达原文含义\n"
                "2. 保持学术语言风格\n"
                "3. 专业术语保留英文并附中文注释\n"
                "4. 只返回翻译结果，不要解释"
            )},
            {"role": "user", "content": f"请将以下内容翻译为{target_lang}：\n\n{text}"}
        ]
        return await self.client.chat(messages, temperature=0.2)
    
    async def translate_stream(self, text: str, target_lang: str = "中文"):
        """流式翻译"""
        messages = [
            {"role": "system", "content": (
                "你是一个专业的学术文献翻译。要求：\n"
                "1. 准确传达原文含义\n"
                "2. 保持学术语言风格\n"
                "3. 专业术语保留英文并附中文注释\n"
                "4. 只返回翻译结果，不要解释"
            )},
            {"role": "user", "content": f"请将以下内容翻译为{target_lang}：\n\n{text}"}
        ]
        async for chunk in self.client.chat_stream(messages, temperature=0.2):
            yield chunk
```

### 7.5 rag_engine.py — RAG 引擎

```python
from typing import List, Dict, Optional
from pathlib import Path
from config import get_config

class RAGEngine:
    """基于向量数据库的检索增强生成"""
    
    def __init__(self):
        cfg = get_config()
        self.vector_db_dir = Path("./data/vector_db")
        self.embeddings = None  # 初始化嵌入模型
        self.collections: Dict[str, object] = {}  # paper_id → collection
    
    def index_paper(self, paper_id: str, chunks: List[str]):
        """为文献建立向量索引"""
        # 使用 ChromaDB 或 LlamaIndex
        # 1. 将 chunks 向量化
        # 2. 存入 vector_db_dir
        # 3. 记录到 collections
        pass
    
    def retrieve(self, paper_id: str, query: str, top_k: int = 5) -> List[str]:
        """检索相关段落"""
        # 1. query 向量化
        # 2. 相似度搜索 top_k
        # 3. 返回原始文本
        pass
    
    async def query(self, paper_ids: List[str], question: str) -> str:
        """RAG 问答：检索 + 生成"""
        contexts = []
        for pid in paper_ids:
            results = self.retrieve(pid, question)
            contexts.extend(results)
        
        from .llm_client import LLMClient
        client = LLMClient()
        
        prompt = f"""基于以下文献内容回答问题。

文献内容：
{chr(10).join(f"[{i+1}] {c}" for i, c in enumerate(contexts))}

问题：{question}

请基于以上内容回答，如果内容不足以回答，请说明。"""

        return await client.chat([{"role": "user", "content": prompt}])
```

### 7.6 analyzer.py — 分析器

```python
from typing import List
from .llm_client import LLMClient

class Analyzer:
    def __init__(self, client=None):
        self.client = client or LLMClient()
    
    async def summarize(self, text: str, max_length: int = 500) -> str:
        """生成文献摘要"""
        messages = [
            {"role": "system", "content": "你是学术文献分析专家。请简洁准确地总结文献核心内容。"},
            {"role": "user", "content": f"请用不超过 {max_length} 字总结以下文献：\n\n{text}"}
        ]
        return await self.client.chat(messages, temperature=0.3)
    
    async def extract_key_points(self, text: str) -> List[str]:
        """提取要点列表"""
        messages = [
            {"role": "system", "content": "你是学术文献分析专家。提取文献的核心要点，以列表形式返回。"},
            {"role": "user", "content": f"请提取以下文献的核心要点：\n\n{text}"}
        ]
        result = await self.client.chat(messages, temperature=0.2)
        # 解析列表格式
        return [line.strip().lstrip("-*•123456789. ") 
                for line in result.split("\n") 
                if line.strip()]
    
    async def structure_analysis(self, text: str) -> Dict:
        """结构性分析：背景、方法、结果、结论"""
        messages = [
            {"role": "system", "content": (
                "你是学术文献分析专家。请对文献进行结构化分析，返回 JSON 格式："
                '{"background": "...", "methodology": "...", "results": "...", "conclusion": "...", "limitations": "..."}'
            )},
            {"role": "user", "content": f"请分析以下文献的结构：\n\n{text}"}
        ]
        result = await self.client.chat(messages, temperature=0.2)
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw_analysis": result}
```

---

## 八、UI 页面设计

### 8.1 页面路由与功能

| 页面 | 文件 | 核心功能 | 依赖的 core 模块 |
|------|------|----------|------------------|
| **首页** | `home.py` | 最近文献、快速搜索、快捷操作入口 | pdf_processor |
| **文献库** | `library.py` | 文件夹浏览、上传 PDF、删除、标签管理 | pdf_processor |
| **阅读器** | `reader.py` | PDF 展示、选中段落翻译、侧边聊天、RAG 问答 | translator, rag_engine, llm_client |
| **设置** | `settings.py` | API Key、模型选择、文献路径配置 | config |

### 8.2 阅读器页面核心交互（最复杂）

```
┌──────────────────────────────────────────────────────────┐
│  ════ 阅读器 (reader.py) ════                            │
├──────────────────────┬───────────────────────────────────┤
│                      │                                   │
│    PDF 显示区域       │        聊天 / 翻译 区域            │
│                      │                                   │
│  ┌────────────────┐ │  ┌─────────────────────────────┐  │
│  │                │ │  │ [翻译] [分析] [问答] 切换Tab │  │
│  │   PDF 内容     │ │  ├─────────────────────────────┤  │
│  │                │ │  │                             │  │
│  │  (选中文字 →    │ │  │  选中段落翻译:               │  │
│  │   自动触发翻译)  │ │  │  原文：xxx                  │  │
│  │                │ │  │  译文：xxx                  │  │
│  │                │ │  │                             │  │
│  │                │ │  │  ── 或 RAG 问答 ──           │  │
│  │                │ │  │  Q: 这篇论文的方法是什么？     │  │
│  │                │ │  │  A: （流式输出...）           │  │
│  └────────────────┘ │  │                             │  │
│                      │  │  [________________] [发送]    │  │
│                      │  └─────────────────────────────┘  │
├──────────────────────┴───────────────────────────────────┤
│  底部工具栏：上一页/下一页 | 缩放 | 全屏模式 | 导出       │
└──────────────────────────────────────────────────────────┘
```

### 8.3 流式输出方案

```python
# Reflex 示例：聊天流式输出
import reflex as rx

class ChatState(rx.State):
    messages: list[dict] = []
    current_input: str = ""
    streaming_text: str = ""
    
    @rx.event
    async def send_message(self):
        user_msg = {"role": "user", "content": self.current_input}
        self.messages.append(user_msg)
        self.current_input = ""
        yield  # 先显示用户消息
        
        assistant_msg = {"role": "assistant", "content": ""}
        self.messages.append(assistant_msg)
        
        from src.core.llm_client import LLMClient
        client = LLMClient()
        async for chunk in client.chat_stream(self.messages[:-1]):
            self.streaming_text += chunk
            assistant_msg["content"] = self.streaming_text
            yield  # 每个字符都刷新 UI
        
        self.streaming_text = ""  # 重置
```

---

## 九、数据库设计

### 9.1 SQLite — 元数据 & 聊天历史

```sql
-- 文献表
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_hash TEXT,                    -- 文件哈希，用于检测变更
    category TEXT DEFAULT 'Uncategorized',
    page_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 会话表（聊天会话）
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'free',           -- free/translate/analysis/qa
    paper_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- 消息表
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,                  -- user/assistant/system
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
```

### 9.2 ChromaDB — 向量索引

```python
# 由 rag_engine.py 自动管理，无需手动建表
# 存储在 data/vector_db/ 目录下
# 每个 Collection 对应一篇文献的向量化段落
```

---

## 十、开发路线图

### Phase 1：骨架搭建（1天）
- [x] 目录结构创建
- [ ] main.py 入口（能启动空页面）
- [ ] config.py 配置系统（.env 支持）
- [ ] requirements.txt 依赖清单
- [ ] .gitignore

### Phase 2：核心能力打通（2-3天）
- [ ] llm_client.py — LLM 调通（非流式 + 流式）
- [ ] pdf_processor.py — PDF 提取能跑
- [ ] translator.py — 翻译流程跑通
- [ ] home.py + library.py — 基础页面（上传/浏览 PDF）

### Phase 3：阅读器 + 聊天（2-3天）
- [ ] reader.py — PDF 展示 + 选中翻译
- [ ] components/chat_box.py — 流式聊天框
- [ ] analyzer.py — 总结和分析功能
- [ ] rag_engine.py — RAG 问答

### Phase 4：完善体验（1-2天）
- [ ] settings.py — 配置管理界面
- [ ] 缓存机制 — PDF 解析缓存、翻译缓存
- [ ] 文献库 — 文件夹树、分类、搜索
- [ ] 会话历史 — 保存和恢复

### Phase 5：工程化（可选）
- [ ] 单元测试
- [ ] 日志系统
- [ ] 错误处理和友好提示
- [ ] 打包分发（Docker / PyInstaller）

---

## 十一、关键注意事项

### 1. UI 框架选型建议

| 因素 | 推荐 Reflex | 推荐 Streamlit |
|------|-------------|----------------|
| 阅读器需要复杂双栏布局 | ✅ | ⚠️ 勉强 |
| 流式输出打字效果 | ✅ 原生支持 | ✅ 原生支持 |
| PDF 内选中文字交互 | ✅ 可用 JS 回调 | ⚠️ 受限 |
| 自定义样式程度 | ✅ 接近自由 | ❌ 受限 |
| 上手速度 | ⚠️ 需学 React 概念 | ✅ 纯 Python 即可 |
| 部署难度 | ✅ npm build 后单文件 | ✅ 单文件 |

**建议：如果阅读器的交互体验优先级高 → 选 Reflex；如果想先快速出 MVP → 选 Streamlit 后续迁移。**

### 2. 文献存储策略

```
papers/
├── Attention Is All You Need.pdf    # 保持原文件名（用户友好）
├── BERT Pre-training.pdf
└── ...（直接存放用户 PDF）

data/cache/
├── {file_hash}.json                 # 按哈希存解析缓存
└── ...

data/vector_db/
└── chroma/                          # ChromaDB 自动管理
```

> 与旧方案的「按 ID 存储」不同：这里保持用户原文件名更直观，
> 用 file_hash 关联缓存和向量索引。

### 3. LLM 兼容性

`llm_client.py` 基于 OpenAI SDK 格式，天然兼容：
- **OpenAI** (GPT-4o, GPT-4o-mini)
- **NVIDIA NIM** (改 base_url 即可)
- **Ollama 本地模型** (`http://localhost:11434/v1`)
- **Azure OpenAI**
- **任何 OpenAI 兼容服务**

### 4. 错误处理原则

```python
# core 层抛出明确异常，UI 层捕获并展示友好提示
class PaperNotFoundError(Exception): pass
class PDFParseError(Exception): pass
class LLMConnectionError(Exception): pass
class TranslationError(Exception): pass

# UI 层统一捕获
try:
    result = await translator.translate(text)
except LLMConnectionError:
    yield rx.toast.error("AI 服务连接失败，请检查网络和 API 设置")
except Exception as e:
    yield rx.toast.error(f"未知错误: {e}")
```

---

## 十二、学习资源

- **Reflex 官方文档**：https://reflex.dev/docs/getting-started/installation
- **Streamlit 官方文档**：https://docs.streamlit.io/
- **PyMuPDF 文档**：https://pymupdf.readthedocs.io/
- **ChromaDB 文档**https://docs.trychroma.com/
- **OpenAI Python SDK**：https://github.com/openai/openai-python
- **LlamaIndex**：https://docs.llamaindex.ai/

---

*文档版本：v4.0（Reflex/Streamlit 全栈架构）*
*最后更新：2026-04-26*

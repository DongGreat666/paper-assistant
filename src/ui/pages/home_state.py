"""State and backend events for the home chat page."""

import logging
from pathlib import Path

import reflex as rx

from config import get_config
from src.core.engine import (
    get_default_translation_engine,
    has_usable_api_key,
    load_engine_profiles,
)
from src.core import chat_history
from src.core.markdown_math import normalize_math_delimiters, normalize_message_math
from src.ui.pages.home_chat_service import stream_chat_completion, trim_context
from src.ui.pages.home_model_service import (
    build_home_engine,
    current_engine_label,
    delete_engine_action,
    find_profile,
    new_engine_form_values,
    persist_home_model,
    resolve_model_defaults,
    save_engine_action,
    select_engine_action,
    start_edit_engine_action,
    test_profile,
)
from src.ui.pages.home_upload_service import (
    delete_upload_source,
    image_data_url,
    prepare_document,
    save_chat_upload,
)

logger = logging.getLogger(__name__)

_model_defaults = resolve_model_defaults()


def _load_engines_safe() -> list[dict]:
    try:
        return load_engine_profiles()
    except Exception as e:
        logger.warning(f"Failed to load engine profiles: {e}")
        return []


def _list_conversations_safe() -> list[dict]:
    try:
        return chat_history.list_conversations()
    except Exception as e:
        logger.warning(f"Failed to list conversations: {e}")
        return []


class HomeState(rx.State):
    """State for the chat workspace."""

    input_text: str = ""
    file_name: str = ""
    saved_path: str = ""
    folder_path: str = ""
    file_info: str = ""
    paper_md: str = ""
    paper_ready: bool = False
    is_preparing: bool = False
    is_chatting: bool = False
    status_message: str = "上传文件后即可提问。"
    messages: list[dict] = []
    pending_image_data_url: str = ""
    pending_image_name: str = ""

    # Conversation persistence
    conversation_id: str = ""
    conversations: list[dict] = _list_conversations_safe()

    # Model config fields. They share the same local profile file as the translation page.
    model_auto: bool = _model_defaults.get("home_model_auto", True)
    model_settings_open: bool = False
    engine_api_key: str = _model_defaults.get("home_engine_api_key", "")
    engine_base_url: str = _model_defaults.get("home_engine_base_url", get_default_translation_engine().base_url)
    engine_model: str = _model_defaults.get("home_engine_model", get_config().get_model_for("qa")[0])
    engine_temperature: str = _model_defaults.get("home_engine_temperature", str(get_config().get_model_for("qa")[1]))
    engine_name: str = _model_defaults.get("home_engine_name", "论文问答模型")
    selected_engine_id: str = _model_defaults.get("home_selected_engine_id", "env-default")
    saved_engines: list[dict] = _load_engines_safe()
    editing_engine_id: str = ""

    def set_input(self, text: str):
        self.input_text = text

    def toggle_model_auto(self, value: bool):
        self.model_auto = value
        self.status_message = "自动模式已启用，将优先使用 .env 中的问答模型。" if value else "自定义模型已启用。"
        self._persist_model()

    def toggle_model_settings(self):
        self.model_settings_open = not self.model_settings_open

    def _persist_model(self):
        persist_home_model(
            model_auto=self.model_auto,
            selected_engine_id=self.selected_engine_id,
            engine_api_key=self.engine_api_key,
            engine_base_url=self.engine_base_url,
            engine_model=self.engine_model,
            engine_temperature=self.engine_temperature,
            engine_name=self.engine_name,
        )

    def set_engine_api_key(self, value: str):
        self.engine_api_key = value

    def set_engine_base_url(self, value: str):
        self.engine_base_url = value

    def set_engine_model(self, value: str):
        self.engine_model = value

    def set_engine_temperature(self, value: str):
        self.engine_temperature = value

    def set_engine_name(self, value: str):
        self.engine_name = value

    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        saved = await save_chat_upload(files[0])
        if saved.suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            self._delete_pending_image_source()
            self.pending_image_data_url = image_data_url(saved.data, saved.safe_name)
            self.pending_image_name = saved.safe_name
            self.saved_path = str(saved.destination)
            self.folder_path = str(saved.folder)
            self.status_message = "图片已附加，输入问题后即可发送。"
            yield
            return

        self.file_name = saved.safe_name
        self.saved_path = str(saved.destination)
        self.folder_path = str(saved.folder)
        self.file_info = saved.file_info
        self.paper_md = ""
        self.paper_ready = False
        self.is_preparing = True
        self.status_message = "文件已上传，正在准备上下文..."
        self.messages = self.messages + [
            {
                "role": "assistant",
                "content": f"已上传 {saved.safe_name}，正在准备问答上下文。",
            }
        ]
        yield

        try:
            md_text = await prepare_document(saved)
            self.paper_md = md_text
            self.paper_ready = bool(md_text.strip())
            self.status_message = "上下文已准备好，可以开始提问。"
        except Exception as exc:
            self.paper_ready = False
            self.status_message = f"文件已保存，但准备上下文失败：{exc}"
            self.messages = self.messages + [
                {
                    "role": "assistant",
                    "content": "文件已保存，但解析失败。请检查文件或稍后重试。",
                }
            ]
        finally:
            delete_upload_source(saved)
            self.saved_path = ""
            self.is_preparing = False
            self._save_chat()
            yield

    async def submit(self, _form_data: dict):
        self.input_text = str(_form_data.get("message", ""))
        async for event in self._send_current_message():
            yield event

    def attach_pasted_image(self, data_url: str):
        if not data_url.startswith("data:image/"):
            return
        self.pending_image_data_url = data_url
        self.pending_image_name = "剪贴板图片"
        self.status_message = "截图已附加，输入问题后即可发送。"

    def clear_pending_image(self):
        self.pending_image_data_url = ""
        self.pending_image_name = ""

    async def _send_current_message(self):
        question = self.input_text.strip()
        image_data_url = self.pending_image_data_url
        if image_data_url and not question:
            question = "请分析这张图片。"
        if not question or self.is_chatting:
            return

        self.input_text = ""
        user_message = {"role": "user", "content": question}
        if image_data_url:
            user_message["image_data_url"] = image_data_url
        self.messages = self.messages + [user_message]
        self.pending_image_data_url = ""
        self.pending_image_name = ""
        self.is_chatting = True
        self.status_message = "正在生成回答..."
        yield

        engine = self._build_engine()
        if not has_usable_api_key(engine.api_key):
            self.messages = self.messages + [
                {
                    "role": "assistant",
                    "content": "还没有可用的 API Key。请在聊天框下方配置模型，或在 .env 里设置 LLM_API_KEY。",
                }
            ]
            self.is_chatting = False
            self.status_message = "缺少 API Key。"
            self._delete_pending_image_source()
            return

        accumulated = ""
        try:
            # Append empty assistant message, then stream into it
            self.messages = self.messages + [{"role": "assistant", "content": ""}]
            yield
            async for chunk in stream_chat_completion(self._build_messages(question, image_data_url), engine):
                accumulated += chunk
                self.messages = self.messages[:-1] + [
                    {"role": "assistant", "content": normalize_math_delimiters(accumulated)}
                ]
                yield
            self.status_message = "回答完成。"
        except Exception as exc:
            # If streaming partially succeeded, keep what we have
            if not accumulated:
                self.messages = self.messages[:-1] + [
                    {"role": "assistant", "content": f"调用模型失败：{exc}"}
                ]
            self.status_message = f"调用模型失败：{exc}"
        finally:
            self._delete_pending_image_source()
            self.is_chatting = False
            self._save_chat()

    def _delete_pending_image_source(self):
        if not self.saved_path:
            return
        try:
            path = Path(self.saved_path)
            chat_upload_root = (get_config().data_dir / "chat_uploads").resolve()
            resolved = path.resolve()
            if resolved.is_relative_to(chat_upload_root):
                resolved.unlink(missing_ok=True)
        except OSError:
            pass
        self.saved_path = ""

    def _build_messages(self, question: str, image_data_url: str = "") -> list[dict]:
        messages: list[dict] = []
        if self.paper_ready:
            context = trim_context(self.paper_md)
            messages.append({
                "role": "system",
                "content": (
                    "用户已上传论文。请基于下面的论文 Markdown 内容回答用户问题。"
                    "如果用户只是泛泛提问或要求开始，请先总结论文的核心问题、方法、实验和结论。"
                    "如果论文内容不足以回答问题，请说明依据不足。\n\n"
                    f"{context}"
                ),
            })

        history = self.messages[-10:]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in history
            if item.get("role") in {"user", "assistant"}
        )
        if image_data_url:
            messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        elif not history or history[-1].get("content") != question:
            messages.append({"role": "user", "content": question})
        return messages

    def select_engine(self, profile_id: str):
        updates = select_engine_action(self.saved_engines, profile_id)
        if updates:
            for k, v in updates.items():
                setattr(self, k, v)
            self.model_auto = False
            self._persist_model()

    def start_edit_engine(self, profile_id: str):
        updates = start_edit_engine_action(self.saved_engines, profile_id)
        if updates:
            for k, v in updates.items():
                setattr(self, k, v)

    def start_new_engine(self):
        values = new_engine_form_values()
        self.model_auto = False
        self.editing_engine_id = "__new__"
        for k, v in values.items():
            setattr(self, k, v)

    def cancel_edit(self):
        self.editing_engine_id = ""

    def save_current_engine(self):
        self.saved_engines, pid = save_engine_action(
            self.saved_engines,
            engine_name=self.engine_name,
            engine_api_key=self.engine_api_key,
            engine_base_url=self.engine_base_url,
            engine_model=self.engine_model,
            engine_temperature=self.engine_temperature,
            editing_engine_id=self.editing_engine_id,
        )
        self.selected_engine_id = pid
        self.editing_engine_id = ""
        self.model_auto = False
        self.status_message = f"已保存模型：{self.engine_name.strip() or '问答模型'}。"
        self._persist_model()

    def delete_engine(self, profile_id: str):
        self.saved_engines = delete_engine_action(self.saved_engines, profile_id)
        if self.selected_engine_id == profile_id:
            self.selected_engine_id = "env-default"
            self.model_auto = True
        if self.editing_engine_id == profile_id:
            self.editing_engine_id = ""
        self.status_message = "已删除模型配置。"
        self._persist_model()

    async def test_engine(self, profile_id: str):
        profile = find_profile(self.saved_engines, profile_id)
        if not profile:
            return
        try:
            await test_profile(profile)
            self.saved_engines = [
                {**p, "status": "ok"} if p.get("id") == profile_id else p
                for p in self.saved_engines
            ]
            self.status_message = f"模型 [{profile.get('name', profile_id)}] 连接正常。"
        except Exception as exc:
            self.saved_engines = [
                {**p, "status": "fail"} if p.get("id") == profile_id else p
                for p in self.saved_engines
            ]
            self.status_message = f"模型 [{profile.get('name', profile_id)}] 连接失败：{exc}"

    def open_folder(self):
        if not self.folder_path:
            return
        import os
        os.startfile(self.folder_path)

    def _reset_chat_workspace(self, status_message: str):
        """Reset the current conversation, draft, and attached document."""
        self.input_text = ""
        self.messages = []
        self.conversation_id = ""
        self.file_name = ""
        self.saved_path = ""
        self.folder_path = ""
        self.file_info = ""
        self.paper_md = ""
        self.paper_ready = False
        self.pending_image_data_url = ""
        self.pending_image_name = ""
        self.is_preparing = False
        self.is_chatting = False
        self.status_message = status_message

    def clear_chat(self):
        self._reset_chat_workspace("对话已清空。")

    def _current_engine_label(self) -> str:
        return current_engine_label(self.model_auto, self.engine_name, self.engine_model)

    def _save_chat(self):
        """Persist current conversation to disk."""
        if not self.messages:
            return
        engine_label = self._current_engine_label()
        if not self.conversation_id:
            conv = chat_history.new_conversation(
                paper=self.file_name, messages=self.messages, engine=engine_label,
            )
            self.conversation_id = conv["id"]
        else:
            conv = chat_history.load(self.conversation_id)
            if conv is None:
                conv = chat_history.new_conversation(
                    paper=self.file_name, messages=self.messages, engine=engine_label,
                )
                self.conversation_id = conv["id"]
            else:
                conv["messages"] = self.messages
                conv["paper"] = self.file_name
                conv["engine"] = engine_label
                chat_history.update_title(conv, self.messages[0].get("content", ""))
        chat_history.save(conv)
        self.conversations = chat_history.list_conversations()

    def new_chat(self):
        """Start a fresh conversation."""
        if self.messages:
            self._save_chat()
        self._reset_chat_workspace("新对话已开始。")

    def switch_chat(self, conv_id: str):
        """Load an existing conversation."""
        if self.messages and self.conversation_id != conv_id:
            self._save_chat()
        conv = chat_history.load(conv_id)
        if conv is None:
            self.status_message = "对话记录不存在。"
            return
        self.conversation_id = conv["id"]
        self.messages = normalize_message_math(conv.get("messages", []))
        self.file_name = conv.get("paper", "")
        self.status_message = f"已加载对话：{conv.get('title', conv_id)}"

    def delete_chat(self, conv_id: str):
        """Delete a conversation from disk and sidebar."""
        chat_history.delete(conv_id)
        self.conversations = chat_history.list_conversations()
        if self.conversation_id == conv_id:
            self.conversation_id = ""
            self.messages = []
            self.input_text = ""
            self.status_message = "对话已删除。"

    def _build_engine(self):
        return build_home_engine(
            model_auto=self.model_auto,
            engine_api_key=self.engine_api_key,
            engine_base_url=self.engine_base_url,
            engine_model=self.engine_model,
            engine_temperature=self.engine_temperature,
        )

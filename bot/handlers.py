import logging
import time
import uuid

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.telegram_utils import clean_html, escape_html, split_html_message
from config.settings import get_settings
from db.repositories import DocumentRepo, RequestRepo
from rag.agent import run_agent

logger = logging.getLogger(__name__)

# Conversation history per user: user_id -> list of message dicts
_history: dict[int, list[dict]] = {}
_last_activity: dict[int, float] = {}


def _cleanup_stale_sessions() -> None:
    """Remove sessions that have been inactive for more than TTL."""
    settings = get_settings()
    now = time.monotonic()
    stale = [uid for uid, ts in _last_activity.items() if now - ts > settings.history_ttl_seconds]
    for uid in stale:
        _history.pop(uid, None)
        _last_activity.pop(uid, None)


def _get_history(user_id: int) -> list[dict]:
    _cleanup_stale_sessions()
    _last_activity[user_id] = time.monotonic()
    return _history.setdefault(user_id, [])


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Добро пожаловать!</b>\n\n"
        "Я — бот-ассистент по монографиям об Agile и организационному дизайну.\n\n"
        "Задайте мне вопрос, и я найду ответ в базе знаний.\n\n"
        "Используйте /help для списка команд."
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Как пользоваться ботом</b>\n\n"
        "Просто отправьте вопрос текстом, например:\n"
        "- <i>Что такое Scrum of Scrums?</i>\n"
        "- <i>Как организовать кросс-функциональные команды?</i>\n"
        "- <i>Какие метрики использовать для оценки agility?</i>\n\n"
        "<b>Команды:</b>\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/sources — список проиндексированных документов\n"
        "/stats — статистика (только для администраторов)"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def sources_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        docs = await DocumentRepo().list_indexed()
    except Exception:
        logger.exception("Failed to fetch document list")
        await update.effective_message.reply_text(
            "Не удалось загрузить список источников. Попробуйте позже."
        )
        return

    if not docs:
        await update.effective_message.reply_text("Пока нет проиндексированных документов.")
        return

    lines = ["<b>Проиндексированные источники:</b>\n"]
    for i, doc in enumerate(docs, 1):
        title = escape_html(doc.title or doc.filename)
        lines.append(f"{i}. {title}")

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    user_id = update.effective_user.id

    if user_id not in settings.admin_user_ids:
        await update.effective_message.reply_text("Нет доступа.")
        return

    try:
        stats = await RequestRepo().get_stats(days=7)
    except Exception:
        logger.exception("Failed to fetch stats")
        await update.effective_message.reply_text(
            "Не удалось загрузить статистику. Попробуйте позже."
        )
        return

    avg_latency = stats.get("avg_latency")
    avg_str = f"{avg_latency:.0f} мс" if avg_latency is not None else "н/д"

    text = (
        "<b>Статистика за 7 дней</b>\n\n"
        f"Запросов: {stats.get('total', 0)}\n"
        f"Уникальных пользователей: {stats.get('unique_users', 0)}\n"
        f"Средняя задержка: {avg_str}\n"
        f"Ошибок: {stats.get('errors', 0)}"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.effective_message.text
    if not query:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username
    history = _get_history(user_id)
    request_id = str(uuid.uuid4())

    status_msg = await update.effective_message.reply_text("🔍 Ищу в монографиях...")

    async def on_status(text: str) -> None:
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass  # Status update is best-effort

    ai_client = context.bot_data["ai_client"]

    # Fetch doc titles for system prompt (best-effort)
    doc_titles: list[str] = []
    try:
        docs = await DocumentRepo().list_indexed()
        doc_titles = [doc.title or doc.filename for doc in docs]
    except Exception:
        logger.warning("Failed to fetch doc titles for system prompt")

    try:
        result = await run_agent(
            query=query,
            user_id=user_id,
            history=history,
            ai_client=ai_client,
            doc_titles=doc_titles,
            on_status=on_status,
        )
    except Exception:
        logger.exception("Agent failed for user %s query: %s", user_id, query[:100])
        try:
            await status_msg.edit_text(
                "Произошла ошибка при обработке запроса. Попробуйте позже."
            )
        except Exception:
            pass
        return

    # Update conversation history
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": result.answer})
    settings = get_settings()
    if len(history) > settings.history_max:
        trimmed = history[-settings.history_trim_to:]
        history.clear()
        history.extend(trimmed)

    # Delete status message
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Send answer in chunks
    answer_html = clean_html(result.answer)
    chunks = split_html_message(answer_html)
    for chunk in chunks:
        try:
            await update.effective_message.reply_text(
                chunk, parse_mode=ParseMode.HTML
            )
        except Exception:
            logger.exception("Failed to send chunk to user %s", user_id)
            await update.effective_message.reply_text(chunk)

    # Log request
    try:
        await RequestRepo().log(
            request_id=request_id,
            user_id=user_id,
            username=username,
            query=query,
            answer=result.answer,
            latency_ms=result.latency_ms,
            tools_used=result.tools_used,
        )
    except Exception:
        logger.exception("Failed to log request %s", request_id)

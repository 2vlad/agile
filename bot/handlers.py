import logging
import tempfile
import time
import uuid
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.telegram_utils import clean_html, escape_html, split_html_message
from config.bot_config import get_bot_config
from config.settings import get_settings
from db.repositories import DocumentRepo, RequestRepo
from indexer.ingest import ingest_file
from indexer.parsers import SUPPORTED_EXTENSIONS
from rag.pipeline import run_pipeline

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
    cfg = get_bot_config()
    doc_count = 0
    try:
        docs = await DocumentRepo().list_indexed()
        doc_count = len(docs)
    except Exception:
        logger.warning("Failed to fetch doc count for start message")

    text = cfg.welcome.replace("{doc_count}", str(doc_count))
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = get_bot_config()
    formats = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    examples = "\n".join(f"- <i>{e}</i>" for e in cfg.help_examples) if cfg.help_examples else ""
    text = cfg.help.replace("{examples}", examples).replace("{formats}", formats)
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
    repo = RequestRepo()
    caller_id = update.effective_user.id

    try:
        stats = await repo.get_stats(days=7, exclude_user_id=caller_id)
        recent = await repo.get_recent(limit=10, exclude_user_id=caller_id)
    except Exception:
        logger.exception("Failed to fetch stats")
        await update.effective_message.reply_text(
            "Не удалось загрузить статистику. Попробуйте позже."
        )
        return

    avg_latency = stats.get("avg_latency")
    avg_str = f"{avg_latency:.0f} мс" if avg_latency is not None else "н/д"

    lines = [
        "<b>Статистика за 7 дней</b>\n",
        f"Запросов: {stats.get('total', 0)}",
        f"Уникальных пользователей: {stats.get('unique_users', 0)}",
        f"Средняя задержка: {avg_str}",
        f"Ошибок: {stats.get('errors', 0)}",
    ]

    if recent:
        lines.append("\n<b>Последние запросы:</b>\n")
        for r in recent:
            ts = r["created_at"].strftime("%d.%m %H:%M") if r.get("created_at") else "?"
            user = escape_html(r.get("username") or "?")
            query = escape_html(r.get("query") or "")
            latency = f"{r['latency_ms']}мс" if r.get("latency_ms") else "?"
            lines.append(f"{ts} | @{user} | {latency}\n{query}")

    text = "\n".join(lines)
    for chunk in split_html_message(text):
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.effective_message.text
    if not query:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username
    history = _get_history(user_id)
    request_id = str(uuid.uuid4())

    logger.info("User %s (%s): %s", user_id, username, query[:200])
    status_msg = await update.effective_message.reply_text("\U0001f4ac Думаю...")

    async def on_status(text: str) -> None:
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass  # Status update is best-effort

    llm_client = context.bot_data["llm_client"]
    embed_client = context.bot_data["embed_client"]

    # Fetch doc titles for system prompt (best-effort)
    doc_titles: list[str] = []
    try:
        docs = await DocumentRepo().list_indexed()
        doc_titles = [doc.title or doc.filename for doc in docs]
    except Exception:
        logger.warning("Failed to fetch doc titles for system prompt")

    try:
        result = await run_pipeline(
            query=query,
            user_id=user_id,
            history=history,
            llm_client=llm_client,
            embed_client=embed_client,
            doc_titles=doc_titles,
            on_status=on_status,
        )
    except Exception as exc:
        logger.exception("Pipeline failed for user %s query: %s — %s", user_id, query[:100], exc)
        try:
            await status_msg.edit_text(
                "Произошла ошибка при обработке запроса. Попробуйте позже."
            )
        except Exception:
            pass
        return

    logger.info(
        "Pipeline result for user %s: %dms, %d chunks, answer_len=%d, preview=%s",
        user_id, result.latency_ms, result.chunks_found, len(result.answer), result.answer[:200],
    )

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
            tools_used=[],
        )
    except Exception:
        logger.exception("Failed to log request %s", request_id)


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uploaded documents — index them into the corpus."""
    doc = update.effective_message.document
    if not doc:
        return

    filename = doc.file_name or "unknown"
    ext = Path(filename).suffix.lower()
    user_id = update.effective_user.id
    username = update.effective_user.username

    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        await update.effective_message.reply_text(
            f"Формат {ext} не поддерживается.\n\nПоддерживаемые: {supported}"
        )
        return

    logger.info("User %s (%s) uploaded file: %s (%d bytes)", user_id, username, filename, doc.file_size or 0)
    status_msg = await update.effective_message.reply_text(
        f"\U0001f4c4 Обрабатываю {escape_html(filename)}...",
        parse_mode=ParseMode.HTML,
    )

    embed_client = context.bot_data["embed_client"]

    try:
        tg_file = await doc.get_file()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / filename
            await tg_file.download_to_drive(str(filepath))

            try:
                await status_msg.edit_text(
                    f"\U0001f4c4 Индексирую {escape_html(filename)}...",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

            status, title, chunk_count = await ingest_file(filepath, embed_client)

        if status == "indexed":
            await status_msg.edit_text(
                f"Проиндексировано: <b>{escape_html(title)}</b> ({chunk_count} фрагментов)",
                parse_mode=ParseMode.HTML,
            )
        elif status == "skipped":
            await status_msg.edit_text(
                f"<b>{escape_html(title)}</b> — уже в базе, пропущено.",
                parse_mode=ParseMode.HTML,
            )

    except Exception as exc:
        logger.exception("Failed to index file %s from user %s: %s", filename, user_id, exc)
        try:
            await status_msg.edit_text(
                f"Не удалось обработать {escape_html(filename)}. Проверьте формат файла.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

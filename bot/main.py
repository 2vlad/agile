import hashlib
import hmac
import logging
import os
from contextlib import asynccontextmanager

# Verbose logging for debugging — set LOG_LEVEL=INFO in production later
_log_level = os.environ.get("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Keep third-party libs at WARNING to reduce noise
for _lib in ("httpx", "httpcore", "telegram", "asyncio", "urllib3"):
    logging.getLogger(_lib).setLevel(logging.WARNING)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (
    help_handler,
    message_handler,
    sources_handler,
    start_handler,
    stats_handler,
)
from config.settings import get_settings
from db.connection import close_pool, init_db
from observability import init_langfuse, shutdown as lf_shutdown
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    init_langfuse()
    logger.info("Starting bot with folder_id=%s, llm_model=%s", settings.yc_folder_id, settings.llm_model)
    logger.info("DATABASE_URL host=%s", settings.database_url.split("@")[-1].split("/")[0] if "@" in settings.database_url else "?")

    # Initialize database
    await init_db()

    # Build shared AI client
    ai_client = YandexAIStudio(
        api_key=settings.yc_api_key,
        folder_id=settings.yc_folder_id,
        llm_model=settings.llm_model,
        embed_doc_model=settings.embed_doc_model,
        embed_query_model=settings.embed_query_model,
        llm_base_url=settings.yc_llm_base_url,
        embeddings_url=settings.yc_embeddings_url,
    )

    # Build Telegram application
    application = Application.builder().token(settings.telegram_token).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("sources", sources_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )

    # Store ai_client in bot_data so handlers can access it
    application.bot_data["ai_client"] = ai_client

    await application.initialize()
    await application.start()

    # Stable webhook secret derived from token — same across cold starts
    webhook_secret = hmac.new(
        settings.telegram_token.encode(), b"webhook-secret", hashlib.sha256
    ).hexdigest()

    use_polling = not settings.webhook_url
    if use_polling:
        # Local mode: use polling (no public URL needed)
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Running in POLLING mode (local)")
    else:
        # Cloud mode: set webhook
        webhook = f"{settings.webhook_url.rstrip('/')}/webhook"
        await application.bot.set_webhook(webhook, secret_token=webhook_secret)
        logger.info("Running in WEBHOOK mode: %s", webhook)

    app.state.bot_app = application
    app.state.webhook_secret = webhook_secret

    yield

    # Shutdown
    if use_polling:
        await application.updater.stop()
    else:
        try:
            await application.bot.delete_webhook()
        except Exception:
            logger.warning("Failed to delete webhook on shutdown")

    await application.stop()
    await application.shutdown()
    await ai_client.close()
    lf_shutdown()
    await close_pool()
    logger.info("Shutdown complete")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    expected = request.app.state.webhook_secret
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if received != expected:
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    bot_app: Application = request.app.state.bot_app
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

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
    document_handler,
    help_handler,
    message_handler,
    sources_handler,
    start_handler,
    stats_handler,
)
from config.settings import get_settings
from db.connection import close_pool, init_db
from engine.auto_index import auto_index_corpus
from engine.embeddings import create_embedding_client
from engine.llm import create_llm_client
from observability import init_langfuse, shutdown as lf_shutdown

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    init_langfuse()
    logger.info(
        "Starting bot: llm=%s/%s, embed=%s/%s",
        settings.llm_provider, settings.llm_model or "default",
        settings.embed_provider, settings.embed_model or "default",
    )
    logger.info("DATABASE_URL host=%s", settings.database_url.split("@")[-1].split("/")[0] if "@" in settings.database_url else "?")

    # Initialize database
    await init_db()

    # Build provider clients via factories
    llm_client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.effective_llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        folder_id=settings.yc_folder_id,
    )
    embed_client = create_embedding_client(
        provider=settings.embed_provider,
        api_key=settings.effective_embed_api_key,
        model=settings.embed_model,
        dim=settings.embed_dim,
        base_url=settings.embed_base_url,
        folder_id=settings.yc_folder_id,
    )

    # Auto-index corpus on startup
    if settings.auto_index:
        try:
            await auto_index_corpus(embed_client)
        except Exception:
            logger.exception("Auto-index failed (non-fatal)")

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
    application.add_handler(
        MessageHandler(filters.Document.ALL, document_handler)
    )

    # Store clients in bot_data so handlers can access them
    application.bot_data["llm_client"] = llm_client
    application.bot_data["embed_client"] = embed_client

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
    await llm_client.close()
    await embed_client.close()
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

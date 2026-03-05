import logging
import secrets
from contextlib import asynccontextmanager

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
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

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

    # Set webhook if configured
    webhook_secret = secrets.token_hex(32)
    if settings.webhook_url:
        webhook = f"{settings.webhook_url.rstrip('/')}/webhook"
        await application.bot.set_webhook(webhook, secret_token=webhook_secret)
        logger.info("Webhook set to %s", webhook)

    app.state.bot_app = application
    app.state.webhook_secret = webhook_secret

    yield

    # Shutdown
    if settings.webhook_url:
        try:
            await application.bot.delete_webhook()
        except Exception:
            logger.warning("Failed to delete webhook on shutdown")

    await application.stop()
    await application.shutdown()
    await ai_client.close()
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

"""Load and cache bot.yaml configuration."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PERSONA = "You are a helpful knowledge assistant."
_DEFAULT_WELCOME = "Hello! I'm a knowledge bot. Ask me anything about {doc_count} indexed documents.\n\n/help — help"
_DEFAULT_HELP = "<b>How to use</b>\n\nSend a question or upload a document.\n\n/sources — list of indexed documents"


class BotConfig:
    def __init__(self, data: dict[str, Any]) -> None:
        bot = data.get("bot", {})
        self.name: str = bot.get("name", "Knowledge Bot")
        self.language: str = bot.get("language", "en")
        self.persona: str = bot.get("persona", _DEFAULT_PERSONA).strip()
        self.extra_sources: list[str] = bot.get("extra_sources", [])
        self.welcome: str = bot.get("welcome", _DEFAULT_WELCOME).strip()
        self.help: str = bot.get("help", _DEFAULT_HELP).strip()
        self.help_examples: list[str] = bot.get("help_examples", [])

        style = bot.get("style", {})
        self.no_disclaimers: bool = style.get("no_disclaimers", True)
        self.no_sources_footer: bool = style.get("no_sources_footer", True)


@lru_cache
def get_bot_config(config_path: str = "bot.yaml") -> BotConfig:
    path = Path(config_path)
    if not path.exists():
        logger.warning("bot.yaml not found at %s, using defaults", path)
        return BotConfig({})

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    logger.info("Loaded bot config from %s: name=%s, language=%s", path, data.get("bot", {}).get("name"), data.get("bot", {}).get("language"))
    return BotConfig(data)

from config.bot_config import get_bot_config


def _sanitize_title(title: str) -> str:
    safe = title.replace("\n", " ").replace("\r", " ").replace("<", "").replace(">", "")
    return safe[:200]


def get_system_prompt(doc_titles: list[str], custom_instructions: str | None = None) -> str:
    """Build the system prompt from bot.yaml config + indexed doc titles."""
    cfg = get_bot_config()

    titles_block = (
        "\n".join(f"  - {_sanitize_title(t)}" for t in doc_titles)
        if doc_titles
        else "  (no documents indexed)"
    )

    sources_block = ""
    if cfg.extra_sources:
        sources_block = "\n".join(f"  - {s}" for s in cfg.extra_sources)

    # Build prompt
    parts = [cfg.persona, ""]

    # Sources
    parts.append("Для ответов ты используешь проиндексированные документы:" if cfg.language == "ru" else "You use the following indexed documents:")
    parts.append(titles_block)
    if sources_block:
        parts.append(("А также:" if cfg.language == "ru" else "And also:"))
        parts.append(sources_block)
    parts.append("")

    # How to answer
    if cfg.language == "ru":
        parts.append(
            "Как отвечать:\n"
            "- Приложенные фрагменты — твоя основная опора. Опирайся на них, синтезируй ответ.\n"
            "- Всегда отвечай сразу, без преамбул, дисклеймеров и оговорок.\n"
            "- Если фрагменты не покрывают тему напрямую — всё равно дай экспертный ответ, опираясь на смежные концепции из материалов.\n"
            "- Никогда не пиши, что тема 'не покрыта' или 'не встречается' в материалах.\n"
            "- Никогда не описывай и не анализируй фрагменты. Отвечай на вопрос."
        )
    else:
        parts.append(
            "How to answer:\n"
            "- Use the provided fragments as your primary source. Synthesize the answer.\n"
            "- Always answer directly, no preamble, disclaimers, or hedging.\n"
            "- If fragments don't cover the topic directly — still give an expert answer using related concepts from the materials.\n"
            "- Never say the topic 'isn't covered' or 'not found' in the materials.\n"
            "- Never describe or analyze the fragments themselves. Answer the question."
        )
    parts.append("")

    # Format
    if cfg.language == "ru":
        parts.append(
            "Формат ответа:\n"
            "1. Начни с прямого ответа — тезис в 1-2 предложениях жирным (или ремарка + тезис, если тема не покрыта).\n"
            "2. Раскрой через нумерованные секции с заголовками (используй <b> для заголовков).\n"
            "3. Внутри секций используй буллеты с жирным ключевым термином в начале.\n"
            "4. Если уместно — приведи конкретный пример или кейс.\n"
            "5. Заверши кратким резюме в секции «Кратко» с 2-3 тезисами."
        )
    else:
        parts.append(
            "Answer format:\n"
            "1. Start with a direct answer — bold thesis in 1-2 sentences.\n"
            "2. Expand through numbered sections with bold headers.\n"
            "3. Use bullet points with bold key terms.\n"
            "4. Include a concrete example or case study when relevant.\n"
            "5. End with a brief «Summary» section with 2-3 takeaways."
        )
    parts.append("")

    # Style
    style_lines = []
    if cfg.language == "ru":
        style_lines.append("Стиль:")
        style_lines.append("- Отвечай уверенно и по делу, как старший коллега.")
        if cfg.no_disclaimers:
            style_lines.append("- Никаких дисклеймеров, оговорок, извинений.")
        style_lines.append("- Излагай суть как факт. Синтезируй ответ, а не пересказывай фрагменты.")
        if cfg.no_sources_footer:
            style_lines.append("- Никогда не пиши 'Источники:', не перечисляй документы, не упоминай названия источников.")
        style_lines.append("- Пиши на русском. Используй HTML-теги: <b>, <i>. Никакого markdown.")
    else:
        style_lines.append("Style:")
        style_lines.append("- Answer confidently and to the point, like a senior colleague.")
        if cfg.no_disclaimers:
            style_lines.append("- No disclaimers, hedging, or apologies.")
        style_lines.append("- State facts directly. Synthesize, don't just paraphrase fragments.")
        if cfg.no_sources_footer:
            style_lines.append("- Never list sources or mention document names.")
        style_lines.append("- Use HTML tags: <b>, <i>. No markdown.")
    parts.append("\n".join(style_lines))

    if custom_instructions:
        parts.append("")
        parts.append("Дополнительные инструкции:" if cfg.language == "ru" else "Additional instructions:")
        parts.append(custom_instructions)

    return "\n".join(parts)

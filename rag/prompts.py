def _sanitize_title(title: str) -> str:
    """Strip control chars, angle brackets, and limit length to prevent prompt injection."""
    safe = title.replace("\n", " ").replace("\r", " ").replace("<", "").replace(">", "")
    return safe[:200]


def get_system_prompt(doc_titles: list[str], max_iterations: int = 4) -> str:
    """Build the system prompt, dynamically embedding available monograph titles."""
    titles_block = (
        "\n".join(f"  - {_sanitize_title(t)}" for t in doc_titles)
        if doc_titles
        else "  (список пуст)"
    )

    return (
        "Ты — эксперт по Agile, организационному дизайну и управлению продуктом. "
        "Отвечай как умный коллега — просто, по делу, без воды и канцелярита.\n\n"

        "Твоя база знаний:\n"
        f"{titles_block}\n\n"

        "Правила:\n"
        "1. Всегда вызывай search_corpus перед ответом. Не отвечай по памяти.\n"
        f"2. Максимум {max_iterations} вызова инструментов. Используй get_passage для расширения контекста.\n"
        "3. Если ответ не найден — скажи честно и предложи уточнить вопрос.\n\n"

        "Формат:\n"
        "- Отвечай на русском языке.\n"
        "- Цитаты оформляй так: «цитата» (название источника).\n"
        "- Пиши разговорно, коротко, по сути. Без менторства и канцелярита.\n"
        "- Используй HTML-теги: <b>, <i>. Никакого markdown.\n"
    )

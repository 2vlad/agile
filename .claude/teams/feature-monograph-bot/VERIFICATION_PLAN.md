# Verification Plan
## Feature: Telegram Monograph RAG Bot

## Build & Types
- [ ] `docker-compose build` passes
- [ ] `python -c "from config.settings import Settings; print('OK')"` no import errors
- [ ] `python -c "from bot.main import app; print('OK')"` no import errors
- [ ] `python -c "from indexer.main import main; print('OK')"` no import errors

## Tests
- [ ] `python -m pytest tests/ -v` all pass (if tests exist)

## Spec Checks
- [ ] File `config/settings.py` exists and exports `Settings` class
- [ ] File `db/schema.sql` exists and contains CREATE TABLE statements
- [ ] File `db/connection.py` exists and exports `get_pool`, `init_db`
- [ ] File `db/repositories.py` exists and exports `DocumentRepo`, `ChunkRepo`, `RequestRepo`
- [ ] File `indexer/parsers.py` exists and exports `parse_file`, `ParsedDocument`
- [ ] File `indexer/chunker.py` exists and exports `chunk_text`, `Chunk`
- [ ] File `indexer/main.py` exists and is executable as module
- [ ] File `yandex/ai_studio.py` exists and exports `YandexAIStudio`
- [ ] File `rag/tools.py` exists and exports `search_corpus`, `get_passage`, `TOOL_SCHEMAS`
- [ ] File `rag/agent.py` exists and exports `run_agent`, `AgentResult`
- [ ] File `rag/prompts.py` exists and exports system prompt generation
- [ ] File `bot/main.py` exists and exports FastAPI `app`
- [ ] File `bot/handlers.py` exists with command and message handlers
- [ ] File `bot/telegram_utils.py` exists and exports `split_html_message`
- [ ] File `Dockerfile` exists
- [ ] File `docker-compose.yml` exists
- [ ] File `Makefile` exists with targets: index, bot
- [ ] File `.env.example` exists with all required env vars
- [ ] File `requirements.txt` exists
- [ ] Directory `corpus/` exists with monograph files
- [ ] No hardcoded secrets in any Python file (grep for patterns like `token=`, `api_key=` with literal values)
- [ ] `.conventions/` directory exists with gold-standards/

## Human Checks
- [ ] Bot responds to /start command in Telegram
  → Set TELEGRAM_TOKEN in .env, run `make bot`, send /start in Telegram
- [ ] Bot answers questions with citations from corpus
  → Ask "что автор говорит об Agile организациях?" and verify citations appear
- [ ] Indexer processes corpus files
  → Run `make index` and verify summary report shows indexed documents
- [ ] Long answers split correctly in Telegram
  → Ask a broad question that generates >4000 chars response

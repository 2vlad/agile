.PHONY: index bot local deploy setup up down

# ── Quick start ───────────────────────────────────────
setup:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d db
	@echo "DB ready at localhost:5432. Edit .env, then: make local"

up:
	docker compose up -d

down:
	docker compose down

# ── Local development ─────────────────────────────────
local:
	WEBHOOK_URL="" uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

# ── Webhook mode (needs WEBHOOK_URL in .env) ──────────
bot:
	uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

# ── Indexer CLI ───────────────────────────────────────
index:
	python -m indexer.main

# ── Cloud deploy ──────────────────────────────────────
deploy:
	docker build --platform linux/amd64 -t cr.yandex/crpklb64osqn44g087ms/agile-bot:latest .
	docker push cr.yandex/crpklb64osqn44g087ms/agile-bot:latest
	@echo "Image pushed. Run 'make deploy-yc' to update the container."

deploy-yc:
	@./scripts/deploy.sh

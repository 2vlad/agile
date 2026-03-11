.PHONY: index bot local deploy docker-build docker-up docker-down docker-index

# ── Local development ──────────────────────────────────
# Run bot locally with polling (no public URL needed)
local:
	WEBHOOK_URL="" uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

# Run bot in webhook mode (needs WEBHOOK_URL in .env)
bot:
	uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

index:
	python -m indexer.main

# ── Cloud deploy ───────────────────────────────────────
deploy:
	docker build --platform linux/amd64 -t cr.yandex/crpklb64osqn44g087ms/agile-bot:latest .
	docker push cr.yandex/crpklb64osqn44g087ms/agile-bot:latest
	@echo "Image pushed. Run 'make deploy-yc' to update the container."

deploy-yc:
	@./scripts/deploy.sh

# ── Docker (local) ─────────────────────────────────────
docker-build:
	docker build -t monograph-bot .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-index:
	docker-compose run --rm indexer

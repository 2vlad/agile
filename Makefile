.PHONY: index bot dev docker-up docker-down docker-build

index:
	python -m indexer.main

bot:
	uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

dev:
	docker-compose up -d postgres
	uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

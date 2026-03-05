.PHONY: index bot docker-build docker-up docker-down docker-index

index:
	python -m indexer.main

# Local dev server with hot reload
bot:
	uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload

docker-build:
	docker build -t monograph-bot .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-index:
	docker-compose run --rm indexer

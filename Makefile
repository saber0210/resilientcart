.PHONY: up down clean logs test lint smoke benchmark contention

up:
	docker compose up --build -d

logs:
	docker compose logs -f --tail=150

down:
	docker compose down

clean:
	docker compose down -v --remove-orphans

test:
	docker compose run --rm --no-deps gateway pytest -q

lint:
	docker compose run --rm --no-deps gateway ruff check app tests --select E9,F63,F7,F82

smoke:
	python scripts/smoke_test.py

benchmark:
	mkdir -p benchmark-results
	locust -f load-tests/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 10m --host http://localhost:8080 --csv benchmark-results/load

contention:
	python scripts/contention_test.py --attempts 1000 --stock 100

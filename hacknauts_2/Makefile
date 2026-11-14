.PHONY: up down logs test fe
up:    ## build and start everything
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f api worker
test:  ## backend unit tests (needs: pip install -r backend/requirements.txt pytest)
	cd backend && python -m pytest -q
fe:    ## frontend dev server with hot reload
	cd frontend && npm install && npm run dev

# Wordle Race. Needs only git, make and Docker (Compose v2).

# Public port. Override with: make setup WEB_PORT=9090
WEB_PORT ?= 8080
export WEB_PORT

.PHONY: setup down clean logs

# Build the images and start everything. --wait returns once the healthchecks pass.
setup:
	docker compose up --build -d --wait
	@echo Wordle Race is running at http://localhost:$(WEB_PORT)

# Stop and remove the containers. The game database volume is kept.
down:
	docker compose down

# Stop everything and delete all state: containers, network and the database volume.
clean:
	docker compose --profile test down -v --remove-orphans

# Follow the logs of all services.
logs:
	docker compose logs -f --tail=100

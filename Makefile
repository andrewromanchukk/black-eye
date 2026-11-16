# Shortcuts. The only command you need is `make up` (= docker compose up --build).
.PHONY: up down reset logs test shell

up:      ## build and start everything (db, web, scheduler)
	docker compose up --build

down:    ## stop containers (data is kept)
	docker compose down

reset:   ## stop and DELETE the local database volume
	docker compose down -v

logs:
	docker compose logs -f web scheduler

test:    ## run the test suite inside the web container
	docker compose run --rm -e SEED_DEMO=0 web python manage.py test tests

shell:
	docker compose exec web python manage.py shell

# 02: Каркас проєкту: Django, середовища, Postgres, healthcheck

**What to build:** Розробник клонує репозиторій, копіює `.env.example`, запускає Postgres через docker compose і `manage.py runserver` — і бачить робочу головну сторінку та `/healthz`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Налаштування читаються лише зі змінних оточення (local/staging/production)
- [x] `docker compose up db` піднімає Postgres; без `DATABASE_URL` працює SQLite
- [x] `GET /healthz` повертає 200 і перевіряє з'єднання з БД
- [x] README описує запуск за 5 команд

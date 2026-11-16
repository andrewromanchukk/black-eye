# Зафіксоване середовище збірки

**Проблема:** різні версії Python і системних бібліотек на машинах розробників → «у мене збирається, у тебе ні».
**Результат:** кожна збірка — локально, на CI в майбутньому чи на сервері — йде в тому самому середовищі.

## Що зафіксовано

| Шар | Де | Значення (16.11.2026) | Як зафіксовано |
|---|---|---|---|
| Golden base image | `docker/base/Dockerfile` | `zapik-base` — див. `docs/base-image.md` | збирається з зафіксованих шарів нижче; у production — за digest з ECR |
| ОС + Python | `docker/base/Dockerfile` | `python:3.13.18-slim-trixie` (Debian 13) | точний патч Python + реліз Debian + **digest** `sha256:e48f59cd…ed90` |
| pip | `docker/base/Dockerfile` | 26.3 | `ARG PIP_VERSION` |
| tini (PID 1) | `docker/base/Dockerfile` | 0.19.0-3+b8 | `ARG TINI_VERSION`, `apt-get install tini=…` |
| Python-пакети | `requirements.txt` | 8 пакетів, включно з транзитивними | lock-файл з хешами для всіх платформ; `pip install --require-hashes --no-deps` + `pip check` |
| Прямі залежності | `requirements.in` | Django 5.2.19, DRF 3.18.3, … | точні версії; джерело для lock-файла |
| PostgreSQL | `docker-compose.yml` | `postgres:16.16-alpine3.24` | точна версія + реліз Alpine + **digest** `sha256:81e77a48…c2e` |
| Інші OS-пакети (apt) | `docker/base/Dockerfile` | лише tini | `apt-get install пакет=ВЕРСІЯ` |
| Python поза Docker | `.python-version` | 3.13.18 | для pyenv/uv/asdf |

### Чому digest, а не лише тег
Теги офіційних образів перезбираються. Приклад, зафіксований під час налаштування: `postgres:16.15-alpine3.24` 26.10.2026 вказував на `sha256:0cefaabd…`, а 06.11.2026 — уже на `sha256:aa6cb33c…`. Тег той самий, вміст інший. Digest незмінний: інший вміст = інший digest.

Digest у Dockerfile і compose — це **multi-arch index**, тож працює і на amd64 (Linux/Windows), і на arm64 (Mac M1+).

## Як оновлювати (свідомо, а не випадково)

**Python-пакет:**
1. Змінити версію в `requirements.in`.
2. Перегенерувати lock (з Python 3.13, напр. у контейнері):
   `docker compose run --rm --no-deps web sh -c "pip install -q pip-tools && pip-compile --generate-hashes --strip-extras --no-emit-index-url --output-file=requirements.txt requirements.in"`
3. `docker compose build && make test`, закомітити обидва файли.

**Базовий образ (безпекові оновлення ОС, новий патч Python/Postgres):**
1. Отримати digest: `docker buildx imagetools inspect python:3.13.X-slim-trixie --format '{{json .Manifest.Digest}}'`
2. Замінити тег і digest у `docker/base/Dockerfile` / `docker-compose.yml`, оновити `.python-version`, дату в коментарі й таблицю вище.
3. `docker compose build && make test`.

Рекомендований ритм: раз на місяць або одразу при CVE. Пізніше це можна доручити Renovate/Dependabot (вони вміють оновлювати і digest, і lock-файл через PR).

## Перевірка
`scripts/verify_pins.sh` (потрібен Docker з доступом до Docker Hub) показує, чи збігаються зафіксовані digest з тим, що зараз віддає реєстр під цими тегами, і чи синхронізований `requirements.txt` з `requirements.in`. «DIFF» по образу не означає помилку збірки — лише те, що тег перезібрано і можна свідомо оновитись.

## Звідки взяті digest
Docker Hub API (`hub.docker.com/v2/repositories/library/<image>/tags/<tag>`), 16.11.2026. Для кожного образу digest конкретного тегу збігся з digest плаваючого тегу (`3.13-slim-trixie`, `16-alpine`), отриманим окремим запитом. Реєстри образів із середовища, де це налаштовувалось, заблоковані, тому реальний `docker pull` за digest ще треба виконати на машині розробника.

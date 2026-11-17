# Golden base image `zapik-base`

Один спільний, зафіксований і централізовано оновлюваний образ середовища виконання для всіх Python-сервісів Zapik (зараз `web` і `scheduler`, далі — воркери, API для мобільного застосунку тощо).

## Шари

```
python:3.13.18-slim-trixie@sha256:e48f…   ← офіційний образ (Debian 13, Python 3.13.18; уже містить ca-certificates, netbase, tzdata)
└── zapik-base  (docker/base/Dockerfile)    ← tini=0.19.0-3+b8, pip 26.3, користувач app (uid/gid 10001), /app, OCI-мітки
    └── zapik-web  (Dockerfile)             ← requirements.txt з хешами + код + collectstatic, USER app
```

| Що | Де фіксується |
|---|---|
| ОС + Python | `ARG PYTHON_IMAGE` (тег + digest) у `docker/base/Dockerfile` |
| OS-пакети | `ARG TINI_VERSION` (точна версія Debian); інші пакети — так само `пакет=версія` |
| pip | `ARG PIP_VERSION` |
| uid/gid | `ARG APP_UID=10001` — однакові права на файли всюди |
| PID 1 | `tini` — коректне завершення по SIGTERM у ECS/Docker, збирання зомбі-процесів |

## Як використовується

| Де | Як потрапляє в збірку застосунку |
|---|---|
| Локально, `docker compose up` | Сервіс `base` (`scale: 0`, не запускається) збирає `zapik-base:local`; `web` отримує його як build context `base` (`FROM base`). Одна команда, як і раніше. |
| Звичайний `docker build` | `scripts/base-image.sh build && docker build --build-arg BASE_IMAGE=zapik-base:local .` |
| Staging / production | `docker build --build-arg BASE_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/zapik-base@sha256:<digest> .` — **завжди за digest** |

## Публікація в ECR

```bash
AWS_ACCOUNT_ID=123456789012 AWS_REGION=eu-central-1 scripts/base-image.sh push
```
- збирає для `linux/amd64` і `linux/arm64` (buildx), пушить у репозиторій `zapik-base` (створює його з `IMMUTABLE` тегами і скануванням уразливостей при пуші);
- тег: `py3.13.18-trixie-YYYYMMDD-<git sha>`;
- друкує рядок `BASE_IMAGE=…@sha256:…` — його й фіксуємо для збірок застосунку.

## Оновлення (ритм: раз на місяць або одразу при CVE)
1. Оновити потрібне в `docker/base/Dockerfile`: digest Python (див. `docs/build-environment.md`), `TINI_VERSION` (`https://api.ftp-master.debian.org/madison?package=tini&s=trixie`), `PIP_VERSION`.
2. `docker compose up --build` + `make test`.
3. `scripts/base-image.sh push` → новий digest → оновити `BASE_IMAGE` у налаштуваннях збірки staging/production.

⚠️ Точна версія apt-пакета зникає з дзеркал Debian, коли виходить новіша збірка (напр. `+b9`). Тоді збірка base-образу впаде з «version not found» — це сигнал свідомо оновити `TINI_VERSION`. Вже опубліковані в ECR образи це не зачіпає. Якщо потрібна повна відтворюваність apt навіть для старих версій — підключати `snapshot.debian.org` (поки не потрібно).

## Що свідомо не входить
- залежності застосунку (`requirements.txt`) — в образі застосунку, щоб base не перезбирати на кожну зміну пакетів;
- `apt-get upgrade` — робить збірку невідтворюваною; оновлення ОС приходять через новий digest офіційного образу;
- компілятори/dev-заголовки — `psycopg[binary]` їх не потребує; якщо знадобляться, використовувати multi-stage збірку, щоб не тягнути їх у runtime.

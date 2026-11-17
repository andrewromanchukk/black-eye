# ADR-0004: Власний golden base image

**Status:** accepted · 2026-11-16

## Context
ADR-0003 зафіксував середовище збірки в одному Dockerfile. З появою кількох сервісів (web, scheduler, далі — воркери, мобільний API) і ECS у production потрібне одне місце, де визначено й централізовано оновлюється runtime.

## Decision
`docker/base/Dockerfile` → образ `zapik-base`: офіційний Python за digest, зафіксовані tini і pip, користувач `app` з фіксованим uid 10001, tini як PID 1. Публікується в ECR (immutable теги, scan on push) скриптом `scripts/base-image.sh`; застосунки збираються `FROM` нього за digest. Локально compose збирає його автоматично (сервіс `base`, `scale: 0`, `additional_contexts: service:base`) — запуск лишається однією командою.

## Consequences
- Безпекові оновлення ОС робляться один раз для всіх сервісів.
- Збірки застосунку швидші й однакові.
- З'являється процес: місячне оновлення base + оновлення digest у збірках (пізніше — Renovate).
- Точні версії apt-пакетів можуть зникнути з дзеркал Debian → збірка base падає, поки не оновити версію (свідомо).

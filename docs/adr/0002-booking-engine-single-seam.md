# ADR-0002: Booking engine — єдиний шов для доступності

**Status:** accepted · 2026-11-13

## Decision
Усі правила доступності (години, крок, горизонт, мінімальне попередження, активні Bay, прив'язка Service до Bay, перетин бронювань) живуть лише в `apps/booking/engine.py`, з інтерфейсом `available_slots` / `book` / `set_status`. `book` перевіряє доступність повторно в транзакції з `SELECT … FOR UPDATE` на Bay цього Workshop.

## Consequences
- Подвійний запис неможливий навіть при паралельних запитах (тест `tests/test_concurrency.py`).
- Запис на Workshop серіалізується. Для майстерні на 1–4 стенди це не проблема; якщо колись стане вузьким місцем — перейти на exclusion constraint PostgreSQL (`tstzrange` + `btree_gist`).

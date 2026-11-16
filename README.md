# Zapik

Онлайн-запис для шиномонтажів і автосервісів. Водій сам обирає вільний термін на сторінці `/w/<warsztat>/`, власник бачить розклад дня по стендах, веде облік зберігання шин і надсилає сезонні нагадування.

**Статус:** прототип (MVP). Остання версія завжди в гілці `dev`.

## Стек
Python 3.13 · Django 5.2 · Django REST Framework · PostgreSQL 16 · Docker / docker compose. Без CI/CD на цьому етапі.

## Швидкий старт (Docker)
```bash
cp .env.example .env
docker compose up --build          # Postgres + застосунок, міграції запускаються автоматично
docker compose exec web python manage.py seed_demo
```
Відкрийте http://localhost:8000. Демо: `/w/opony-kowalski/`, панель — `demo@zapik.pl` / `ZapikDemo2026`.

## Запуск без Docker для застосунку (Postgres у контейнері)
```bash
cp .env.example .env
docker compose up -d db
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
```

## SMS (SMSAPI.pl)
Локально SMS пишуться в консоль. Для реальної відправки в `.env`:
```
SMS_BACKEND=apps.notifications.backends.SmsapiBackend
SMSAPI_TOKEN=<OAuth-токен з панелі SMSAPI>
SMSAPI_SENDER=<зареєстроване ім'я відправника, необов'язково>
```
Нагадування за добу: `python manage.py send_visit_reminders` щогодини (див. `docs/environments.md`).

## Тести
```bash
python manage.py test tests        # 64 тести на PostgreSQL
```

## Структура
| Шлях | Що там |
|---|---|
| `apps/booking/engine.py` | **Booking engine** — усі правила доступності: `available_slots`, `book`, `set_status` |
| `apps/workshops` | Workshop, години роботи, стенди (Bay), послуги |
| `apps/booking` | Customer, Booking, повідомлення про запис |
| `apps/storage` | Przechowalnia: зберігання шин і сезонні нагадування |
| `apps/booking/reservations.py` | Єдиний шлях запису (онлайн/ручний) + SMS-підтвердження |
| `apps/booking/customers.py` | Один клієнт на телефон, пошук, історія |
| `apps/booking/reminders.py` | Нагадування за добу (`manage.py send_visit_reminders`, щогодини) |
| `apps/workshops/tenancy.py` | Seam ізоляції: поточна майстерня і її дані |
| `apps/notifications` | `send_sms()` + журнал `SmsMessage`; бекенди: лог, SMSAPI.pl |
| `apps/web` | Веб-сторінки: лендинг, юридичні, запис клієнта, панель власника |
| `apps/api` | REST API v1 для майбутнього мобільного застосунку |
| `design/` | `tokens.css`, `kit.css` (джерело правди для UI) і статичний прототип `design/prototype/` |
| `design-system/zapik/MASTER.md` | Дизайн-система (ui-ux-pro-max) |
| `docs/spec/01-mvp-spec.md` | Специфікація MVP (#1) |
| `docs/issues/` | Тікети #2–#16 (опубліковані в GitHub Issues) |
| `docs/adr/` | Архітектурні рішення |
| `docs/environments.md` | Середовища local/staging/production і стадії |
| `GLOSSARY.md` | Словник домену |
| `docs/journal/JOURNAL.md` | Журнал проєкту для ретроспективи |
| `CLAUDE.md` | Інструкції для агента (включно з веденням журналу) |

## REST API v1 (коротко)
| Метод | Шлях | Опис |
|---|---|---|
| POST | `/api/v1/auth/token/` | `{"username": email, "password"}` → токен |
| GET/PATCH | `/api/v1/workshop/` | Дані майстерні |
| CRUD | `/api/v1/bays/`, `/api/v1/services/` | Стенди, послуги |
| GET | `/api/v1/bookings/?date=YYYY-MM-DD` | Розклад дня |
| POST | `/api/v1/bookings/` | Ручний запис (дзвінок) |
| POST | `/api/v1/bookings/{id}/status/` | `completed` / `no_show` / `cancelled` |
| GET/POST | `/api/v1/tire-deposits/?q=` | Зберігання шин |
| POST | `/api/v1/tire-deposits/{id}/return/`, `/api/v1/tire-deposits/remind/` | Видача, нагадування |
| GET | `/api/v1/customers/?q=` | Пошук клієнтів (ім'я, телефон, номер авто) |
| GET | `/api/v1/customers/{id}/` | Картка: візити, авто, шини |
| GET | `/api/v1/public/workshops/{slug}/` | Публічно: майстерня й послуги |
| GET | `/api/v1/public/workshops/{slug}/services/{id}/slots/?date=` | Публічно: вільні слоти |
| POST | `/api/v1/public/workshops/{slug}/bookings/` | Публічно: запис (409, якщо слот зайняли) |

Власницькі ендпоінти: заголовок `Authorization: Token <key>`.

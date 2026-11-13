# #17 — Специфікація: готовність до пілоту

> Скіл **to-spec**, на основі прототипу (#1–#16), огляду архітектури і прогалин аудиту. Статус: `ready-for-agent`.
> Тікети: #18–#24.

## Problem Statement

Прототип працює, але показати його 3–5 реальним шиномонтажам ще не можна:

- **SMS не надсилаються**, лише пишуться в лог. Водій не отримує підтвердження і посилання на скасування, а сезонні нагадування нікуди не йдуть.
- **Пропущені візити** коштують майстерні 100–300 zł кожен, а нагадування напередодні візиту немає.
- **Історії клієнта немає** (user story 33 зі специфікації #1 не реалізована): власник не бачить, що Jan із WWL12345 був тут восени і його шини лежать на регалі B3.
- **Код не готовий до третього adapter (мобільний застосунок):** правило «онлайн-запис = згода + бронювання + SMS» повторено у вебі та API; фільтр за Workshop кожна в'юха пише сама; Customer створюється за різними правилами в бронюванні та в przechowalni.

## Solution

- Реальні SMS через **SMSAPI.pl** з журналом кожного повідомлення (кому, що, статус, помилка); локально і в тестах — як і раніше, без зовнішніх викликів.
- **Нагадування за добу до візиту** з посиланням на скасування; власник вмикає/вимикає їх у налаштуваннях.
- **Картка клієнта:** візити, номери авто, шини в przechowalni; пошук клієнтів за ім'ям, телефоном або номером авто.
- **Три поглиблення архітектури** з огляду: module `reservations`, seam `tenancy`, module `customers`.

## User Stories

1. As a Customer, I want an SMS confirmation right after booking, so that I have the date, address and cancel link on my phone.
2. As a Customer, I want an SMS the day before my visit, so that I don't forget it.
3. As a Customer, I want the reminder to include the cancel link, so that I can free the slot if my plans changed.
4. As a Customer, I want to receive the season reminder as a real SMS, so that I can book the tire swap.
5. As an Owner, I want visit reminders on by default, so that no-shows drop without configuration.
6. As an Owner, I want to switch visit reminders off, so that I control messages sent in my name.
7. As an Owner, I want to see a log of SMS sent by my workshop (date, phone, type, status), so that I can check what my customers received.
8. As an Owner, I want a failed SMS to never block a booking, so that the customer still gets the slot.
9. As an Owner, I want to open a customer card from a booking in the schedule, so that I see who is coming.
10. As an Owner, I want the customer card to show all past and future visits with status, so that I know reliable and unreliable customers.
11. As an Owner, I want the customer card to show the customer's cars (plates), so that I recognise them.
12. As an Owner, I want the customer card to show tire sets in storage, so that I prepare them before the visit.
13. As an Owner, I want to search customers by name, phone or plate, so that I find a card in seconds when they call.
14. As an Owner, I want each customer to exist once per phone number, whether they came via booking or via storage, so that history is not split.
15. As an Owner, I want the latest name given by a customer to be kept, so that the card shows the current name.
16. As a future mobile app, I want customer search and customer card in the API, so that the owner can use them on the phone.
17. As a future mobile app, I want the visit-reminder switch in the workshop API, so that settings match the web.
18. As a developer, I want one module that performs online and manual reservations including notifications, so that web, API and mobile cannot diverge.
19. As a developer, I want one seam that resolves the current Workshop and scopes queries, so that a new view cannot leak another workshop's data.
20. As a developer, I want SMS provider credentials only in environment variables, so that secrets never land in git.

## Implementation Decisions

- **`apps/booking/reservations.py` (deep module):** `reserve_online(workshop, service, start, details, consent)`, `reserve_manual(workshop, service, start, details)`, `cancel_by_customer(token)`. Він викликає Booking engine, перевіряє згоду і ставить SMS-підтвердження на `transaction.on_commit`. Веб і API лише перекладають `SlotUnavailable` / `InvalidBooking` / `ConsentRequired` у redirect, 409 чи 400. `engine` лишається чистим (без повідомлень).
- **`apps/workshops/tenancy.py` (seam):** `current_workshop(request)` (кидає `NoWorkshop`) і `scoped(model_or_qs, request)` — QuerySet, відфільтрований за Workshop власника. Веб-адаптер перетворює `NoWorkshop` на 404, API — на 404 DRF. Усі в'юхи власника використовують лише його.
- **`apps/booking/customers.py`:** `resolve(workshop, name, phone) -> Customer` (нормалізація телефону, створення або оновлення імені), `search(workshop, q)`, `history(customer)` (візити, номери авто, депозити шин). І бронювання, і przechowalnia ходять через `resolve`.
- **SMS:**
  - `SmsapiBackend`: `POST https://api.smsapi.pl/sms.do` з `Authorization: Bearer <SMSAPI_TOKEN>`, поля `to` (48 + 9 цифр), `message`, `from` (`SMSAPI_SENDER`, необов'язково), `format=json`; при мережевій помилці — одна спроба на `https://api2.smsapi.pl/sms.do`. Відповідь з полем `error` вважається помилкою.
  - Інтерфейс розширюється: `send_sms(phone, text, *, workshop, kind)`; `kind` ∈ `booking_confirmation`, `visit_reminder`, `season_reminder`.
  - Модель `SmsMessage` (workshop, phone, kind, text, status `sent`/`failed`, provider_id, error, created_at) — журнал кожного виклику. Помилка провайдера записується в журнал і в лог, але не піднімається вище.
  - HTTP-клієнт — стандартна бібліотека (`urllib`), транспорт підмінний для тестів.
- **Нагадування про візит:** поле `Workshop.visit_reminders` (за замовчуванням увімкнено) і `Booking.reminder_sent_at`. Команда `manage.py send_visit_reminders` надсилає нагадування на підтверджені Booking, що починаються через 20–28 годин і ще не мають нагадування. Запускається щогодини (cron локально, у майбутньому — ECS Scheduled Task). Повторний запуск нічого не дублює.
- **Картка клієнта:** `/panel/klienci/` (пошук) і `/panel/klienci/<id>/`; ім'я клієнта в розкладі веде на картку. API: `GET /api/v1/customers/?q=`, `GET /api/v1/customers/{id}/` з історією.
- **Конфігурація:** `SMS_BACKEND`, `SMSAPI_TOKEN`, `SMSAPI_SENDER`, `SMSAPI_URL`, `SMSAPI_BACKUP_URL` в `.env.example`.

## Testing Decisions

- Тести лише через interface модулів: `reservations.*`, `customers.*`, команда нагадувань, HTTP (веб і API).
- `SmsapiBackend` тестується з підмінним транспортом: перевіряємо URL, заголовок Bearer, поля запиту, фолбек на резервну адресу й обробку `error` — без мережі.
- Нагадування — з фіксованим `now`: потрапляння у вікно 20–28 год, без дубліката при повторному запуску, вимкнений перемикач.
- Ізоляція tenancy: кожен маршрут панелі й API з чужим id повертає 404 (параметризований тест по всіх маршрутах).
- Prior art: `tests/test_engine.py`, `tests/test_web.py`, `tests/test_api.py`.

## Out of Scope

- Оплата підписки, рахунки.
- Передоплата візиту (BLIK).
- Email-повідомлення клієнтам.
- Кілька користувачів на Workshop.
- Деплой на AWS і CI/CD.
- Юридична перевірка текстів (робить юрист окремо).

## Further Notes

- Шви (seams) узгоджені з оглядом архітектури: кандидати 1–3. Кандидат 4 (часовий пояс Workshop) не робимо — немає ринку поза CET.
- Тексти SMS польською; одне SMS ≤ 160 символів без діакритиків або ≤ 70 з ними — тексти підтвердження й нагадування мають вкладатися у 2 частини.

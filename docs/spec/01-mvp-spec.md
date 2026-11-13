# #1 — Специфікація MVP: Zapik, онлайн-запис для шиномонтажів і автосервісів

> Створено скілом **to-spec** на основі ресерчу ніші. Статус: `ready-for-agent`.
> Тікети реалізації: [`docs/issues/`](../issues/) (#2–#16).

## Problem Statement

Власник незалежного шиномонтажу чи автосервісу на 1–4 підйомники двічі на рік (березень–квітень, жовтень–листопад) отримує десятки дзвінків на день. Механіків бракує (75% майстерень шукають працівників, дані SDCM), тож трубку бере той самий механік, що стоїть із ключем біля машини. Запис ведеться в зошиті або в голові. Наслідки: черги на кілька тижнів, накладки, пропущені візити, загублені дзвінки й клієнти, що йдуть до конкурента.

Водій, зі свого боку, не може дізнатися вільний час, не подзвонивши. Наявні рішення — маркетплейси з оплатою за ліди (DobryMechanik), мережеві системи (Premio, Euromaster) або складні програми для майстерень — не підходять маленькому незалежному сервісу, якому потрібен простий календар запису за фіксовану ціну.

## Solution

**Zapik** — простий онлайн-запис для майстерень за фіксовану місячну ціну без комісій.

- Власник за 5 хвилин реєструється, вказує години роботи, стенди (Bay) і послуги з тривалістю — і отримує власну сторінку запису `zapik.pl/w/<nazwa>`, яку ставить у Google Maps, Facebook і на двері.
- Водій відкриває сторінку з телефону, обирає послугу, бачить лише реально вільні терміни, вводить ім'я, телефон і номер авто — і отримує підтвердження з посиланням для скасування.
- Власник бачить розклад дня по стендах, додає записи з телефону вручну, позначає «виконано» / «не прийшов».
- Модуль **przechowalnia** (зберігання шин) веде облік шин клієнтів і перед сезоном формує список нагадувань «час міняти шини — запишіться».

Веб-застосунок будується API-first, щоб наступним кроком додати мобільний застосунок для власника на тому ж API.

## User Stories

### Власник: реєстрація і налаштування
1. As an Owner, I want to sign up with email and password, so that I can start using Zapik without talking to sales.
2. As an Owner, I want to create my Workshop with name, address and phone, so that customers know where to come.
3. As an Owner, I want Zapik to generate a short public booking address from my workshop name, so that I can share it easily.
4. As an Owner, I want to change the public address (slug), so that it matches my brand.
5. As an Owner, I want to set opening hours for each weekday, so that customers can book only when I work.
6. As an Owner, I want to mark a weekday as closed, so that no slots appear on Sundays.
7. As an Owner, I want to add Bays (e.g. "Podnośnik 1", "Stanowisko opon"), so that Zapik knows how many cars I can serve at once.
8. As an Owner, I want to deactivate a Bay temporarily, so that a broken lift does not receive bookings.
9. As an Owner, I want to add Services with name, duration and price, so that customers see what they book and how much it costs.
10. As an Owner, I want to restrict a Service to specific Bays, so that tire changes are only booked on the tire station.
11. As an Owner, I want to hide a Service without deleting it, so that past bookings keep their history.
12. As an Owner, I want to set the slot step (15/30/60 min), so that the schedule matches how I work.
13. As an Owner, I want to set how many days ahead customers can book, so that I control my calendar horizon.
14. As an Owner, I want to set a minimum notice (e.g. 2 hours), so that nobody books a slot that starts in 5 minutes.

### Водій: запис
15. As a Customer, I want to open the workshop page on my phone without installing anything, so that booking takes under a minute.
16. As a Customer, I want to see the list of services with duration and price, so that I know what I pay.
17. As a Customer, I want to choose a date and see only free start times, so that I don't waste time on taken slots.
18. As a Customer, I want to enter only my name, phone and plate number, so that the form is fast.
19. As a Customer, I want to add an optional note (e.g. "mam swoje opony"), so that the workshop is prepared.
20. As a Customer, I want to give explicit consent to the privacy policy, so that my data is processed legally (RODO).
21. As a Customer, I want a confirmation page with date, time, address and service, so that I know the booking succeeded.
22. As a Customer, I want a cancel link, so that I can cancel without calling.
23. As a Customer, I want a clear message if somebody took my slot a second earlier, so that I can choose another one.
24. As a Customer, I want the booking page to be readable and usable on a small phone screen, so that I can book in the car.

### Власник: щоденна робота
25. As an Owner, I want to see today's schedule split by Bays, so that I know what comes next.
26. As an Owner, I want to switch between days, so that I can plan the week.
27. As an Owner, I want to add a booking manually when a customer calls, so that phone and online bookings live in one calendar.
28. As an Owner, I want Zapik to block slots taken by manual bookings too, so that there are no double bookings.
29. As an Owner, I want to mark a booking as completed, so that I track finished work.
30. As an Owner, I want to mark a booking as no-show, so that I know unreliable customers.
31. As an Owner, I want to cancel a booking, so that the slot becomes free again.
32. As an Owner, I want to see customer phone and plate on each booking, so that I can call them.
33. As an Owner, I want to see a customer's previous visits, so that I recognise returning clients.

### Зберігання шин (przechowalnia)
34. As an Owner, I want to register a tire deposit with plate, customer, description (size, brand, rims) and storage location, so that I find the tires quickly.
35. As an Owner, I want to mark which season set is stored (summer/winter), so that I know whom to remind and when.
36. As an Owner, I want to mark a deposit as returned, so that my storage list stays accurate.
37. As an Owner, I want to search deposits by plate or phone, so that I find a set in seconds.
38. As an Owner, I want to generate a season reminder list for all stored sets of one season, so that I can fill my calendar before the rush.
39. As an Owner, I want each reminder to contain a link to my booking page, so that customers book themselves.
40. As an Owner, I want to see which customers were already reminded, so that I don't spam them.

### Акаунт, юридичне, середовища
41. As an Owner, I want to log in and log out securely, so that nobody else manages my workshop.
42. As an Owner, I want to reset my password by email, so that I don't lose access.
43. As a visitor, I want to read Terms (Regulamin) and Privacy Policy (Polityka prywatności), so that I know the rules.
44. As a visitor, I want a landing page explaining Zapik and its price, so that I can decide to sign up.
45. As a future mobile app, I want a versioned REST API with token auth, so that the owner app can use the same backend.
46. As a developer, I want separate local / staging / production settings via environment variables, so that secrets never live in code.

## Implementation Decisions

- **Стек:** Python 3.13, Django 5.2, Django REST Framework, PostgreSQL (локально через docker compose; для швидких тестів допускається SQLite). Той самий стек, що в обговореному кейсі клієнта, тож пізніше він лягає на AWS ECS без змін.
- **API-first:** уся бізнес-логіка живе в доменних модулях; веб-сторінки (Django templates) і REST API v1 (`/api/v1/`) — два тонкі адаптери над ними. Мобільний застосунок власника пізніше використовує той самий API.
- **Booking engine — один глибокий модуль** з двома операціями:
  - `available_slots(workshop, service, date) -> list[Slot]` — усі правила доступності (години роботи, крок, горизонт, мінімальне попередження, активні Bay, обмеження Service до Bay, перетин із наявними Booking).
  - `book(workshop, service, start, customer_data, source) -> Booking` — повторно перевіряє доступність усередині транзакції з блокуванням рядків Bay і обирає перший вільний Bay; кидає `SlotUnavailable`.
  - Веб, API і ручний запис з панелі ходять тільки через ці дві операції.
- **Захист від подвійного запису:** транзакція + `select_for_update` на Bay цього Workshop; перевірка перетину інтервалів `start < other.end AND end > other.start` лише по статусах, що займають час (`confirmed`, `completed`).
- **Час:** зберігається в UTC (`USE_TZ=True`), відображається в `Europe/Warsaw`. Опенінг-години — локальний час Workshop.
- **Customer** унікальний у межах Workshop за нормалізованим телефоном; Plate нормалізується (великі літери, без пробілів).
- **Cancel link:** випадковий токен (`secrets.token_urlsafe`) на кожну Booking.
- **Повідомлення:** модуль `notifications` з одним інтерфейсом `send_sms(phone, text)`; у прототипі — бекенд, що пише в лог/консоль. Реальний SMS-провайдер (напр. SMSAPI.pl) — наступна ітерація.
- **Авторизація:** веб — сесії Django; API — токени DRF (`Authorization: Token …`). Один Owner = один Workshop у MVP (поле `owner` у Workshop), мульти-користувачі — пізніше.
- **Модель даних (скорочено):** Workshop(owner, name, slug, address, phone, slot_step_min, booking_horizon_days, min_notice_min) · OpeningHours(workshop, weekday, opens, closes) · Bay(workshop, name, is_active) · Service(workshop, name, duration_min, price, is_active, bays M2M — порожньо = усі) · Customer(workshop, name, phone) · Booking(workshop, bay, service, customer, plate, start, end, status, source[online/manual], note, cancel_token) · TireDeposit(workshop, customer, plate, season, description, location, status, stored_at, returned_at, reminded_at).
- **Середовища:** `local` / `staging` / `production`, конфігурація лише через змінні оточення (`.env.example`). CI/CD у цьому етапі **свідомо не робимо**.
- **Юридичні сторінки:** шаблони Regulamin і Polityka prywatności (RODO) польською з позначкою «wymaga weryfikacji prawnika»; явна згода в формі запису.
- **Дизайн:** дизайн-система з ui-ux-pro-max (`design-system/zapik/MASTER.md`), токени й компоненти в `design/tokens.css` і `design/kit.css`, які напряму використовуються Django-шаблонами (одне джерело правди).

## Testing Decisions

- Добрий тест перевіряє **зовнішню поведінку** через інтерфейс модуля, а не внутрішні деталі: «який Slot повертається», «чи вдалося зарезервувати», «що бачить користувач на сторінці».
- **Головний шов — Booking engine** (`available_slots`, `book`): години роботи, закритий день, крок, горизонт, мінімальне попередження, неактивний Bay, обмеження Service до Bay, перетин бронювань, вибір вільного Bay, `SlotUnavailable`.
- **Другий шов — HTTP:** Django test client для публічного запису (повний шлях від сторінки до підтвердження й скасування за посиланням) і DRF APIClient для API (авторизація, ізоляція даних між Workshop).
- Prior art: на старті немає — ці тести стають зразком.

## Out of Scope

- Онлайн-оплата й передоплати (BLIK, Przelewy24) — наступна ітерація.
- Реальна відправка SMS/email (є тільки інтерфейс і лог-бекенд).
- Мобільний застосунок (лише API під нього).
- Кілька користувачів і ролей на один Workshop, мережі майстерень.
- Склад запчастин, рахунки, KSeF, CRM, маркетинг.
- Інтеграції з Google Calendar, DobryMechanik, Oponeo.
- CI/CD і деплой на AWS.

## Further Notes

- Робоча назва **Zapik** (домен `zapik.pl` був вільний на 13.11.2026 за RDAP NASK; перевірку торговельної марки ще треба зробити).
- Ціни на лендингу — гіпотеза для перевірки інтерв'ю з 15–20 шиномонтажами.
- Тікети #2–#16 опубліковані в GitHub Issues (мітка `ready-for-agent`); копії лежать у `docs/issues/`. Скрипт `scripts/publish_issues.sh` публікує їх через REST API.

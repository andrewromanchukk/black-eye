# 18: Module reservations: один шлях для онлайн- і ручного запису

**Parent:** #17

**What to build:** Водій, який бронює через веб або API, і власник, який записує дзвінок, проходять через `reservations` — він перевіряє згоду, бронює через Booking engine і ставить SMS-підтвердження. Поведінка для користувачів не змінюється.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `reserve_online`, `reserve_manual`, `cancel_by_customer` з тестами на interface
- [ ] Веб і API не викликають `engine.book` і `notify` напряму
- [ ] Без згоди → `ConsentRequired` (400 в API, помилка форми у вебі)
- [ ] Усі наявні тести зелені

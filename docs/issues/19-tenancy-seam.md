# 19: Seam tenancy: поточна майстерня і ізоляція даних

**Parent:** #17

**What to build:** Кожна сторінка панелі й кожен ендпоінт власника отримують Workshop і об'єкти лише через `tenancy`; чужий id завжди дає 404.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `current_workshop`, `scoped` у одному модулі
- [ ] Жодної в'юхи з власним фільтром `workshop=`
- [ ] Параметризований тест: усі маршрути панелі та API з чужим id → 404

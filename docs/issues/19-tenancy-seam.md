# 19: Seam tenancy: поточна майстерня і ізоляція даних

**Parent:** #17

**What to build:** Кожна сторінка панелі й кожен ендпоінт власника отримують Workshop і об'єкти лише через `tenancy`; чужий id завжди дає 404.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `current_workshop`, `scoped` у одному модулі
- [x] Жодної в'юхи з власним фільтром `workshop=`
- [x] Параметризований тест: усі маршрути панелі та API з чужим id → 404

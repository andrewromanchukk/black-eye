# Середовища і стадії розробки

## Середовища
| | local | staging | production |
|---|---|---|---|
| `DJANGO_ENV` | `local` | `staging` | `production` |
| `DJANGO_DEBUG` | `True` | `False` | `False` |
| База | Postgres у docker compose | RDS PostgreSQL | RDS PostgreSQL (Multi-AZ) |
| SMS | `LogSmsBackend` (консоль) | тестовий провайдер / лог | реальний провайдер |
| Email | console | SES (sandbox) | SES |
| HTTPS, secure cookies, HSTS | ні | так | так |
| Секрети | `.env` | AWS Secrets Manager → змінні оточення ECS | AWS Secrets Manager |

Уся конфігурація — лише через змінні оточення (`.env.example` — повний список). Код однаковий для всіх середовищ.

## Стадії продукту
1. **Prototype (зараз):** усі сценарії MVP працюють локально; SMS у лог; юридичні тексти — чернетки.
2. **Pilot:** 3–5 шиномонтажів; реальний SMS-провайдер; юрист перевіряє Regulamin і Politykę prywatności; домен zapik.pl; staging на AWS.
3. **MVP launch:** оплата підписки, моніторинг і алерти, бекапи RDS, umowa powierzenia (RODO) для майстерень.
4. **Mobile:** застосунок власника на `/api/v1/`.

## Чекліст перед production
- [ ] Регулярні бекапи й тест відновлення БД
- [ ] Логи й алерти (5xx, latency, health check `/healthz`)
- [ ] Rate limiting публічного запису (API вже має throttle 60/хв)
- [ ] Перевірені юристом Regulamin, Polityka prywatności, umowa powierzenia
- [ ] CI/CD (свідомо відкладено на цьому етапі)

## Періодичні задачі
| Команда | Частота | Що робить |
|---|---|---|
| `python manage.py send_visit_reminders` | щогодини | SMS за 20–28 год до підтвердженого візиту; повторний запуск нічого не дублює |

- **local:** `0 * * * * cd /path/to/black-eye && docker compose exec -T web python manage.py send_visit_reminders` (crontab), або запускайте вручну.
- **staging/production:** ECS Scheduled Task (EventBridge, `rate(1 hour)`) з тим самим образом і командою.

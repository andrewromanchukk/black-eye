# 21: Реальні SMS через SMSAPI.pl + журнал повідомлень

**Parent:** #17

**What to build:** Підтвердження запису й сезонні нагадування надходять водієві реальним SMS; власник бачить журнал SMS своєї майстерні; помилка провайдера не ламає запис.

**Blocked by:** #18

**Status:** ready-for-agent

- [ ] `SmsapiBackend` (Bearer, `to`=48XXXXXXXXX, `format=json`, фолбек на api2) з тестами на підмінному транспорті
- [ ] Модель `SmsMessage` і сторінка журналу в панелі
- [ ] Помилка → `status=failed`, запис у лог, бронювання створене
- [ ] Налаштування лише з env (`SMSAPI_TOKEN`, `SMSAPI_SENDER`)

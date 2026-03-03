# Техническое задание: Контроль рентабельности отгрузок по ЛС (Go+React)

**Код проекта:** FM-LS-PROFIT
**Версия ФМ:** 1.0.7
**Версия ТЗ:** 1.0
**Дата:** 03.03.2026
**Автор:** Шаховский А.С.
**Платформа:** Go 1.22+ (Clean Architecture) + React (Next.js 15)
**Репозиторий:** `profitability-service/`
**Архитектура:** Микросервисная, 6 Go-сервисов + React SPA

---

## Содержание

1. [Общая информация](#1-общая-информация)
2. [Сервисы и архитектура](#2-сервисы-и-архитектура)
3. [API Endpoints](#3-api-endpoints)
4. [Модель данных](#4-модель-данных)
5. [Frontend (React)](#5-frontend-react)
6. [Аналитика](#6-аналитика)
7. [Интеграции](#7-интеграции)
8. [Инфраструктура](#8-инфраструктура)
9. [Оценка трудоемкости](#9-оценка-трудоемкости)
10. [Критерии приемки](#10-критерии-приемки)
11. [Риски и ограничения](#11-риски-и-ограничения)
12. [Открытые вопросы](#12-открытые-вопросы)

---

## 1. Общая информация

### 1.1. Назначение системы

Сервис `profitability-service` -- отдельное веб-приложение для контроля рентабельности отгрузок по локальным сметам (ЛС). 1С:УТ 10.2 остается source of truth для оперативных данных. Go-сервис добавляет:

- расчет и хранение рентабельности в реальном времени;
- автоматическую маршрутизацию согласований через ELMA BPM с резервным режимом;
- 3-уровневую аналитику аномалий (детерминистическую, интерпретацию, автономное расследование);
- веб-дашборд с KPI, очередью согласований и отчетами;
- систему уведомлений (Telegram, Email, 1С);
- обратную связь в 1С через Kafka.

### 1.2. Связь с 1С:УТ

| Аспект | 1С:УТ 10.2 | profitability-service |
|--------|-----------|----------------------|
| Ввод данных | Заказы, отгрузки, НПСС, контрагенты | Только чтение (через Kafka) |
| Расчет рентабельности | Инициирует событие при проведении | Выполняет расчет, хранит результат |
| Согласование | Получает результат (callback) | Маршрутизирует, контролирует SLA |
| Отчетность | Базовые отчеты (1С формы) | Расширенные дашборды, прогнозы |
| Аналитика | Нет | 3-уровневая (статистика + Sonnet 4.6 + Opus 4.6) |
| Пользовательский интерфейс | Обычные формы, толстый клиент | React SPA, любой браузер |

### 1.3. Ссылки на документы

| Документ | Ссылка |
|----------|--------|
| Функциональная модель | [ФМ FM-LS-PROFIT](https://confluence.ekf.su/pages/viewpage.action?pageId=83951683) |
| Архитектура 1С | [Архитектура 1С](https://confluence.ekf.su/pages/viewpage.action?pageId=86049550) |
| ТЗ на 1С | [ТЗ 1С](https://confluence.ekf.su/pages/viewpage.action?pageId=86049548) |
| Доменная модель (DDD) | [Phase 1A: Domain Model](https://confluence.ekf.su/pages/viewpage.action?pageId=86049881) |
| Go-архитектура | [Phase 1B: Go Architecture](https://confluence.ekf.su/pages/viewpage.action?pageId=86049882) |
| React-архитектура | [Phase 1C: React Architecture](https://confluence.ekf.su/pages/viewpage.action?pageId=86049883) |
| AI-аналитика | [Phase 1D: AI Analytics](https://confluence.ekf.su/pages/viewpage.action?pageId=86049884) |
| Интеграции | [Phase 1E: Integration Architecture](https://confluence.ekf.su/pages/viewpage.action?pageId=86049885) |
| Дорожная карта | [Jira — Profitability Service](https://jira.ekf.su/secure/RapidBoard.jspa?rapidView=39) |

### 1.4. Основные формулы

**Рентабельность позиции:**
```
Рентабельность = (Цена - НПСС) / Цена x 100%
```

**Накопленная + Заказ:**
```
(Выручка_отгруж + Выручка_заказа - Себест_отгруж(НПСС) - Себест_заказа) /
(Выручка_отгруж + Выручка_заказа) x 100%
```

**Рентабельность остатка ЛС:**
```
SUM((Цена_i - НПСС_i) x Кол_i) / SUM(Цена_i x Кол_i) x 100%
```
где i -- неотгруженные позиции за вычетом позиций Заказов в статусах "На согласовании" и "Согласован".

**Отклонение:**
```
Отклонение = Рент_ЛС(плановая) - MAX(Накопленная+Заказ, Рент_остатка)
Округление: до 2 знаков ДО сравнения с границами
```

**НПСС (нормативная плановая себестоимость):**
```
НПСС = ЦЗсредняя x ТТК_страна
ЦЗсредняя = средневзвешенная цена закупки за 6 месяцев
```

### 1.5. Матрица согласования

| Отклонение (п.п.) | Согласующий | SLA P1 | SLA P2 | SLA <100тр | Автоэскалация |
|-------------------|-------------|--------|--------|------------|---------------|
| < 1,00 | Не требуется | - | - | - | - |
| 1,00 - 15,00 | РБЮ | 4ч | 24ч | 2ч | Директор ДРП |
| 15,01 - 25,00 | ДП | 8ч | 48ч | 4ч | ГД |
| > 25,00 | ГД | 24ч | 72ч | 12ч | Автоотказ 48ч |

**Агрегированные лимиты автосогласования:**
- Менеджер: 20 000 руб/день
- Бизнес-юнит: 100 000 руб/день

### 1.6. Приоритизация (P1 / P2)

- **P1 (MVP):** **64 требования** -- контроль рентабельности, согласование, жизненный цикл, блокировки, базовые отчеты, интеграции, пилотные отчеты
- **P2 (Этап 2):** 19 требований -- обеспечение наличием, санкции за невыкуп, расширенные отчеты

### 1.7. Целевые показатели

| Показатель | Значение |
|-----------|----------|
| Одновременные пользователи | 50-70 |
| Позиций в одной ЛС | до 1000 |
| Заказов на согласовании по одной ЛС | до 50 |
| Расчет рентабельности | < 2 секунд (до 500 позиций) |
| Обработка сообщения из 1С | < 1 секунда |
| Таймаут блокировки ЛС | 5 минут |
| Доступность сервиса | 99.5% (бизнес-часы 08:00-20:00 МСК) |
| Время ответа API (p95) | < 200 мс |

### 1.8. Технологический стек

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Язык (backend) | Go | 1.22+ |
| HTTP-роутер | chi | v5 |
| gRPC | connect-go + buf | - |
| ORM / SQL | sqlc | - |
| Kafka-клиент | franz-go | - |
| Dependency Injection | Wire | - |
| Конфигурация | envconfig | - |
| Логирование | slog (structured) | - |
| Метрики | prometheus/client_golang | - |
| Трейсинг | OpenTelemetry | - |
| Десятичная арифметика | shopspring/decimal | - |
| Frontend-фреймворк | Next.js (App Router) | 15 |
| UI-библиотека | Tailwind CSS + shadcn/ui | - |
| Графики | Recharts | - |
| State management | Zustand + TanStack Query | - |
| База данных | PostgreSQL | 16+ |
| Очередь сообщений | Kafka (KRaft) | 3.7+ |
| Кэш | Redis | 7+ |
| Контейнеризация | Docker + Docker Compose | - |
| Аутентификация | AD (LDAP/Kerberos) -> JWT | - |
| Observability | Langfuse | v3 |

### 1.9. Пользователи и роли

| Роль | Кол-во | Основные функции | Роль в AD |
|------|--------|-----------------|-----------|
| Менеджер по продажам (manager) | ~50 | Просмотр ЛС, создание заказов, корректировка цен | `APP_PROFIT_MANAGER` |
| Руководитель БЮ (rbu) | ~10 | Согласование 1-15 п.п., перелив очереди | `APP_PROFIT_RBU` |
| Директор по продажам (dp) | 1-2 | Согласование 15-25 п.п., аналитика | `APP_PROFIT_DP` |
| Генеральный директор (gd) | 1 | Согласование >25 п.п. | `APP_PROFIT_GD` |
| Финансовый директор (fd) | 1 | Отчеты, мониторинг, настройки, стоимость аналитики | `APP_PROFIT_FD` |
| Аналитик | 2-3 | Отчеты, мониторинг НПСС | `APP_PROFIT_ANALYST` |

---

## 2. Сервисы и архитектура

### 2.1. Схема сервисов

```
                        +-------------------+
                        |   api-gateway     |
                        | (auth, RBAC,      |
                        |  rate limiting)   |
                        +---------+---------+
                                  |
                    +-------------+-------------+
                    |             |             |
           +-------v-------+ +--v----------+ +v--------------+
           | profitability  | | workflow    | | analytics     |
           | service        | | service     | | service       |
           | (calc, LS,     | | (approval,  | | (anomaly,     |
           |  shipments)    | |  SLA, ELMA) | |  reports)     |
           +-------+-------+ +------+------+ +-------+-------+
                   |                |                 |
                   +--------+-------+---------+-------+
                            |                 |
                   +--------v-------+ +-------v--------+
                   | integration    | | notification   |
                   | service        | | service        |
                   | (Kafka, MDM,   | | (Telegram,     |
                   |  outbox, 1C)   | |  Email, 1C)    |
                   +----------------+ +----------------+
```

### 2.2. Протоколы связи

| Маршрут | Протокол | Описание |
|---------|----------|----------|
| Frontend -> api-gateway | REST (HTTPS) | Все запросы пользователей |
| api-gateway -> сервисы | gRPC (connect-go, protobuf) | Внутренняя маршрутизация |
| сервис -> сервис (async) | Kafka (franz-go) | Доменные события |
| сервисы -> integration-service (sync) | gRPC | Чтение MDM-данных |
| сервисы -> PostgreSQL | TCP | Хранение данных |
| сервисы -> Redis | TCP | Кэширование |
| integration-service -> 1С | HTTP REST | Callback (результаты согласования) |
| 1С -> integration-service | HTTP POST | События из 1С (создание/изменение документов) |

### 2.3. Описание сервисов

#### 2.3.1. api-gateway

**Назначение:** Единая точка входа для фронтенда. Аутентификация (AD LDAP/Kerberos -> JWT), авторизация (RBAC по ролям), rate limiting, маршрутизация к внутренним сервисам.

**Функции:**
- Аутентификация через Active Directory (LDAP bind / Kerberos)
- Выдача и валидация JWT-токенов (RS256, TTL 1 час, refresh TTL 24 часа)
- RBAC на основе групп AD -> роли приложения
- Rate limiting: 1000 req/min на пользователя, 10 000 req/min глобально
- Маршрутизация REST-запросов -> gRPC к внутренним сервисам
- CORS, security headers, request logging

**Порт:** 8080 (HTTP), 8443 (HTTPS)

#### 2.3.2. profitability-service

**Назначение:** Расчет рентабельности, управление ЛС и заказами. Ядро бизнес-логики.

**Bounded Context:** Profitability
**Агрегаты:** LocalEstimate, Shipment, ProfitabilityCalculation, PriceSheet

**Функции:**
- Расчет рентабельности позиции, заказа, накопленной, остатка
- Определение уровня согласования по матрице порогов
- Перекрестный контроль при изменении плана ЛС (cross-validation)
- Управление жизненным циклом ЛС (создание, продление, закрытие)
- Кэширование НПСС в Redis (TTL 1 час)
- Проверка агрегированных лимитов автосогласования

**Порт:** 9001 (gRPC), 9101 (HTTP health/metrics)
**БД:** PostgreSQL (schema: profitability)

#### 2.3.3. workflow-service

**Назначение:** Маршрутизация согласований, контроль SLA, интеграция с ELMA BPM.

**Bounded Context:** Workflow
**Агрегаты:** ApprovalProcess, EmergencyApproval

**Функции:**
- Создание процесса согласования (state machine с 11 состояниями)
- Маршрутизация к согласующему по уровню и доступности
- SLA-трекинг: уведомление при 50%, предупреждение при 80%, автоэскалация при 100%
- Поддержка мульти-БЮ согласований
- Корректировка цены (до 5 итераций)
- Экстренные согласования с постфактум-контролем (24ч/48ч)
- Резервный режим ELMA (circuit breaker: 5 ошибок -> open, автосогласование до 5 п.п., очередь FIFO свыше)
- Перелив очереди (>30 задач -> заместитель, >50/день -> назначение доп. ресурса)

**Порт:** 9002 (gRPC), 9102 (HTTP health/metrics)
**БД:** PostgreSQL (schema: workflow)

#### 2.3.4. analytics-service

**Назначение:** 3-уровневая аналитика, отчеты, прогнозы, интерфейс к Claude API.

**Bounded Context:** Analytics
**Агрегаты:** Anomaly, Investigation

**Функции:**
- Уровень 1 (детерминистический): Z-score аномалий (окно 90 дней, порог 2 sigma), ARIMA-прогноз (горизонт 30 дней), 17 бизнес-правил
- Уровень 2 (интерпретация, Sonnet 4.6): объяснение аномалий, суммаризация отчетов, Q&A
- Уровень 3 (расследование, Opus 4.6): автономное расследование с инструментами (max 10 итераций, 60 сек)
- 8 отчетов P1 (рентабельность по ЛС, устаревшие НПСС, низкий выкуп, дашборд эффективности, нагрузка согласующих, базовый замер, промежуточный отчет, конфликты блокировки)
- KPI менеджера/согласующего
- Мониторинг стоимости аналитики (лимит $50/день)

**Порт:** 9003 (gRPC), 9103 (HTTP health/metrics)
**БД:** PostgreSQL (schema: analytics)

#### 2.3.5. integration-service

**Назначение:** Прием событий из 1С, Mini MDM (темпоральные таблицы), обратная связь в 1С, внешние интеграции.

**Bounded Context:** Integration
**Агрегаты:** Client, Sanction, PriceSheet (MDM)

**Функции:**
- HTTP API для приема событий из 1С (POST /api/v1/events, дедупликация по message_id)
- Маршрутизация событий в Kafka (9 входящих топиков)
- Mini MDM: темпоральные таблицы для контрагентов, товаров, НПСС, сотрудников, бизнес-юнитов
- gRPC API для внутренних сервисов (чтение MDM-данных)
- Outbox pattern для публикации доменных событий
- Callback в 1С (результат согласования, санкции, блокировки)
- Получение курсов ЦБ РФ (ежедневно 08:00 МСК)
- Управление санкциями (P2)

**Порт:** 9004 (gRPC), 9104 (HTTP + REST для 1С)
**БД:** PostgreSQL (schema: integration)

#### 2.3.6. notification-service

**Назначение:** Отправка уведомлений по всем каналам.

**Функции:**
- Telegram Bot API: уведомления согласующих, алерты
- Email (SMTP): еженедельные отчеты, эскалации
- 1С (callback): обновление статусов в карточках документов
- Шаблоны уведомлений (по типу события)
- Дедупликация уведомлений (1 уведомление на событие)

**Порт:** 9005 (gRPC), 9105 (HTTP health/metrics)
**БД:** PostgreSQL (schema: notifications)

---

## 3. API Endpoints

### 3.1. profitability-service (REST)

| Метод | Путь | Описание | Роли |
|-------|------|----------|------|
| POST | /api/v1/shipments/{id}/calculate | Рассчитать рентабельность заказа | manager, rbu |
| GET | /api/v1/shipments/{id}/profitability | Получить расчет рентабельности | manager, rbu, dp, gd, fd |
| GET | /api/v1/local-estimates/{id}/summary | Сводка рентабельности по ЛС | manager, rbu, dp, gd, fd |
| GET | /api/v1/local-estimates/{id}/shipments | Список заказов по ЛС (cursor-based) | manager, rbu |
| GET | /api/v1/local-estimates/{id}/remainder | Рентабельность остатка ЛС | manager, rbu |
| GET | /api/v1/shipments/{id} | Детали заказа | manager, rbu, dp, gd, fd |
| GET | /api/v1/dashboard/manager | Панель менеджера: ЛС и заказы | manager |
| GET | /api/v1/price-sheets/{product_id} | Текущая НПСС по товару | manager, rbu, fd |
| GET | /api/v1/price-sheets/stale | Список устаревших НПСС | fd |

### 3.2. workflow-service (REST)

| Метод | Путь | Описание | Роли |
|-------|------|----------|------|
| POST | /api/v1/approvals | Создать заявку на согласование | manager |
| GET | /api/v1/approvals/{id} | Детали согласования | manager, rbu, dp, gd, fd |
| POST | /api/v1/approvals/{id}/decide | Принять решение | rbu, dp, gd |
| POST | /api/v1/approvals/{id}/correct | Предложить корректировку цены | manager |
| GET | /api/v1/approvals/queue | Очередь согласующего | rbu, dp, gd |
| GET | /api/v1/approvals/queue/count | Количество задач в очереди | rbu, dp, gd |
| POST | /api/v1/emergency-approvals | Зафиксировать экстренное согласование | manager |
| POST | /api/v1/emergency-approvals/{id}/confirm | Подтвердить постфактум | rbu, dp, gd |
| GET | /api/v1/approvals/sla/{id} | Оставшееся время SLA | manager, rbu, dp, gd |
| GET | /api/v1/approvals/aggregate-limits | Текущие лимиты менеджера | manager |
| GET | /api/v1/approvals/workload/{approver_id} | Нагрузка согласующего | rbu, dp, gd, fd |
| GET | /api/v1/fallback/status | Статус резервного режима ELMA | fd |
| GET | /api/v1/fallback/queue | Очередь резервного режима | fd |

### 3.3. analytics-service (REST)

| Метод | Путь | Описание | Роли |
|-------|------|----------|------|
| GET | /api/v1/anomalies | Список аномалий | rbu, dp, gd, fd |
| GET | /api/v1/anomalies/{id} | Детали аномалии | rbu, dp, gd, fd |
| GET | /api/v1/anomalies/{id}/investigation | Результат расследования | dp, gd, fd |
| POST | /api/v1/anomalies/{id}/resolve | Отметить как решенную | dp, gd, fd |
| GET | /api/v1/forecasts/profitability | Прогноз рентабельности (ARIMA) | fd |
| GET | /api/v1/reports/daily-efficiency | Дашборд эффективности (LS-RPT-070) | fd |
| GET | /api/v1/reports/npss-age | Возраст НПСС (LS-RPT-071) | fd |
| GET | /api/v1/reports/baseline-kpi | Базовый замер KPI (LS-RPT-073) | fd |
| GET | /api/v1/reports/pilot-progress | Промежуточный отчет пилота (LS-RPT-074) | fd |
| GET | /api/v1/reports/low-fulfillment | Клиенты с низким выкупом (LS-RPT-068) | dp, gd, fd |
| POST | /api/v1/ai/ask | Вопрос аналитика (Q&A) | dp, gd, fd |
| GET | /api/v1/ai/costs | Стоимость аналитики | fd |
| GET | /api/v1/kpi/manager/{id} | KPI менеджера | rbu, dp, gd, fd |
| GET | /api/v1/kpi/approver/{id}/workload | Нагрузка согласующего (пороги 30/50) | rbu, dp, gd, fd |

### 3.4. integration-service (REST)

| Метод | Путь | Описание | Роли |
|-------|------|----------|------|
| POST | /api/v1/events | Прием событий из 1С | (API key) |
| GET | /api/v1/mdm/npss | НПСС по товару на дату | (internal) |
| GET | /api/v1/mdm/npss/batch | Пакетный запрос НПСС | (internal) |
| GET | /api/v1/mdm/clients/{id} | Карточка контрагента | (internal) |
| GET | /api/v1/mdm/clients/{id}/history | Темпоральная история | dp, fd |
| GET | /api/v1/mdm/exchange-rates | Курсы валют ЦБ РФ | (internal) |
| GET | /api/v1/mdm/employees/{id} | Данные сотрудника | (internal) |
| GET | /api/v1/mdm/business-units/{id} | Бизнес-юнит | (internal) |
| GET | /api/v1/sanctions/{client_id} | Активные санкции | rbu, dp, gd, fd |
| POST | /api/v1/sanctions/{id}/cancel | Отмена санкции (решение ДП) | dp |

### 3.5. gRPC сервисы (межсервисное взаимодействие)

**Типы данных в protobuf (ОБЯЗАТЕЛЬНО):**
- Финансовые значения (Money): `int64` с суффиксом `_cents` (копейки)
- Проценты (Percentage, deviation): `int64` с суффиксом `_bp` (basis points, сотые доли %)
- Количество (Quantity): `string` (shopspring/decimal, lossless)
- **НЕ использовать** `double`/`float` для финансовых значений — потеря точности на границах (14.999% vs 15.00%)

| Сервис | RPC | Описание |
|--------|-----|----------|
| ProfitabilityService | GetCalculation | Получить расчет рентабельности заказа |
| ProfitabilityService | RecalculateForPlanChange | Перекрестный контроль при смене плана ЛС |
| ProfitabilityService | GetShipmentHistory | История заказов по ЛС |
| ProfitabilityService | CalculateWhatIf | Сценарий "что если" |
| WorkflowService | CreateApprovalProcess | Создать процесс согласования |
| WorkflowService | HandleELMACallback | Обработать callback от ELMA |
| WorkflowService | GetApprovalHistory | История согласований |
| AnalyticsService | CheckAnomaly | Проверка аномалии при расчете |
| AnalyticsService | GetAnomalySummary | Описание аномалии |
| IntegrationService | GetNPSS / GetNPSSBatch | Чтение НПСС из MDM |
| IntegrationService | GetClient | Чтение контрагента из MDM |
| IntegrationService | GetEmployee | Чтение сотрудника из MDM |
| IntegrationService | GetBusinessUnit | Чтение бизнес-юнита из MDM |
| IntegrationService | GetExchangeRate | Чтение курса валюты |
| IntegrationService | GetActiveSanctions | Активные санкции клиента |

---

## 4. Модель данных

### 4.1. Доменная модель (DDD)

#### 4.1.1. Bounded Contexts

| Контекст | Агрегаты | Описание |
|----------|---------|----------|
| Profitability | LocalEstimate, Shipment, ProfitabilityCalculation, PriceSheet | Расчет рентабельности, управление ЛС и заказами |
| Workflow | ApprovalProcess, EmergencyApproval | Маршрутизация согласований, SLA, ELMA |
| Analytics | Anomaly, Investigation | Детекция аномалий, расследования |
| Integration | Client, Sanction, PriceSheet (MDM) | MDM, внешние системы |

#### 4.1.2. Агрегаты

**LocalEstimate (Локальная Смета):**
- Центральная сущность. Плановая рентабельность, зафиксированные НПСС позиций, жизненный цикл.
- Инварианты: рентабельность фиксируется при создании; НПСС -- snapshot; максимум 2 продления; НПСС > 90 дней блокирует согласование; максимум 1000 позиций; максимум 50 заказов на согласовании.

**Shipment (Заказ клиента / Отгрузка):**
- Заказ по ЛС. Содержит расчет рентабельности, статус контроля, обоснование.
- 12 статусов: draft, awaiting_stock, pending_approval, rejected, approval_expired, partially_approved, approved, in_progress, fulfilled, partially_closed, overdue, cancelled.
- Инварианты: пересчет при каждом изменении; обоснование при отклонении >= 1 п.п. (мин. 50 символов); после передачи на склад согласование не аннулируется; срок согласования 5 рабочих дней; при >= 3 аннулированиях -- эскалация на ДП.

**ApprovalProcess (Процесс согласования):**
- 11 состояний: pending, auto_approved, routing, level_1, level_2, level_3, approved, rejected, expired, fallback_auto_approved, fallback_queued.
- Инварианты: матрица уровней по отклонению; SLA по уровню и приоритету; автоэскалация; автоотказ после SLA ГД (48ч); лимит итераций корректировки цены -- 5; агрегированные лимиты; резервный режим ELMA.

**ProfitabilityCalculation (Расчет рентабельности):**
- Снимок расчета: плановая, заказа, накопленная, остатка, отклонение.
- Все формулы из ФМ п. 3.3. Округление до 2 знаков ДО сравнения с границами.

**Anomaly (Аномалия):**
- 3 уровня детекции (L1 детерминистический, L2 интерпретация, L3 расследование).
- 4 статуса: open, investigating, resolved, false_positive.

#### 4.1.3. Value Objects

| Value Object | Описание | Хранение в БД |
|-------------|----------|---------------|
| Money | Денежная сумма в копейках (int64) | BIGINT |
| Quantity | Количество товара, 6 знаков (shopspring/decimal) | NUMERIC(18,6) |
| Percentage | Проценты в basis points (сотые доли %) | BIGINT |
| SLADeadline | Срок SLA с учетом рабочих часов (rickar/cal) | TIMESTAMPTZ |
| ProfitabilityThreshold | Пороги матрицы согласования | BIGINT (basis points) |
| ApprovalDecision | Решение согласующего | VARCHAR + TEXT |
| PriceCorrection | Итерация корректировки цены (1-5) | INT + BIGINT |
| DateRange | Диапазон дат | TIMESTAMPTZ x 2 |
| AggregateLimit | Дневной лимит автосогласования | BIGINT (копейки) |

### 4.2. PostgreSQL: ключевые таблицы

#### 4.2.1. Schema: profitability

| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| local_estimates | Локальные сметы | external_id(11), planned_profitability(bp), total_amount(коп), renewal_count(0-2), status |
| local_estimate_line_items | Позиции ЛС | product_id, quantity(18,6), price(коп), npss(коп), profitability(bp), min_allowed_price |
| shipments | Заказы клиентов | external_id(30), status(12 вариантов), priority(P1/P2), source(manual/edi), order_profitability(bp), deviation(bp) |
| shipment_line_items | Позиции заказов | quantity(18,6), price(коп), npss(коп), is_non_liquid |
| profitability_calculations | Снимки расчетов | planned/order/cumulative/remainder profitability(bp), shipped_revenue(коп), deviation(bp) |
| calculation_line_items | Детализация расчета | profitability(bp), is_blocked, block_reason |
| price_sheet_cache | Локальный кэш НПСС | product_id, npss(коп), method, valid_from/to |
| auto_approval_counters | Дневные лимиты | entity_type(manager/bu), total_amount(коп), approval_count |
| profitability_outbox | Outbox доменных событий | event_type, payload(JSONB), kafka_topic, published_at |

#### 4.2.2. Schema: workflow

| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| approval_processes | Процессы согласования | state(11 вариантов), deviation(bp), required_level, mode(standard/fallback), correction_iteration(0-5) |
| bu_approvals | Мульти-БЮ согласования | process_id, business_unit_id, approver_id, decision |
| routing_history | История маршрутизации | step_number, approver_id, sla_breached |
| sla_tracking | Трекинг SLA | sla_hours, deadline, escalation_threshold(80%), notification_threshold(50%), breached |
| fallback_queue | Очередь резервного режима | priority, deviation, position (FIFO) |
| emergency_approvals | Экстренные согласования | confirmation_status(pending/approved/rejected), check_24h, check_48h |
| workflow_outbox | Outbox доменных событий | event_type, payload(JSONB), kafka_topic, published_at |

#### 4.2.3. Schema: analytics

| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| anomalies | Аномалии | level(1/2/3), score, status(open/investigating/resolved/false_positive), confidence |
| investigations | Расследования (L3) | root_cause, recommendation, confidence_score, iterations(0-10), cost_usd |
| investigation_evidence | Цепочка улик | tool_used, input(JSONB), output(JSONB) |
| ai_audit_log | Журнал запросов к Claude API | request_type, model, input/output_tokens, cached_tokens, cost_usd, latency_ms |
| forecasts | Прогнозы ARIMA | entity_type, predicted_values(JSONB), confidence |
| analytics_outbox | Outbox доменных событий | event_type, payload(JSONB), kafka_topic |

#### 4.2.4. Schema: integration

| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| mdm_clients | Контрагенты (темпоральная) | external_id, is_strategic, strategic_criteria, allowed_deviation, valid_from/to |
| mdm_products | Товары (темпоральная) | external_id, name, is_non_liquid, origin, valid_from/to |
| mdm_price_sheets | НПСС (темпоральная) | product_id, npss(коп), method, trigger, valid_from/to |
| mdm_exchange_rates | Курсы валют | currency(USD/EUR/CNY), rate, rate_date |
| mdm_employees | Сотрудники (темпоральная) | external_id, name, position, ad_login, valid_from/to |
| mdm_business_units | Бизнес-юниты | external_id, name, head_id, deputy_id |
| kafka_dedup | Дедупликация Kafka | message_id, topic, processed_at |
| sanctions | Санкции за невыкуп (P2) | client_id, type, discount_reduction(bp), cumulative_reduction(bp), status |
| mdm_audit_log | Аудит-лог MDM (append-only) | entity_type, operation, old/new_values(JSONB), hash(SHA-256 chain) |
| integration_outbox | Outbox доменных событий | event_type, payload(JSONB), kafka_topic |

### 4.3. Precision and Overflow

| Тип | Хранение | Пояснение |
|-----|----------|-----------|
| Денежные суммы | BIGINT (копейки) | Максимум: 92 233 720 368 547 758.07 руб. Overflow protection в Go |
| Количество | NUMERIC(18,6) | shopspring/decimal в Go, 6 знаков дробной части (метры, кг, литры) |
| Проценты | BIGINT (basis points x100) | Точность 0.01%. Округление до 2 знаков ДО сравнения с границами |
| Временные метки | TIMESTAMPTZ | С учетом часовых поясов (МСК = UTC+3) |

---

## 5. Frontend (React)

### 5.1. Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | Next.js 15 (App Router) |
| Стили | Tailwind CSS |
| UI-компоненты | shadcn/ui (Atomic Design) |
| Графики | Recharts |
| Серверное состояние | TanStack Query v5 |
| Клиентское состояние | Zustand |
| Формы | React Hook Form + zod |
| Таблицы | TanStack Table |
| Иконки | Lucide React |

### 5.2. Страницы и маршруты

| Маршрут | Страница | Описание |
|---------|----------|----------|
| /login | Авторизация | AD-аутентификация |
| /dashboard | Дашборд | KPI-карточки, график рентабельности, лента алертов |
| /shipments | Отгрузки | Таблица заказов с фильтрами, drawer с деталями |
| /shipments/:id | Детали отгрузки | Расчет рентабельности, позиции, история |
| /approvals | Очередь согласования | Карточки задач, SLA-таймеры, массовые операции |
| /approvals/:id | Детали согласования | Полная информация о процессе согласования |
| /insights | Аналитика | Список аномалий по уровням, фильтры |
| /insights/:id | Детали аномалии | Расследование, цепочка улик, рекомендации |
| /insights/ask | Чат с аналитиком | Q&A интерфейс (стриминг) |
| /reports | Отчеты | Каталог из 8 отчетов P1, рассылки |
| /reports/:reportId | Конкретный отчет | Параметры, таблицы/графики, экспорт (Excel/PDF) |
| /settings | Настройки | Пороги, роли, уведомления, функциональные опции, аудит-лог |

### 5.3. Доступ по ролям

| Маршрут | manager | rbu | dp | gd | fd |
|---------|---------|-----|----|----|-----|
| /dashboard | чтение (свои) | чтение (БЮ) | чтение (все) | чтение (все) | чтение + admin |
| /shipments | чтение + создание | чтение | чтение | чтение | чтение |
| /approvals | чтение (свои) | согласование L1-2 | согласование L2-3 | согласование L3-4 | чтение |
| /insights | -- | чтение | чтение + решение | чтение + решение | чтение + решение + ask |
| /reports | свои отчеты | отчеты БЮ | все отчеты | все отчеты | все отчеты + admin |
| /settings | только уведомления | -- | -- | -- | полный доступ |

### 5.4. Ключевые компоненты

#### Дашборд (34 компонента)

- **KPIRow**: 4 карточки -- общая рентабельность, тренд, аномалии, SLA-соответствие
- **ProfitabilityChart**: AreaChart (Recharts) за 30/90/180 дней
- **AlertFeed**: Лента алертов (последние 10), ссылка на /insights
- **QuickFilters**: Период, бизнес-юнит, менеджер
- Данные: polling 60 сек для KPI, 2 мин для алертов, 5 мин для графиков

#### Таблица отгрузок

- **DataTable**: Серверная сортировка, cursor-based пагинация (не OFFSET)
- **ShipmentDrawer**: Slide-in панель справа -- расчет рентабельности (4 показателя с визуализацией), позиции заказа, timeline
- **ProfitabilityBreakdown**: Визуализация план vs факт (ProfitabilityBar), отклонение (DeviationIndicator), уровень (ApprovalLevelBadge)
- **FilterBar**: Клиент (autocomplete), менеджер, период, статус (multi-select), рентабельность (RangeSlider)

#### Очередь согласования

- **TaskCard**: SLA-таймер (обратный отсчет, цвета green->yellow->red->pulsing), карточка заявки, рекомендация, действия
- **BatchActions**: Массовое согласование выбранных задач
- **SLATimer**: Визуальный countdown -- >50% зеленый, 20-50% желтый, <20% красный, просрочено -- пульсация
- **RejectionModal**: Textarea (мин. 50 символов) для причины отклонения

#### Аналитика

- **AnomalyCard**: Severity + z-score + confidence, описание, рекомендация, действия
- **InvestigationTimeline**: Шаги расследования L3 (инструменты, входы/выходы)
- **ConfidenceIndicator**: Круговой gauge (270 градусов), 3 уровня (>=0.8 зеленый, 0.5-0.8 желтый, <0.5 красный)
- **AIChatInterface**: Стриминг ответов (ReadableStream/SSE), предложенные вопросы

#### Отчеты

- **ReportCatalog**: Сетка карточек (4 колонки desktop, 2 tablet, 1 mobile)
- **ReportViewer**: Параметры (период, БЮ) + контент (таблицы/графики) + экспорт (Excel через SheetJS, PDF через jsPDF)
- **ScheduledReports**: Настройка рассылок (ежедневная/еженедельная)

### 5.5. Performance Budget

| Метрика | Целевое значение |
|---------|-----------------|
| LCP (Largest Contentful Paint) | < 2.5 сек |
| FID (First Input Delay) | < 100 мс |
| CLS (Cumulative Layout Shift) | < 0.1 |
| Bundle size (gzipped) | < 250 KB (initial) |
| Time to Interactive | < 3 сек |

### 5.6. Отзывчивость (Responsive Design)

| Breakpoint | Ширина | Поведение |
|-----------|--------|-----------|
| Mobile | < 768px | Sidebar скрыт, таблицы горизонтально прокручиваются, 1 колонка |
| Tablet | 768-1024px | Sidebar свернут, 2 колонки для карточек |
| Desktop | > 1024px | Sidebar развернут, 3-4 колонки, drawer справа |

---

## 6. Аналитика

### 6.1. 3-уровневая архитектура

```
Уровень 1                  Уровень 2                  Уровень 3
(детерминистический)        (интерпретация)            (расследование)
gonum/stat                  Sonnet 4.6                 Opus 4.6

Z-score аномалий            Объяснение аномалий        Автономное расследование
ARIMA-прогноз               Суммаризация отчетов       Инструменты (5 шт.)
17 бизнес-правил            Q&A по данным              Цепочка улик

Стоимость: $0/запрос        ~$0.003/запрос             ~$0.05/запрос
Задержка: < 100 мс          < 15 сек                   < 60 сек
Лимит: без ограничений      200 запросов/час           50 запросов/час
```

### 6.2. Уровень 1: Детерминистический

**Z-score аномалий:**
```
Z = (x - mu) / sigma
Окно: 90 дней
Порог: |Z| >= 2.0
Минимум выборки: 30 значений
Сегментация: по менеджеру, БЮ, клиенту, общая
```

**ARIMA-прогноз:**
```
ARIMA(1,1,1) -- 30-дневный горизонт
Входные данные: средневзвешенные дневные отклонения за 90 дней
Минимум: 60 точек данных
Доверительный интервал: 95%
```

**Каталог бизнес-правил (17 правил):**

| Правило | Описание | Порог | Серьезность | Ссылка на ФМ |
|---------|----------|-------|-------------|--------------|
| margin_drop_7d | Падение маржи >5 п.п. за 7 дней | 5.0 п.п. | high | BR-004 |
| volume_anomaly | Объем заказов >3x среднего | 3.0x | high | -- |
| client_deviation | Клиент отклоняется от своего паттерна | 2 sigma | medium | -- |
| npss_age_warning | Возраст НПСС 31-60 дней | 30 дней | low | BR-052 |
| npss_age_confirm | Возраст НПСС 61-90 дней | 60 дней | medium | BR-053 |
| npss_age_block | Возраст НПСС >90 дней | 90 дней | critical | BR-054 |
| auto_approval_limit_mgr | Лимит менеджера близок к потолку | 80% от 20 000 | medium | BR-011 |
| auto_approval_limit_bu | Лимит БЮ близок к потолку | 80% от 100 000 | medium | BR-012 |
| approver_overload_30 | Очередь согласующего >30 задач | 30 | high | BR-070 |
| approver_overload_50 | Дневная нагрузка >50 задач | 50 | critical | BR-071 |
| emergency_limit_mgr | Лимит экстренных менеджера | 2/3 (пиковые: 4/5) | medium | BR-030 |
| emergency_limit_client | Лимит экстренных клиента | 4/5 (пиковые: 7/8) | medium | BR-031 |
| sla_breach_risk | Осталось <25% SLA | 25% | high | BR-014 |
| exchange_rate_trigger | Курс изменился >5% за 7 дней | 5% | high | LS-BR-075 |
| purchase_price_trigger | Закупочная цена отклонилась >15% от НПСС | 15% | high | LS-BR-075b |
| cherry_picking_pattern | Клиент выбирает низкомарж. позиции | маржа < 70% плана AND выкуп < 60% | critical | -- |
| correction_iterations | Приближение к лимиту корректировок | 4 из 5 макс. | medium | BR-019 |

### 6.3. Уровень 2: Интерпретация (Sonnet 4.6)

**Назначение:** Объяснение аномалий, обнаруженных на Уровне 1.

**Системный промпт:**
- Кэшируемый (~20 000 токенов), содержит полный контекст ФМ: бизнес-модель, формулы, пороги, роли, SLA, санкции, перекрестный контроль
- 90% скидка на входные токены за счет кэширования

**Пользовательский промпт:** данные аномалии (z-score, нарушенные правила, история заказов, данные клиента, изменения цен)

**Выходной формат:** структурированный JSON -- explanation (русский текст), confidence (0.0-1.0), recommendations (массив действий на русском), requires_level_3 (boolean), severity, financial_impact_rub, affected_entities

**Эскалация:** если confidence < 0.7 -> передача на Уровень 3

### 6.4. Уровень 3: Автономное расследование (Opus 4.6)

**Назначение:** Глубокое расследование сложных аномалий.

**Инструменты (5 шт.):**

| Инструмент | Описание | Вход | Выход |
|-----------|----------|------|-------|
| query_shipments | Заказы по ЛС/клиенту/менеджеру | local_estimate_id, client_id, date range | Список заказов |
| query_client_history | История клиента (объемы, частота, маржа) | client_id, months | Сводка по клиенту |
| query_price_changes | Изменения цен/НПСС | product_id, date_from | Список изменений |
| calculate_what_if | Сценарий "что если" | ls_id, items | Результат расчета |
| get_approval_history | История согласований | shipment_id | Записи согласований |

**Ограничения:** максимум 10 вызовов инструментов, таймаут 60 секунд

### 6.5. Контроль стоимости

| Параметр | Значение |
|----------|----------|
| Дневной лимит | $50 |
| Алерт при 60% ($30) | Уведомление ФД |
| При 80% ($40) | Деградация: только Уровень 1 + Уровень 2 |
| При 100% ($50) | Hard stop: только Уровень 1 |
| Стоимость Уровня 2 | ~$0.003/запрос (с кэшированием промпта) |
| Стоимость Уровня 3 | ~$0.05/запрос |
| Observability | Langfuse: трейсинг каждого запроса к Claude API |

### 6.6. Guardrails

- Входные данные: санитизация (удаление любых инструкций), максимальный размер контекста 50K токенов
- Системный и пользовательский промпты разделены (injection protection)
- Выходные данные: валидация JSON-схемы, ограничение длины полей
- Rate limiting: 200 req/hour для Уровня 2, 50 req/hour для Уровня 3
- Timeout: 15 сек для Уровня 2, 60 сек для Уровня 3
- Fallback при ошибке Claude API: возврат результата Уровня 1 (детерминистического)

---

## 7. Интеграции

### 7.1. Матрица интеграций (17 шт.)

| # | Интеграция | Направление | Протокол | Частота | Ссылка на ФМ |
|---|------------|-------------|----------|---------|--------------|
| 1 | Заказ создан | 1С -> Go | HTTP->Kafka | event-driven | п. 3.3 |
| 2 | Заказ изменен | 1С -> Go | HTTP->Kafka | event-driven | п. 3.3 |
| 3 | Отгрузка проведена | 1С -> Go | HTTP->Kafka | event-driven | п. 3.8 |
| 4 | Возврат товаров | 1С -> Go | HTTP->Kafka | event-driven | п. 3.8 |
| 5 | НПСС обновлена | 1С -> Go | HTTP->Kafka | event-driven | п. 3.2, 3.19 |
| 6 | Закупочная цена изменена | 1С -> Go | HTTP->Kafka | event-driven | LS-BR-075 |
| 7 | Контрагент обновлен | 1С -> Go | HTTP->Kafka | event-driven | п. 3.15 |
| 8 | ЛС создана | 1С -> Go | HTTP->Kafka | event-driven | п. 3.1 |
| 9 | План ЛС изменен | 1С -> Go | HTTP->Kafka | event-driven | п. 3.14 |
| 10 | Результат согласования | Go -> 1С | Kafka->REST | event-driven | п. 3.5 |
| 11 | Санкция применена | Go -> 1С | Kafka->REST | event-driven | п. 3.17 |
| 12 | Блокировка отгрузки | Go -> 1С | Kafka->REST | event-driven | п. 3.13 |
| 13 | ELMA согласование | Go <-> ELMA | REST API | event-driven | LS-INT-003 |
| 14 | WMS разрешение отгрузки | Go -> WMS | REST API | event-driven | п. 3.8 |
| 15 | WMS факт отгрузки | WMS -> Go | Webhook | event-driven | п. 3.8 |
| 16 | Курсы ЦБ РФ | ЦБ -> Go | REST (XML) | daily 08:00 | LS-BR-075 |
| 17 | AD аутентификация | Go <-> AD | LDAP/Kerberos | on-demand | п. 4.1 |

### 7.2. 1С -> Go (входящие события)

**Архитектура:**
1. Расширение 1С (.cfe) перехватывает проведение/запись документов через подписки на события
2. HTTP-клиент в расширении отправляет POST на integration-service
3. integration-service валидирует, дедуплицирует (message_id), маршрутизирует в Kafka

**HTTP Endpoint:** `POST /api/v1/events`
- Аутентификация: API key (X-Api-Key), ротация ежемесячно (Infisical)
- Дедупликация: UUID message_id, таблица kafka_dedup
- Rate limit: 200 req/sec

**9 входящих Kafka-топиков:**

| Топик | Partition Key | Источник |
|-------|-------------|----------|
| `1c.order.created.v1` | order_id | ЗаказПокупателя (запись) |
| `1c.order.updated.v1` | order_id | ЗаказПокупателя (изменение) |
| `1c.shipment.posted.v1` | order_id | РеализацияТоваровИУслуг (проведение) |
| `1c.shipment.returned.v1` | order_id | ВозвратТоваровОтПокупателя (проведение) |
| `1c.price.npss-updated.v1` | product_id | Обновление НПСС |
| `1c.price.purchase-changed.v1` | product_id | Изменение закупочной цены |
| `1c.client.updated.v1` | client_id | Обновление контрагента |
| `1c.ls.created.v1` | ls_id | Создание ЛС |
| `1c.ls.plan-changed.v1` | ls_id | Изменение плана ЛС |

**Retry queue в 1С:**
- Регистр сведений `ОчередьОтправкиСобытий` в расширении
- Экспоненциальный backoff: 30 сек -> 1 мин -> 2 мин -> ... -> 2 час (макс. 100 попыток, ~6 суток)
- Фоновое задание каждые 30 секунд, batch 50 записей
- Алерт администратору после 10 неудачных попыток

### 7.3. Go -> 1С (исходящие команды)

**3 исходящих Kafka-топика:**

| Топик | Назначение | Callback URL |
|-------|-----------|-------------|
| `cmd.approval.result.v1` | Результат согласования | PUT /api/v1/callback/approval/{order_id}/result |
| `cmd.sanction.applied.v1` | Применение санкции | PUT /api/v1/callback/sanction/{client_id}/apply |
| `cmd.shipment.block.v1` | Блокировка отгрузки | PUT /api/v1/callback/shipment/{order_id}/block |

**Callback HTTP-сервис в 1С:**
- Базовый URL: `https://1c-ekf-app-01:443/EKF/hs/profit-callback/api/v1/`
- Аутентификация: отдельный API key (X-Api-Key), Infisical: `CALLBACK_1C_API_KEY`
- Retry: 3 попытки с экспоненциальным backoff (1с, 5с, 15с), DLQ после 3-й ошибки

### 7.4. ELMA BPM

**Назначение:** Маршрутизация задач согласования к ответственным лицам.

**Circuit Breaker:**
- Порог: 5 последовательных ошибок
- Open state: 30 секунд
- Half-open: 1 тестовый запрос
- Восстановление: автоматическое при успехе

**API ELMA:**
- POST /api/bpm/tasks -- создать задачу согласования
- GET /api/bpm/tasks/{id} -- статус задачи
- POST /api/bpm/tasks/{id}/complete -- завершить задачу

**Резервный режим (при недоступности ELMA):**
- Отклонение <= 5 п.п.: автосогласование с пометкой `mode=fallback`
- Отклонение > 5 п.п.: очередь FIFO (P1 -> P2)
- При восстановлении: drain queue в ELMA, уведомление согласующих о fallback-решениях
- Health check: каждые 5 минут

### 7.5. WMS (LeadWMS)

**Исходящие:** REST POST для разрешения отгрузки после согласования
**Входящие:** Webhook от WMS при фактической отгрузке (подтверждение)

### 7.6. ЦБ РФ

**Назначение:** Мониторинг курсов валют для автотриггера пересчета НПСС.

**Расписание:** Ежедневно в 08:00 МСК
**Протокол:** REST GET -> XML парсинг (cbr.ru/scripts/XML_daily.asp)
**Валюты:** USD, EUR, CNY
**Триггер:** если курс изменился > 5% за 7 дней -> генерация события `evt.integration.price.exchange-trigger.v1`
**Fallback:** при недоступности cbr.ru -- использовать последний сохраненный курс, retry через 1 час

### 7.7. Active Directory

**Назначение:** Аутентификация и авторизация пользователей.

**Протокол:** LDAP bind (фаза 1), Kerberos (фаза 2)
**Группы AD -> Роли приложения:**

| Группа AD | Роль |
|-----------|------|
| APP_PROFIT_MANAGER | manager |
| APP_PROFIT_RBU | rbu |
| APP_PROFIT_DP | dp |
| APP_PROFIT_GD | gd |
| APP_PROFIT_FD | fd |
| APP_PROFIT_ANALYST | analyst |

**JWT:** RS256, TTL 1 час, refresh token 24 часа

### 7.8. Уведомления

| Канал | Назначение | Шаблоны |
|-------|-----------|---------|
| Telegram Bot | Согласующие: новые заявки, SLA-предупреждения, эскалации | 8 шаблонов |
| Email (SMTP) | Еженедельные отчеты, эскалации, алерты ФД | 5 шаблонов |
| 1С callback | Обновление статусов в карточках документов | 3 шаблона |

---

## 8. Инфраструктура

### 8.1. Kafka

**Режим:** KRaft (без ZooKeeper)
**Клиент:** franz-go

**44 топика:**

| Категория | Формат имени | Кол-во | Пример |
|-----------|-------------|--------|--------|
| Входящие из 1С | `1c.<domain>.<event>.v1` | 9 | `1c.order.created.v1` |
| Исходящие в 1С | `cmd.<domain>.<command>.v1` | 3 | `cmd.approval.result.v1` |
| Доменные события | `evt.<service>.<aggregate>.<event>.v1` | 20 | `evt.profitability.shipment.calculated.v1` |
| DLQ | `<topic>.dlq` | 12 | `1c.order.created.v1.dlq` |

**Конфигурация:**
- Partitions: 6 per topic (по числу Go-сервисов)
- Replication factor: 3 (dev: 1)
- Retention: 7 дней
- Compression: lz4
- Consumer groups: по сервису (e.g. `profitability-consumer`)
- Exactly-once: через Outbox pattern (не Kafka transactions)

### 8.2. Redis

| Назначение | Key pattern | TTL |
|-----------|-----------|-----|
| Кэш НПСС | `npss:{product_id}` | 1 час |
| Кэш клиента | `client:{client_id}` | 15 мин |
| Счетчик rate limit | `ratelimit:{user_id}:{minute}` | 2 мин |
| Сессия JWT | `session:{token_hash}` | 1 час |
| Замок блокировки ЛС | `lock:ls:{ls_id}` | 5 мин |

**Eviction policy:** allkeys-lfu
**Persistence:** RDB snapshots every 5 min (не AOF -- кэш, не storage)

### 8.3. PostgreSQL

**Версия:** 16+
**4 базы данных (по сервису):** profitability_db, workflow_db, analytics_db, integration_db

**Миграции:** golang-migrate, нумерация: `001_initial.up.sql`, `002_indexes.up.sql`, etc.

**Размерность (оценка на 1 год):**

| Таблица | Записей/год | Размер (примерно) |
|---------|-------------|-------------------|
| shipments | ~100 000 | 100 MB |
| shipment_line_items | ~1 000 000 | 500 MB |
| profitability_calculations | ~100 000 | 150 MB |
| approval_processes | ~50 000 | 50 MB |
| mdm_price_sheets | ~500 000 | 100 MB |
| ai_audit_log | ~50 000 | 30 MB |
| Итого | | ~1 GB/year |

### 8.4. Docker Compose

**Сервисы в docker-compose.yml:**

| Сервис | Image | Порты |
|--------|-------|-------|
| api-gateway | profitability/api-gateway | 8080, 8443 |
| profitability-service | profitability/profitability | 9001, 9101 |
| workflow-service | profitability/workflow | 9002, 9102 |
| analytics-service | profitability/analytics | 9003, 9103 |
| integration-service | profitability/integration | 9004, 9104 |
| notification-service | profitability/notification | 9005, 9105 |
| web | profitability/web (Next.js) | 3000 |
| postgres | postgres:16 | 5432 |
| kafka | bitnami/kafka:3.7 (KRaft) | 9092 |
| redis | redis:7-alpine | 6379 |

**Healthcheck:** каждый Go-сервис предоставляет GET /healthz (readiness) и GET /livez (liveness)

### 8.5. Среды

| Среда | Описание | Особенности |
|-------|----------|-------------|
| Dev | Homelab, моки внешних систем | Mock ELMA, Mock 1С, Mock WMS, Mock ЦБ |
| Staging | Homelab + 100% данных, туннель к корп. сети | Реальная ELMA, реальный AD, тестовая 1С |
| Prod | Корпоративная сеть | Полная интеграция со всеми системами |

### 8.6. Конфигурация (переменные окружения)

| Переменная | Описание | Значение (prod) |
|-----------|----------|-----------------|
| DATABASE_URL | PostgreSQL connection string | `postgres://...` |
| KAFKA_BROKERS | Kafka broker addresses | `kafka-01:9092,kafka-02:9092,kafka-03:9092` |
| REDIS_URL | Redis connection string | `redis://redis:6379/0` |
| AD_HOST | Active Directory LDAP host | `ldap://172.20.0.xxx` |
| AD_BASE_DN | LDAP base distinguished name | `DC=ekf,DC=su` |
| ELMA_API_URL | ELMA BPM API endpoint | `http://172.20.0.226/api/bpm` |
| WMS_API_URL | LeadWMS API endpoint | `http://172.20.0.210/api` |
| AI_MODEL_ANALYST | Модель для Level 2 | `claude-sonnet-4-6-20250514` |
| AI_MODEL_INVESTIGATOR | Модель для Level 3 | `claude-opus-4-6-20250514` |
| AI_DAILY_COST_CEILING | Дневной лимит на аналитику | `50.00` |
| INTEGRATION_1C_API_KEY | API key для 1С -> Go | Infisical |
| CALLBACK_1C_API_KEY | API key для Go -> 1С | Infisical |
| JWT_PRIVATE_KEY | RSA private key для JWT | Infisical |
| LANGFUSE_PUBLIC_KEY | Langfuse observability | Infisical |

### 8.7. Observability

| Компонент | Инструмент | Описание |
|-----------|-----------|----------|
| Логирование | slog (structured JSON) | Все сервисы, поля: trace_id, span_id, service, level |
| Метрики | Prometheus | HTTP-эндпоинты /metrics на каждом сервисе |
| Трейсинг | OpenTelemetry -> Langfuse | Distributed tracing через все сервисы |
| Алерты | Grafana | Дашборды по сервисам, алерты SLA/error rate/latency |
| AI Observability | Langfuse | Каждый запрос к Claude API: токены, стоимость, задержка |

### 8.8. Outbox Pattern

Каждый сервис с доменными событиями использует Outbox pattern:
1. Доменное событие записывается в таблицу `{service}_outbox` в той же транзакции, что и бизнес-данные
2. Background poller (каждые 100 мс) читает неопубликованные записи, batch по 100
3. Публикует в Kafka, при успехе устанавливает `published_at`
4. Retry: экспоненциальный backoff (1с x 2^attempt), max 10 попыток, после -- DLQ
5. Cleanup: опубликованные старше 7 дней удаляются (batch по 1000)

### 8.9. Graceful Shutdown

Каждый сервис при получении SIGTERM:
1. Прекращает принимать новые запросы (HTTP listener close)
2. Завершает in-flight запросы (30 сек таймаут)
3. Commit Kafka offsets
4. Flush outbox poller
5. Close DB connections
6. Exit

---

## 9. Оценка трудоемкости

### 9.1. По фазам

| Фаза | Описание | Агент | Недели | Задачи |
|------|----------|-------|--------|--------|
| 0 | Протоколы и инфраструктура | Архитектор | 1 | 9 |
| 1 | Архитектура и ТЗ | Архитектор | 2-4 | 31 |
| 1.5 | Расширение 1С | Разработчик 1С + Ревьюер | 3 | 4 |
| 2 | Ревью архитектуры | Ведущий разработчик | 5 | 9 |
| 3 | Генерация кода (Go+React) | Разработчик Go+React | 6-8 | 50 |
| 4 | Тестирование | Тестировщик | 9-10 | 32 |
| 5 | Документация | Технический писатель | 10 | 8 |
| 6 | Деплой и релиз | Инженер релизов + Публикатор | 11-12 | 19 |
| **Итого** | | | **~12 недель** | **~162 задачи + подзадачи** |

### 9.2. Фаза 3 -- Генерация кода (детализация)

| Подфаза | Описание | Задачи |
|---------|----------|--------|
| 3A | Scaffold (репозиторий, Go tooling, React, Docker) | 4 |
| 3B | Domain Layer (entities, VOs, events, errors, ports, services) | 6 |
| 3C | Use Cases (calculate, approve, detect, sanction, price, report) | 6 |
| 3D | Adapters (HTTP, PG, Kafka, Redis, Claude, ELMA, WMS, ЦБ, notifications) | 10 |
| 3E | AI Service (deterministic, Claude, agentic, audit) | 4 |
| 3F | React Frontend (components, dashboard, shipment, approval, AI, reports, settings, auth) | 8 |
| 3G | Infrastructure (migrations, Kafka topics, seed data, Wire DI) | 4 |
| 3H | Cross-Cutting (logging, tracing, shutdown, mocks, Grafana, errors, outbox, dev experience) | 8 |

### 9.3. Фаза 4 -- Тестирование (детализация)

| Подфаза | Описание | Задачи |
|---------|----------|--------|
| 4A | Go Unit Tests (domain, usecase, HTTP, AI) | 4 |
| 4B | React Tests (components, pages, forms) | 3 |
| 4C | Integration Tests (PG, Kafka, DLQ, Redis, LDAP) | 5 |
| 4D | Contract Tests (API, Kafka schema) | 3 |
| 4E | E2E Tests (Playwright, 12 flows) | 5 |
| 4F | Load Tests (k6, 70 пользователей, p95 <200ms) | 3 |
| 4G | Visual Regression Tests | 2 |
| 4H | AI Eval Suite (accuracy, latency, cost) | 3 |
| 4I | Security Testing (OWASP, injection, auth) | 3 |
| 4J | Data Consistency Tests | 2 |
| 4K | Mutation Testing (domain/) | 1 |

### 9.4. Целевое покрытие тестами

| Область | Покрытие |
|---------|----------|
| Domain layer | 95% |
| Use cases | 90% |
| Adapters | 80% |
| Frontend | 80% |
| **Общее** | **88%** |
| Mutation testing | domain/ only |

### 9.5. Milestones

| Milestone | Неделя | Deliverable | Критерий успеха |
|-----------|--------|------------|-----------------|
| M0 | 1 | Инфраструктура | CI/CD pipeline настроен, протоколы обновлены, инфраструктура развернута |
| M1 | 4 | Архитектура | Доменная модель, спецификации 6 сервисов, OpenAPI, DB-схемы, дизайн аналитики |
| M1.5 | 3 | Расширение 1С | BSL-код, SE review пройден, расширение компилируется |
| M2 | 5 | SE review | 0 CRITICAL, 0 HIGH findings, все корректировки применены |
| M3 | 8 | Код готов | Все сервисы собираются, lint пройден, базовые тесты, `docker compose up` работает |
| M4 | 10 | Тесты готовы | 88% coverage, E2E пройдены, нагрузочные тесты, security scan чистый |
| M5 | 10 | Документация | Руководство пользователя, руководство администратора, FAQ, API docs, runbook |
| M6 | 12 | Production release | v1.0.0 задеплоен, мониторинг 15 мин, error rate <1% |

---

## 10. Критерии приемки

### 10.1. Функциональные

| # | Критерий | Метрика | Ссылка на ФМ |
|---|---------|---------|--------------|
| FA-01 | Расчет рентабельности совпадает с ФМ на 100% (формулы п. 3.3) | Совпадение на тестовой выборке 100 ЛС | п. 3.3 |
| FA-02 | Матрица согласования корректно определяет уровень | 100% корректных маршрутизаций на 50 тестовых случаях | п. 3.5 |
| FA-03 | SLA-таймеры корректно считают бизнес-часы (09:00-18:00 МСК) | Точность до 1 минуты на 20 тестовых случаях | п. 3.6 |
| FA-04 | Автоэскалация срабатывает при нарушении SLA | 100% срабатываний на тестовых данных | п. 3.6 |
| FA-05 | Агрегированные лимиты блокируют автосогласование при превышении | Корректная блокировка при 20K/100K | п. 3.5 |
| FA-06 | Перекрестный контроль отзывает согласование при смене плана ЛС | Корректный отзыв на 10 тестовых случаях | п. 3.14 |
| FA-07 | Экстренные согласования: лимиты, постфактум-контроль (24ч/48ч) | Корректная работа лимитов и эскалации | п. 3.7 |
| FA-08 | Резервный режим ELMA: автосогласование <= 5 п.п., очередь > 5 п.п. | Корректная работа при имитации сбоя ELMA | п. 3.9 |
| FA-09 | Z-score аномалий: порог 2 sigma, окно 90 дней | Точность детекции > 90% на синтетических данных | п. 3.10 |
| FA-10 | ARIMA-прогноз: горизонт 30 дней | R-squared > 0.7 на 60+ точек данных | п. 3.10 |
| FA-11 | Все 8 отчетов P1 отображают корректные данные | Сверка с ручным расчетом на 10 ЛС | п. 3.11-3.12 |
| FA-12 | Интеграция с 1С: 9 входящих событий обрабатываются | 100% событий из тестовой выборки обработаны | п. 3.3, 3.8 |
| FA-13 | Callback в 1С: результат согласования записывается | 100% callback-ов на тестовых данных | п. 3.5 |

### 10.2. Нефункциональные

| # | Критерий | Метрика |
|---|---------|---------|
| NF-01 | Время ответа API (p95) | < 200 мс |
| NF-02 | Расчет рентабельности (500 позиций) | < 2 секунд |
| NF-03 | Одновременные пользователи | 70 без деградации |
| NF-04 | Доступность (бизнес-часы) | 99.5% |
| NF-05 | Тестовое покрытие | 88% общее, 95% domain |
| NF-06 | Безопасность | OWASP Top 10 clean, no SQL injection, no XSS |
| NF-07 | LCP (frontend) | < 2.5 секунд |
| NF-08 | Стоимость аналитики | < $50/день при нормальной нагрузке |
| NF-09 | Время восстановления после сбоя | < 5 минут (graceful restart) |
| NF-10 | Потеря данных при сбое Kafka | 0 (Outbox pattern) |

---

## 11. Риски и ограничения

### 11.1. Риски

| # | Риск | Влияние | Вероятность | Митигация |
|---|------|---------|-------------|-----------|
| R1 | Несовместимость API ELMA с Go-клиентом | HIGH | MEDIUM | Мок-режим в dev, тестирование с реальной ELMA в staging |
| R2 | Ограничения HTTP-сервисов 1С:УТ 10.2 | HIGH | MEDIUM | Минимальное расширение, тестирование на реальном экземпляре |
| R3 | Стоимость Claude API превышает бюджет | MEDIUM | LOW | Кэширование промптов, потолок $50/день, деградация до Level 1 |
| R4 | Пропускная способность Kafka недостаточна | LOW | LOW | KRaft, franz-go, раннее нагрузочное тестирование |
| R5 | Сложность AD-аутентификации (Kerberos) | MEDIUM | MEDIUM | Начать с LDAP bind, добавить Kerberos позже |
| R6 | Доменная модель не соответствует ФМ | HIGH | LOW | Трассировка каждого правила к LS-BR-*, перекрестная проверка |
| R7 | Cold start MDM -- нет данных | HIGH | MEDIUM | Bulk seed из CSV-экспорта 1С, валидация перед запуском |
| R8 | Outbox poller пропустил события | MEDIUM | LOW | Та же транзакция, идемпотентный poller, мониторинг |
| R9 | Неполная миграция данных | HIGH | MEDIUM | Row count + hash verification, dry-run на staging |
| R10 | Нестабильность корпоративного туннеля | MEDIUM | MEDIUM | Health checks, auto-reconnect, fallback to mock |
| R11 | Ломающие изменения gRPC-контрактов | MEDIUM | LOW | buf lint + breaking в CI, contract tests |
| R12 | Prompt injection в аналитике | HIGH | LOW | Санитизация входных данных, разделение system/user промптов |

### 11.2. Ограничения

| Ограничение | Описание |
|-------------|----------|
| 1С:УТ 10.2 -- source of truth | Все оперативные данные остаются в 1С. Go-сервис -- вторичная система |
| Обычные формы 1С | Расширение работает только с обычными формами (не управляемыми) |
| Вендорная поддержка 1С:УТ 10.2 | Прекращена с 01.04.2024 |
| Корпоративная сеть | Prod-среда доступна только из корпоративной сети |
| AD-группы | Необходимо согласование с ИТ для создания групп APP_PROFIT_* |
| ELMA BPM | Должна поддерживать REST API для создания/управления задачами |
| Kafka | Требуется кластер Kafka в корпоративной сети (или homelab) |
| Claude API | Требуется стабильный интернет-канал для вызовов к Claude API |

---

## 12. Открытые вопросы

| # | Вопрос | Статус | Ответственный |
|---|--------|--------|---------------|
| Q1 | Наличие и версия ELMA REST API в корпоративной среде | Открыт | ДИТ |
| Q2 | Создание AD-групп APP_PROFIT_* | Открыт | ИТ-служба |
| Q3 | Доступность Kafka-кластера в корпоративной сети | Открыт | ДИТ |
| Q4 | Параметры VPN-туннеля для staging-среды | Открыт | Инфраструктура |
| Q5 | Формат CSV-экспорта из 1С для seed MDM | Открыт | Аналитик 1С |
| Q6 | Бюджет на Claude API (согласование $50/день) | Открыт | ФД |
| Q7 | Сертификаты TLS для HTTPS (api-gateway) | Открыт | ИБ |

---

*Документ подготовлен на основании ФМ FM-LS-PROFIT v1.0.7, архитектурных документов phase1a-1e, дорожной карты проекта. Ссылки на ФМ: Confluence PAGE_ID 83951683.*

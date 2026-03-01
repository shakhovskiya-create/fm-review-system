# Phase 1E: Integration Architecture

**Проект:** FM-LS-PROFIT (Контроль рентабельности отгрузок по ЛС)
**Версия ФМ:** 1.0.7
**Дата:** 02.03.2026
**Автор:** Шаховский А.С.
**Зависимости:**
- Domain Model: `phase1a_domain_model.md` (секция 10: Integration Contracts)
- Go Architecture: `phase1b_go_architecture.md` (секции 5, 9: integration-service, Kafka Topic Catalog)
- 1С:УТ 10.2, платформа 8.3, обычные формы, расширение .cfe

---

## Содержание

1. [Integration Landscape](#1-integration-landscape)
2. [1С to Kafka Pipeline (Inbound)](#2-1с-to-kafka-pipeline-inbound)
3. [Kafka to 1С Callback API (Outbound)](#3-kafka-to-1с-callback-api-outbound)
4. [ELMA BPM Integration](#4-elma-bpm-integration)
5. [ЦБ РФ Exchange Rates](#5-цб-рф-exchange-rates)
6. [WMS Integration](#6-wms-integration)
7. [AD LDAP Integration](#7-ad-ldap-integration)
8. [Notification Channels](#8-notification-channels)
9. [AI Model Integration](#9-ai-model-integration)
10. [Sequence Diagrams](#10-sequence-diagrams)
11. [Error Handling and Retry Strategy](#11-error-handling-and-retry-strategy)
12. [Monitoring and Alerting](#12-monitoring-and-alerting)

---

## 1. Integration Landscape

### 1.1. All 17 Integrations

```
+------------------+                                    +-------------------+
|  1С:УТ 10.2      |  9 inbound events (HTTP->Kafka)    | integration-      |
|  (расширение     |  ================================> | service           |
|   .cfe)          |                                    |                   |
|                  |  3 outbound commands (REST)        |  Mini MDM         |
|  Подписки на     |  <================================ |  Outbox           |
|  проведение      |                                    |  Kafka consumers  |
+------------------+                                    +---+---+-----------+
                                                            |   |
+------------------+                                        |   |
|  ELMA BPM        |  REST API (bidirectional)              |   |
|  172.20.0.226    |  <====================================>+   |
+------------------+                                        |   |
                                                            |   |
+------------------+                                        |   |
|  WMS (LeadWMS)   |  REST outbound / webhook inbound       |   |
|  172.20.0.210    |  <====================================>+   |
+------------------+                                        |   |
                                                            |   |
+------------------+                                        |   |
|  ЦБ РФ           |  XML (ежедневно 08:00 MSK)            |   |
|  cbr.ru          |  ================================>     |   |
+------------------+                                        |   |
                                                            |   |
+------------------+                                        |   |
|  AD (LDAP)       |  LDAP/Kerberos (аутентификация)        |   |
|  172.20.0.xxx    |  <====================================>+   |
+------------------+                                            |
                                                                |
+------------------+         +------------------+               |
|  Claude API      |  REST   | Telegram Bot API |   REST        |
|  (Sonnet+Opus)   |  <=====>| Email (SMTP)     |  <==========> |
+------------------+         +------------------+               |
```

### 1.2. Integration Matrix

| # | Интеграция | Направление | Протокол | Источник | Приемник | Частота | FM Ref |
|---|------------|-------------|----------|----------|----------|---------|--------|
| 1 | Заказ создан | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.3 |
| 2 | Заказ изменен | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.3 |
| 3 | Отгрузка проведена | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.8 |
| 4 | Возврат товаров | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.8 |
| 5 | НПСС обновлена | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.2, 3.19 |
| 6 | Закупочная цена изменена | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | LS-BR-075 |
| 7 | Контрагент обновлен | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.15 |
| 8 | ЛС создана | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.1 |
| 9 | План ЛС изменен | 1С -> Go | HTTP->Kafka | 1С:УТ | integration-service | event-driven | п. 3.14 |
| 10 | Результат согласования | Go -> 1С | Kafka->REST | workflow-service | 1С:УТ | event-driven | п. 3.5 |
| 11 | Санкция применена | Go -> 1С | Kafka->REST | integration-service | 1С:УТ | event-driven | п. 3.17 |
| 12 | Блокировка отгрузки | Go -> 1С | Kafka->REST | workflow-service | 1С:УТ | event-driven | п. 3.13 |
| 13 | ELMA согласование | Go <-> ELMA | REST API | workflow-service | ELMA BPM | event-driven | LS-INT-003 |
| 14 | WMS разрешение отгрузки | Go -> WMS | REST API | workflow-service | LeadWMS | event-driven | п. 3.8 |
| 15 | WMS факт отгрузки | WMS -> Go | Webhook | LeadWMS | integration-service | event-driven | п. 3.8 |
| 16 | Курсы ЦБ РФ | ЦБ -> Go | REST (XML) | cbr.ru | integration-service | daily 08:00 | LS-BR-075 |
| 17 | AD аутентификация | Go <-> AD | LDAP/Kerberos | api-gateway | Active Directory | on-demand | п. 4.1 |

### 1.3. Non-Kafka Integrations (REST/LDAP)

Интеграции 13-17 работают по протоколам REST/LDAP/Webhook напрямую, без Kafka. Kafka используется только для обмена данными между 1С:УТ и Go-сервисами (интеграции 1-12).

---

## 2. 1С to Kafka Pipeline (Inbound)

### 2.1. Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
| 1С:УТ 10.2        |     | integration-      |     | Kafka             |
| (расширение .cfe) |     | service           |     |                   |
|                   |     |                   |     |                   |
| Подписка на       | HTTP| HTTP handler      | TCP | Producer          |
| проведение -----> | POST| /api/v1/events    | --> | (franz-go)        |
| документа         |     |                   |     |                   |
|                   |     | Validation        |     | 9 inbound topics  |
| Retry queue       |     | Routing           |     | (1c.*.v1)         |
| (Рег. сведений)   |     | Dedup             |     |                   |
+-------------------+     +-------------------+     +-------------------+
```

Поток: 1С генерирует событие при проведении/записи документа -> HTTP-сервис в расширении отправляет POST -> integration-service валидирует, маршрутизирует, публикует в Kafka.

### 2.2. HTTP-сервис в расширении 1С

**Подход:** Расширение (.cfe) для 1С:УТ 10.2 на платформе 8.3. Обычные формы. Расширение не изменяет основную конфигурацию. Все доработки -- через подписки на события и дополнительные объекты расширения.

**Подписка на события (BSL):**

Расширение использует подписку на событие `ПриЗаписиДокумента` (в модуле расширения) для перехвата проведения документов. На платформе 8.3 в расширениях доступны подписки на события, но в обычных формах (УТ 10.2) нет управляемого приложения. Подписка реализуется через расширяемый общий модуль.

```bsl
// Расширение: ОбщийМодуль.ИнтеграцияРентабельностьСервер

Процедура ОбработкаПроведенияДокумента(Источник, Отказ, РежимПроведения) Экспорт
    // Определяем тип документа
    Если ТипЗнч(Источник) = Тип("ДокументОбъект.ЗаказПокупателя") Тогда
        ОтправитьСобытие("order.created", СформироватьДанныеЗаказа(Источник));
    ИначеЕсли ТипЗнч(Источник) = Тип("ДокументОбъект.РеализацияТоваровИУслуг") Тогда
        ОтправитьСобытие("shipment.posted", СформироватьДанныеОтгрузки(Источник));
    ИначеЕсли ТипЗнч(Источник) = Тип("ДокументОбъект.ВозвратТоваровОтПокупателя") Тогда
        ОтправитьСобытие("shipment.returned", СформироватьДанныеВозврата(Источник));
    КонецЕсли;
КонецПроцедуры

Процедура ОбработкаЗаписиДокумента(Источник, Отказ) Экспорт
    Если ТипЗнч(Источник) = Тип("ДокументОбъект.ЗаказПокупателя") Тогда
        Если Источник.ЭтоНовый() Тогда
            ОтправитьСобытие("order.created", СформироватьДанныеЗаказа(Источник));
        Иначе
            ОтправитьСобытие("order.updated", СформироватьДанныеЗаказа(Источник));
        КонецЕсли;
    КонецЕсли;
КонецПроцедуры
```

**Отправка событий (HTTP-клиент):**

```bsl
// Расширение: ОбщийМодуль.ИнтеграцияРентабельностьСервер

Процедура ОтправитьСобытие(ТипСобытия, ДанныеСобытия)
    // Формируем JSON payload
    ИдентификаторСообщения = Новый УникальныйИдентификатор;

    СтруктураСобытия = Новый Структура;
    СтруктураСобытия.Вставить("message_id", Строка(ИдентификаторСообщения));
    СтруктураСобытия.Вставить("event_type", ТипСобытия);
    СтруктураСобытия.Вставить("timestamp", XMLСтрока(ТекущаяДата()));
    СтруктураСобытия.Вставить("source", "1c_ut");
    СтруктураСобытия.Вставить("schema_version", "v1");
    СтруктураСобытия.Вставить("payload", ДанныеСобытия);

    ТелоЗапроса = ПолучитьJSON(СтруктураСобытия);

    // Отправка через HTTP
    Попытка
        Соединение = Новый HTTPСоединение(
            ПолучитьНастройку("ИнтеграцияСервисURL"),  // integration-service host
            ПолучитьНастройку("ИнтеграцияСервисПорт"),  // port
            , , , 10  // таймаут 10 секунд
        );

        Заголовки = Новый Соответствие;
        Заголовки.Вставить("Content-Type", "application/json");
        Заголовки.Вставить("X-Api-Key", ПолучитьНастройку("ИнтеграцияAPIКлюч"));
        Заголовки.Вставить("X-Message-Id", Строка(ИдентификаторСообщения));
        Заголовки.Вставить("X-Event-Type", ТипСобытия);

        Запрос = Новый HTTPЗапрос("/api/v1/events", Заголовки);
        Запрос.УстановитьТелоИзСтроки(ТелоЗапроса);

        Ответ = Соединение.ВызватьHTTPМетод("POST", Запрос);

        Если Ответ.КодСостояния <> 202 Тогда
            // Не 202 Accepted - записать в очередь повторной отправки
            ЗаписатьВОчередьПовтора(ИдентификаторСообщения, ТипСобытия, ТелоЗапроса,
                Ответ.КодСостояния);
        КонецЕсли;
    Исключение
        // Сервис недоступен - записать в очередь повторной отправки
        ЗаписатьВОчередьПовтора(ИдентификаторСообщения, ТипСобытия, ТелоЗапроса, 0);
    КонецПопытки;
КонецПроцедуры
```

### 2.3. Retry Queue (Регистр сведений в расширении)

При недоступности integration-service события сохраняются в регистр сведений расширения и повторно отправляются фоновым заданием.

**Регистр сведений `ОчередьОтправкиСобытий`:**

| Измерение/Ресурс | Тип | Назначение |
|-------------------|-----|------------|
| ИдентификаторСообщения (измерение) | УникальныйИдентификатор | Ключ дедупликации |
| ТипСобытия (ресурс) | Строка(100) | `order.created`, `shipment.posted`, etc. |
| ТелоСообщения (ресурс) | ХранилищеЗначения | JSON payload (сжатый) |
| ДатаСоздания (ресурс) | Дата | Время постановки в очередь |
| КоличествоПопыток (ресурс) | Число(3,0) | Счетчик попыток (макс. 100) |
| СледующаяПопытка (ресурс) | Дата | Дата+время следующей попытки |
| КодОшибки (ресурс) | Число(5,0) | Последний HTTP-код ответа |
| ТекстОшибки (ресурс) | Строка(500) | Описание последней ошибки |
| Статус (ресурс) | Строка(20) | `pending` / `sending` / `failed` / `expired` |

**Фоновое задание повторной отправки:**

```bsl
// Расширение: ОбщийМодуль.ИнтеграцияРентабельностьФоновые

Процедура ОбработатьОчередьОтправки() Экспорт
    // Расписание: каждые 30 секунд
    // Макс. batch: 50 записей за цикл

    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ ПЕРВЫЕ 50
        | ИдентификаторСообщения,
        | ТипСобытия,
        | ТелоСообщения,
        | КоличествоПопыток
        |ИЗ
        | РегистрСведений.ОчередьОтправкиСобытий КАК Очередь
        |ГДЕ
        | Очередь.Статус = ""pending""
        | И Очередь.СледующаяПопытка <= &ТекущаяДата
        | И Очередь.КоличествоПопыток < 100
        |УПОРЯДОЧИТЬ ПО
        | Очередь.ДатаСоздания";
    Запрос.УстановитьПараметр("ТекущаяДата", ТекущаяДата());

    Выборка = Запрос.Выполнить().Выбрать();
    Пока Выборка.Следующий() Цикл
        Попытка
            ОтправитьИзОчереди(Выборка);
        Исключение
            ОбновитьПопытку(Выборка.ИдентификаторСообщения,
                Выборка.КоличествоПопыток + 1);
        КонецПопытки;
    КонецЦикла;
КонецПроцедуры
```

**Retry backoff (экспоненциальный):**

| Попытка | Задержка | Суммарное время |
|---------|----------|-----------------|
| 1 | 30 сек | 30 сек |
| 2 | 1 мин | 1.5 мин |
| 3 | 2 мин | 3.5 мин |
| 4 | 5 мин | 8.5 мин |
| 5 | 10 мин | 18.5 мин |
| 6-10 | 15 мин | ~93 мин |
| 11-20 | 30 мин | ~8 час |
| 21-50 | 1 час | ~38 час |
| 51-100 | 2 час | ~138 час (~6 дн) |

После 100 попыток (примерно 6 суток непрерывной недоступности) запись получает статус `expired`. Администратор уведомляется через 1С (задача) после 10 неудачных попыток подряд.

### 2.4. HTTP Endpoint Specification (integration-service)

**Endpoint:** `POST /api/v1/events`

**Назначение:** Единая точка приема событий из 1С. integration-service маршрутизирует событие в соответствующий Kafka-топик.

**Headers:**

| Header | Обязателен | Описание |
|--------|-----------|----------|
| `Content-Type` | да | `application/json` |
| `X-Api-Key` | да | API-ключ для аутентификации (ротация ежемесячно) |
| `X-Message-Id` | да | UUID дедупликации (генерирует 1С) |
| `X-Event-Type` | да | Тип события (routing key) |

**Request Body:**

```json
{
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "order.created",
  "timestamp": "2026-03-02T10:30:00+03:00",
  "source": "1c_ut",
  "schema_version": "v1",
  "payload": { /* event-specific data */ }
}
```

**Responses:**

| Code | Описание | Действие 1С |
|------|----------|-------------|
| 202 Accepted | Событие принято, будет опубликовано в Kafka | Удалить из очереди |
| 400 Bad Request | Невалидный JSON или отсутствуют обязательные поля | Логировать, не повторять |
| 401 Unauthorized | Неверный API-ключ | Логировать, уведомить администратора |
| 409 Conflict | Дубликат (message_id уже обработан) | Удалить из очереди (идемпотентно) |
| 429 Too Many Requests | Rate limit exceeded | Повторить через `Retry-After` |
| 500 Internal Server Error | Внутренняя ошибка сервиса | Записать в retry queue |
| 503 Service Unavailable | Kafka недоступен | Записать в retry queue |

**Rate Limiting:** 200 req/sec per API key. 1С отправляет примерно 1-5 событий/сек при нормальной нагрузке. Пиковая нагрузка (массовое проведение) -- до 50 событий/сек.

### 2.5. Event Routing (integration-service)

```go
// internal/adapter/http/event_handler.go

var eventTopicMap = map[string]string{
    "order.created":       "1c.order.created.v1",
    "order.updated":       "1c.order.updated.v1",
    "shipment.posted":     "1c.shipment.posted.v1",
    "shipment.returned":   "1c.shipment.returned.v1",
    "price.npss-updated":  "1c.price.npss-updated.v1",
    "price.purchase-changed": "1c.price.purchase-changed.v1",
    "client.updated":      "1c.client.updated.v1",
    "ls.created":          "1c.ls.created.v1",
    "ls.plan-changed":     "1c.ls.plan-changed.v1",
}

var eventPartitionKeyMap = map[string]string{
    "order.created":       "order_id",
    "order.updated":       "order_id",
    "shipment.posted":     "order_id",
    "shipment.returned":   "order_id",
    "price.npss-updated":  "product_id",
    "price.purchase-changed": "product_id",
    "client.updated":      "client_id",
    "ls.created":          "ls_id",
    "ls.plan-changed":     "ls_id",
}
```

### 2.6. Event Payload Schemas (9 Inbound Topics)

#### 2.6.1. `1c.order.created.v1` / `1c.order.updated.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OrderEvent",
  "type": "object",
  "required": ["order_id", "local_estimate_id", "client_id", "manager_id",
               "business_unit_id", "total_amount", "line_items"],
  "properties": {
    "order_id": {
      "type": "string",
      "description": "Номер Заказа покупателя в 1С (e.g. ЗП-000012345)"
    },
    "local_estimate_id": {
      "type": "string",
      "description": "Код ЛС (e.g. ЛС-00001234)"
    },
    "client_id": {
      "type": "string",
      "description": "Код контрагента в 1С"
    },
    "manager_id": {
      "type": "string",
      "description": "Код менеджера (сотрудника) в 1С"
    },
    "business_unit_id": {
      "type": "string",
      "description": "Код бизнес-юнита"
    },
    "source": {
      "type": "string",
      "enum": ["manual", "edi"],
      "default": "manual"
    },
    "total_amount": {
      "type": "integer",
      "description": "Сумма заказа в копейках"
    },
    "currency": {
      "type": "string",
      "enum": ["RUB"],
      "default": "RUB"
    },
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["product_id", "quantity", "price", "amount"],
        "properties": {
          "product_id": {
            "type": "string",
            "description": "Код номенклатуры в 1С"
          },
          "quantity": {
            "type": "number",
            "minimum": 0.001
          },
          "price": {
            "type": "integer",
            "description": "Цена за единицу в копейках"
          },
          "amount": {
            "type": "integer",
            "description": "Сумма по строке в копейках"
          },
          "business_unit_id": {
            "type": "string"
          },
          "is_non_liquid": {
            "type": "boolean",
            "default": false,
            "description": "Признак неликвидной позиции (исключается из контроля)"
          }
        }
      }
    }
  }
}
```

#### 2.6.2. `1c.shipment.posted.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ShipmentPostedEvent",
  "type": "object",
  "required": ["shipment_doc_id", "order_id", "local_estimate_id",
               "posted_at", "line_items"],
  "properties": {
    "shipment_doc_id": {
      "type": "string",
      "description": "Номер РТУ в 1С (e.g. РТ-000054321)"
    },
    "order_id": {
      "type": "string",
      "description": "Номер связанного Заказа покупателя"
    },
    "local_estimate_id": {
      "type": "string"
    },
    "client_id": {
      "type": "string"
    },
    "posted_at": {
      "type": "string",
      "format": "date-time",
      "description": "Дата проведения РТУ (RFC 3339)"
    },
    "warehouse_id": {
      "type": "string",
      "description": "Код склада отгрузки"
    },
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["product_id", "quantity", "price", "amount"],
        "properties": {
          "product_id": { "type": "string" },
          "quantity": { "type": "number", "minimum": 0.001 },
          "price": { "type": "integer", "description": "Цена в копейках" },
          "amount": { "type": "integer", "description": "Сумма в копейках" }
        }
      }
    },
    "total_amount": {
      "type": "integer",
      "description": "Итоговая сумма РТУ в копейках"
    }
  }
}
```

#### 2.6.3. `1c.shipment.returned.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ShipmentReturnedEvent",
  "type": "object",
  "required": ["return_doc_id", "order_id", "local_estimate_id",
               "returned_at", "line_items"],
  "properties": {
    "return_doc_id": {
      "type": "string",
      "description": "Номер документа Возврат товаров от покупателя"
    },
    "order_id": { "type": "string" },
    "local_estimate_id": { "type": "string" },
    "client_id": { "type": "string" },
    "returned_at": {
      "type": "string",
      "format": "date-time"
    },
    "reason": {
      "type": "string",
      "description": "Причина возврата"
    },
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["product_id", "quantity", "amount"],
        "properties": {
          "product_id": { "type": "string" },
          "quantity": { "type": "number", "minimum": 0.001 },
          "amount": { "type": "integer" }
        }
      }
    },
    "total_amount": {
      "type": "integer",
      "description": "Итоговая сумма возврата в копейках"
    }
  }
}
```

#### 2.6.4. `1c.price.npss-updated.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "NPSSUpdatedEvent",
  "type": "object",
  "required": ["product_id", "npss", "method", "calculated_at"],
  "properties": {
    "product_id": {
      "type": "string",
      "description": "Код номенклатуры в 1С"
    },
    "npss": {
      "type": "integer",
      "description": "Новая НПСС в копейках"
    },
    "previous_npss": {
      "type": "integer",
      "description": "Предыдущая НПСС в копейках (для delta)"
    },
    "method": {
      "type": "string",
      "enum": ["planned", "temporary"],
      "description": "Метод расчета НПСС"
    },
    "purchase_price": {
      "type": "integer",
      "description": "Закупочная цена в копейках"
    },
    "logistics_cost": {
      "type": "integer",
      "description": "Логистические расходы в копейках"
    },
    "overhead_cost": {
      "type": "integer",
      "description": "Накладные расходы в копейках"
    },
    "calculated_at": {
      "type": "string",
      "format": "date-time"
    },
    "calculated_by": {
      "type": "string",
      "description": "Код сотрудника, выполнившего расчет"
    }
  }
}
```

#### 2.6.5. `1c.price.purchase-changed.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PurchasePriceChangedEvent",
  "type": "object",
  "required": ["product_id", "new_purchase_price", "previous_purchase_price",
               "changed_at"],
  "properties": {
    "product_id": { "type": "string" },
    "new_purchase_price": {
      "type": "integer",
      "description": "Новая закупочная цена в копейках"
    },
    "previous_purchase_price": {
      "type": "integer",
      "description": "Предыдущая закупочная цена в копейках"
    },
    "deviation_pct": {
      "type": "number",
      "description": "Отклонение в процентах ((new-old)/old*100)"
    },
    "supplier_id": {
      "type": "string",
      "description": "Код поставщика в 1С"
    },
    "origin": {
      "type": "string",
      "enum": ["import", "domestic", "production"],
      "description": "Происхождение товара"
    },
    "changed_at": {
      "type": "string",
      "format": "date-time"
    },
    "source_document_id": {
      "type": "string",
      "description": "Номер документа-основания (ПТУ, Упаковочный лист)"
    }
  }
}
```

**Trigger logic (integration-service):** Если `deviation_pct > 15%` (LS-BR-075, ФМ п. 3.19) -- integration-service генерирует событие `evt.integration.price.exchange-trigger.v1` для оповещения о необходимости пересмотра НПСС в течение 5 рабочих дней.

#### 2.6.6. `1c.client.updated.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ClientUpdatedEvent",
  "type": "object",
  "required": ["client_id", "name"],
  "properties": {
    "client_id": {
      "type": "string",
      "description": "Код контрагента в 1С"
    },
    "name": {
      "type": "string",
      "maxLength": 500
    },
    "inn": {
      "type": "string",
      "pattern": "^[0-9]{10,12}$"
    },
    "is_strategic": {
      "type": "boolean",
      "default": false
    },
    "strategic_criteria": {
      "type": "string",
      "enum": ["volume", "contract", "category_a", null]
    },
    "strategic_since": {
      "type": "string",
      "format": "date-time"
    },
    "allowed_deviation": {
      "type": "number",
      "description": "Допустимое отклонение для стратегического клиента (п.п.)"
    },
    "manager_id": { "type": "string" },
    "business_unit_id": { "type": "string" },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

#### 2.6.7. `1c.ls.created.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LSCreatedEvent",
  "type": "object",
  "required": ["ls_id", "client_id", "manager_id", "business_unit_id",
               "planned_profitability", "total_amount", "expires_at", "line_items"],
  "properties": {
    "ls_id": {
      "type": "string",
      "description": "Код ЛС в 1С (e.g. ЛС-00001234)"
    },
    "client_id": { "type": "string" },
    "manager_id": { "type": "string" },
    "business_unit_id": { "type": "string" },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time"
    },
    "planned_profitability": {
      "type": "integer",
      "description": "Плановая рентабельность в basis points (сотые доли %)"
    },
    "total_amount": {
      "type": "integer",
      "description": "Общая сумма ЛС в копейках"
    },
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["product_id", "quantity", "price", "npss"],
        "properties": {
          "product_id": { "type": "string" },
          "quantity": { "type": "number", "minimum": 0.001 },
          "price": { "type": "integer", "description": "Цена в копейках" },
          "amount": { "type": "integer", "description": "Сумма в копейках" },
          "npss": { "type": "integer", "description": "Зафиксированная НПСС в копейках" },
          "business_unit_id": { "type": "string" }
        }
      }
    }
  }
}
```

#### 2.6.8. `1c.ls.plan-changed.v1`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LSPlanChangedEvent",
  "type": "object",
  "required": ["ls_id", "old_planned_profitability", "new_planned_profitability",
               "changed_at"],
  "properties": {
    "ls_id": { "type": "string" },
    "old_planned_profitability": {
      "type": "integer",
      "description": "Предыдущая плановая рентабельность (basis points)"
    },
    "new_planned_profitability": {
      "type": "integer",
      "description": "Новая плановая рентабельность (basis points)"
    },
    "reason": {
      "type": "string",
      "description": "Причина изменения плана"
    },
    "changed_by": {
      "type": "string",
      "description": "Код сотрудника"
    },
    "changed_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

**Trigger logic (profitability-service):** При получении `LSPlanChangedEvent` запускается CrossValidator (phase1a, секция 5.6) -- пересчитывает отклонения всех согласованных (но не отгруженных) Заказов по ЛС и при изменении уровня согласования отзывает согласование (BR-020/LS-BR-077).

### 2.7. API Key Management

**Ротация API-ключа:**
- Хранение: Infisical (secret name `INTEGRATION_1C_API_KEY`)
- Ротация: ежемесячно 1-го числа
- Процедура:
  1. Infisical: сгенерировать новый ключ (UUID v4), сохранить как `INTEGRATION_1C_API_KEY_NEW`
  2. integration-service: при deploy считывает оба ключа, принимает оба 48 часов
  3. Администратор 1С: обновляет константу `ИнтеграцияAPIКлюч` в расширении
  4. Через 48 часов: старый ключ деактивируется

**Настройки в 1С (константы расширения):**

| Константа | Тип | Значение |
|-----------|-----|----------|
| `ИнтеграцияСервисURL` | Строка(200) | `profit-api.ekf.su` (prod) / `profit-api-staging.ekf.su` (staging) |
| `ИнтеграцияСервисПорт` | Число(5,0) | `443` (HTTPS) |
| `ИнтеграцияAPIКлюч` | Строка(100) | API key (из Infisical) |
| `ИнтеграцияАктивна` | Булево | `Истина` / `Ложь` (kill switch) |

### 2.8. Processing Flow in integration-service

```go
// internal/adapter/http/event_handler.go

func (h *EventHandler) HandleEvent(w http.ResponseWriter, r *http.Request) {
    // 1. Validate API key
    apiKey := r.Header.Get("X-Api-Key")
    if !h.auth.ValidateAPIKey(apiKey) {
        respondJSON(w, http.StatusUnauthorized, problemDetail("Invalid API key"))
        return
    }

    // 2. Parse envelope
    var envelope EventEnvelope
    if err := json.NewDecoder(r.Body).Decode(&envelope); err != nil {
        respondJSON(w, http.StatusBadRequest, problemDetail("Invalid JSON"))
        return
    }

    // 3. Idempotency check (message_id dedup)
    exists, err := h.dedup.Exists(r.Context(), envelope.MessageID)
    if err != nil {
        respondJSON(w, http.StatusInternalServerError, problemDetail("Dedup check failed"))
        return
    }
    if exists {
        respondJSON(w, http.StatusConflict, map[string]string{
            "status": "duplicate", "message_id": envelope.MessageID,
        })
        return
    }

    // 4. Validate event_type -> topic mapping
    topic, ok := eventTopicMap[envelope.EventType]
    if !ok {
        respondJSON(w, http.StatusBadRequest, problemDetail("Unknown event_type"))
        return
    }

    // 5. Validate payload schema
    if err := h.validator.Validate(envelope.EventType, envelope.Payload); err != nil {
        respondJSON(w, http.StatusBadRequest, problemDetail("Schema validation: "+err.Error()))
        return
    }

    // 6. Extract partition key
    partitionKeyField := eventPartitionKeyMap[envelope.EventType]
    partitionKey := extractField(envelope.Payload, partitionKeyField)

    // 7. Write to outbox (same transaction as dedup record)
    if err := h.outbox.WriteInTx(r.Context(), OutboxEntry{
        Topic:     topic,
        Key:       partitionKey,
        Payload:   envelope,
        MessageID: envelope.MessageID,
    }); err != nil {
        respondJSON(w, http.StatusInternalServerError, problemDetail("Outbox write failed"))
        return
    }

    // 8. Return 202 Accepted
    respondJSON(w, http.StatusAccepted, map[string]string{
        "status": "accepted", "message_id": envelope.MessageID,
    })
}
```

---

## 3. Kafka to 1С Callback API (Outbound)

### 3.1. Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
| Kafka             |     | integration-      |     | 1С:УТ 10.2        |
|                   |     | service           |     | (расширение .cfe) |
| 3 outbound topics | TCP | Consumer          | HTTP|                   |
| cmd.*.v1          | --> | (franz-go)        | PUT | HTTP-сервис       |
|                   |     |                   | --> | /api/v1/callback  |
|                   |     | Retry + DLQ       |     |                   |
+-------------------+     +-------------------+     +-------------------+
```

integration-service потребляет 3 outbound command topics и вызывает REST API в 1С (HTTP-сервис расширения) для доставки результатов согласования, санкций и блокировок.

### 3.2. 1С Callback HTTP-сервис (расширение)

**HTTP-сервис:** `КонтрольРентабельностиКоллбэк`

**Базовый URL:** `https://1c-ekf-app-01:443/EKF/hs/profit-callback/api/v1/`

**Аутентификация:** API key в заголовке `X-Api-Key` (отдельный ключ от inbound, Infisical: `CALLBACK_1C_API_KEY`).

#### 3.2.1. PUT /api/v1/callback/approval/{order_id}/result

**Назначение:** Передача результата согласования заказа в 1С.

**Source Kafka topic:** `cmd.approval.result.v1`

**Request:**

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_id": "ЗП-000012345",
  "decision": "approved",
  "approval_level": "rbu",
  "approver_name": "Петров И.А.",
  "approver_comment": "Согласовано, клиент стратегический",
  "decided_at": "2026-03-02T14:30:00+03:00",
  "mode": "standard",
  "deviation_pp": 3.5,
  "correction_price": null,
  "expires_at": "2026-03-09T14:30:00+03:00"
}
```

**Fields:**

| Поле | Тип | Обязательно | Описание |
|------|-----|------------|----------|
| `request_id` | string (UUID) | да | Ключ идемпотентности |
| `order_id` | string | да | Номер Заказа покупателя в 1С |
| `decision` | string | да | `approved` / `rejected` / `approved_with_correction` / `expired` / `fallback_approved` |
| `approval_level` | string | да | `auto` / `rbu` / `dp` / `gd` |
| `approver_name` | string | нет | ФИО согласующего (пусто для auto) |
| `approver_comment` | string | нет | Комментарий согласующего |
| `decided_at` | string (datetime) | да | Время решения (RFC 3339) |
| `mode` | string | да | `standard` / `fallback` |
| `deviation_pp` | number | да | Отклонение в п.п. |
| `correction_price` | integer | нет | Скорректированная цена (копейки), для `approved_with_correction` |
| `expires_at` | string (datetime) | нет | Срок действия согласования (+5 р.д.), для `approved` |

**Response (1С):**

```json
{
  "status": "ok",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "processed_at": "2026-03-02T14:30:01+03:00"
}
```

| Code | Описание |
|------|----------|
| 200 OK | Результат обработан |
| 409 Conflict | Дубликат request_id (идемпотентно, ок) |
| 400 Bad Request | Невалидные данные |
| 404 Not Found | Заказ не найден в 1С |
| 500 Internal Server Error | Ошибка обработки в 1С |

#### 3.2.2. PUT /api/v1/callback/sanction/{client_id}

**Назначение:** Уведомление 1С о применении/снятии санкции к контрагенту.

**Source Kafka topic:** `cmd.sanction.applied.v1`

**Request:**

```json
{
  "request_id": "660e8400-e29b-41d4-a716-446655440001",
  "client_id": "КА-000054321",
  "action": "applied",
  "sanction_type": "discount_reduction_3pp",
  "discount_reduction_pp": 3.0,
  "cumulative_reduction_pp": 3.0,
  "trigger_ls_id": "ЛС-00001234",
  "fulfillment_rate_pct": 42.5,
  "applied_at": "2026-03-02T09:00:00+03:00",
  "rehabilitation_at": "2026-09-02T09:00:00+03:00"
}
```

**Fields:**

| Поле | Тип | Обязательно | Описание |
|------|-----|------------|----------|
| `request_id` | string (UUID) | да | Ключ идемпотентности |
| `client_id` | string | да | Код контрагента в 1С |
| `action` | string | да | `applied` / `rehabilitated` / `cancelled` |
| `sanction_type` | string | да | `discount_reduction_3pp` / `discount_reduction_10pp` / `standard_prices_only` |
| `discount_reduction_pp` | number | да | Снижение скидки (п.п.) |
| `cumulative_reduction_pp` | number | да | Накопленное снижение (п.п.) |
| `trigger_ls_id` | string | да | ЛС, вызвавшая санкцию |
| `fulfillment_rate_pct` | number | да | Процент выкупа ЛС |
| `applied_at` | string (datetime) | да | Дата применения |
| `rehabilitation_at` | string (datetime) | нет | Дата реабилитации (для `applied`) |

#### 3.2.3. PUT /api/v1/callback/block/{order_id}

**Назначение:** Блокировка/разблокировка отгрузки заказа в WMS и 1С.

**Source Kafka topic:** `cmd.block.shipment.v1`

**Request:**

```json
{
  "request_id": "770e8400-e29b-41d4-a716-446655440002",
  "order_id": "ЗП-000012345",
  "action": "block",
  "reason": "pending_approval",
  "blocked_at": "2026-03-02T10:00:00+03:00",
  "blocked_by": "system"
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|------------|----------|
| `request_id` | string (UUID) | да | Ключ идемпотентности |
| `order_id` | string | да | Номер Заказа покупателя |
| `action` | string | да | `block` / `unblock` |
| `reason` | string | да | `pending_approval` / `rejected` / `npss_stale` / `sanction` |
| `blocked_at` | string (datetime) | да | Время действия |
| `blocked_by` | string | да | `system` / ФИО сотрудника |

### 3.3. Idempotency Strategy

**Механизм:** Каждый callback-запрос содержит `request_id` (UUID). 1С хранит таблицу обработанных request_id в регистре сведений `ОбработанныеКоллбэки`.

**Регистр сведений `ОбработанныеКоллбэки`:**

| Измерение/Ресурс | Тип | Назначение |
|-------------------|-----|------------|
| ИдентификаторЗапроса (измерение) | Строка(36) | request_id (UUID) |
| ДатаОбработки (ресурс) | Дата | Время обработки |
| ТипОперации (ресурс) | Строка(30) | `approval` / `sanction` / `block` |
| Результат (ресурс) | Строка(10) | `ok` / `error` |

**Логика обработки (1С BSL):**

```bsl
// HTTP-сервис: КонтрольРентабельностиКоллбэк
// Метод: ОбработатьЗапрос

Функция ОбработатьЗапрос(ИдентификаторЗапроса, ТипОперации, ДанныеЗапроса)
    // 1. Проверка дубликата
    Если ЗаписьУжеОбработана(ИдентификаторЗапроса) Тогда
        Возврат НовыйОтвет(409, "duplicate");
    КонецЕсли;

    // 2. Начать транзакцию
    НачатьТранзакцию();
    Попытка
        // 3. Обработать данные
        Если ТипОперации = "approval" Тогда
            ОбработатьРезультатСогласования(ДанныеЗапроса);
        ИначеЕсли ТипОперации = "sanction" Тогда
            ОбработатьСанкцию(ДанныеЗапроса);
        ИначеЕсли ТипОперации = "block" Тогда
            ОбработатьБлокировку(ДанныеЗапроса);
        КонецЕсли;

        // 4. Записать в dedup-регистр (в той же транзакции)
        ЗаписатьОбработанныйКоллбэк(ИдентификаторЗапроса, ТипОперации, "ok");

        ЗафиксироватьТранзакцию();
        Возврат НовыйОтвет(200, "ok");
    Исключение
        ОтменитьТранзакцию();
        Возврат НовыйОтвет(500, ОписаниеОшибки());
    КонецПопытки;
КонецФункции
```

**Очистка dedup-регистра:** Фоновое задание удаляет записи старше 30 дней.

### 3.4. Callback Consumer (integration-service)

```go
// internal/adapter/kafka/callback_consumer.go

type CallbackConsumer struct {
    httpClient *http.Client
    baseURL    string // "https://1c-ekf-app-01:443/EKF/hs/profit-callback/api/v1"
    apiKey     string
    metrics    *CallbackMetrics
}

// Routes for outbound topics
var callbackRoutes = map[string]func(c *CallbackConsumer, payload json.RawMessage) error{
    "cmd.approval.result.v1":  (*CallbackConsumer).sendApprovalResult,
    "cmd.sanction.applied.v1": (*CallbackConsumer).sendSanction,
    "cmd.block.shipment.v1":   (*CallbackConsumer).sendBlock,
}

func (c *CallbackConsumer) sendApprovalResult(payload json.RawMessage) error {
    var event ApprovalResultEvent
    if err := json.Unmarshal(payload, &event); err != nil {
        return fmt.Errorf("unmarshal approval result: %w", err)
    }

    url := fmt.Sprintf("%s/callback/approval/%s/result", c.baseURL, event.OrderID)
    return c.sendWithRetry(url, http.MethodPut, payload, event.RequestID)
}

func (c *CallbackConsumer) sendWithRetry(url, method string, body json.RawMessage, requestID string) error {
    // Retry policy: 3 attempts (1s, 30s, 5min)
    delays := []time.Duration{1 * time.Second, 30 * time.Second, 5 * time.Minute}

    for attempt, delay := range delays {
        req, _ := http.NewRequest(method, url, bytes.NewReader(body))
        req.Header.Set("Content-Type", "application/json")
        req.Header.Set("X-Api-Key", c.apiKey)
        req.Header.Set("X-Request-Id", requestID)

        resp, err := c.httpClient.Do(req)
        if err == nil {
            defer resp.Body.Close()
            if resp.StatusCode == 200 || resp.StatusCode == 409 {
                c.metrics.Success.Inc()
                return nil // 200 OK or 409 duplicate = success
            }
            if resp.StatusCode == 400 {
                c.metrics.PermanentError.Inc()
                return fmt.Errorf("permanent error: 400 Bad Request")
            }
        }

        c.metrics.RetryAttempt.WithLabelValues(fmt.Sprintf("%d", attempt+1)).Inc()
        if attempt < len(delays)-1 {
            time.Sleep(delay)
        }
    }

    c.metrics.DLQ.Inc()
    return fmt.Errorf("callback failed after %d attempts", len(delays))
}
```

### 3.5. API Key Rotation (Outbound)

Отдельный от inbound API-ключ. Infisical secret: `CALLBACK_1C_API_KEY`.

**Процедура ротации (аналогична секции 2.7):**
1. Infisical: новый ключ `CALLBACK_1C_API_KEY_NEW`
2. 1С (расширение): обновить константу `КоллбэкAPIКлюч`, HTTP-сервис принимает оба ключа 48 часов
3. integration-service: deploy с новым ключом
4. Через 48 часов: старый ключ деактивируется в 1С

---

## 4. ELMA BPM Integration

### 4.1. Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
| workflow-service   |     | ELMA BPM          |     | 1С:УТ (косвенно)  |
|                   |     | 172.20.0.226      |     |                   |
| ApprovalRouter    | REST| REST API           |     |                   |
| (circuit breaker) | --> | /api/bpm/tasks     |     |                   |
|                   |     |                   |     |                   |
| Callback handler  | <-- | Webhook            |     |                   |
|                   |     | (решение)          |     |                   |
|                   |     |                   |     |                   |
| Fallback mode     |     |                   |     |                   |
| (auto/FIFO queue) |     |                   |     |                   |
+-------------------+     +-------------------+     +-------------------+
```

### 4.2. ELMA REST API Specification

**Base URL:** `https://elma.ekf.su/api/bpm` (172.20.0.226)

**Authentication:** API key в заголовке `Authorization: Bearer {ELMA_API_KEY}` (Infisical: `ELMA_API_KEY`).

#### 4.2.1. Create Approval Task

```
POST /api/bpm/tasks
Content-Type: application/json
Authorization: Bearer {ELMA_API_KEY}
X-Idempotency-Key: {process_id}
```

**Request:**

```json
{
  "process_type": "shipment_approval",
  "external_id": "AP-550e8400-e29b-41d4-a716-446655440000",
  "priority": "P1",
  "assignee_id": "emp-12345",
  "title": "Согласование отгрузки ЗП-000012345",
  "description": "Отклонение: 5.2 п.п. | ЛС: ЛС-00001234 | Клиент: ООО Рога и Копыта",
  "deadline": "2026-03-03T10:30:00+03:00",
  "metadata": {
    "shipment_id": "ЗП-000012345",
    "local_estimate_id": "ЛС-00001234",
    "deviation_pp": 5.2,
    "required_level": "rbu",
    "callback_url": "https://profit-api.ekf.su/api/v1/approvals/elma-callback"
  }
}
```

**Response:**

```json
{
  "task_id": "elma-task-98765",
  "status": "pending",
  "created_at": "2026-03-02T10:30:05+03:00"
}
```

#### 4.2.2. Get Task Status

```
GET /api/bpm/tasks/{task_id}
Authorization: Bearer {ELMA_API_KEY}
```

**Response:**

```json
{
  "task_id": "elma-task-98765",
  "status": "completed",
  "decision": "approved",
  "decided_by": "Петров И.А.",
  "comment": "Согласовано",
  "decided_at": "2026-03-02T11:15:00+03:00"
}
```

#### 4.2.3. Cancel Task

```
POST /api/bpm/tasks/{task_id}/cancel
Authorization: Bearer {ELMA_API_KEY}
```

**Используется при:** отзыв согласования из-за cross-validation (BR-020/LS-BR-077), истечение срока действия, отмена заказа.

### 4.3. Callback Handler (workflow-service)

ELMA вызывает callback URL при принятии решения.

**Endpoint:** `POST /api/v1/approvals/elma-callback`

```json
{
  "task_id": "elma-task-98765",
  "external_id": "AP-550e8400-e29b-41d4-a716-446655440000",
  "decision": "approved",
  "decided_by": {
    "id": "emp-12345",
    "name": "Петров И.А."
  },
  "comment": "Согласовано, клиент стратегический",
  "decided_at": "2026-03-02T11:15:00+03:00"
}
```

**Mapping:** `task.decision` -> domain `ApprovalDecisionValue`:

| ELMA decision | Domain decision |
|---------------|----------------|
| `approved` | `ApprovalDecisionApproved` |
| `rejected` | `ApprovalDecisionRejected` |
| `returned` | `ApprovalDecisionCorrectionRequested` |

### 4.4. Circuit Breaker Configuration

```go
// internal/adapter/elma/client.go

type CircuitBreakerConfig struct {
    FailureThreshold   int           // 5 consecutive failures
    OpenTimeout        time.Duration // 30 seconds
    HalfOpenMaxRequests int          // 1 test request
    SuccessThreshold   int           // 1 success to close
}

type CircuitBreaker struct {
    state             CircuitState // closed, open, half_open
    failures          int
    lastFailure       time.Time
    config            CircuitBreakerConfig
    mu                sync.RWMutex
    onStateChange     func(from, to CircuitState)
}

type CircuitState string

const (
    CircuitClosed   CircuitState = "closed"
    CircuitOpen     CircuitState = "open"
    CircuitHalfOpen CircuitState = "half_open"
)
```

**State transitions:**

```
+--------+     5 failures     +------+     30s elapsed     +-----------+
| CLOSED | =================> | OPEN | ==================> | HALF_OPEN |
+--------+                    +------+                     +-----------+
    ^                                                          |    |
    |                    1 success                             |    |
    +----------------------------------------------------------+    |
                                                                    |
                         1 failure                                  |
    +------+  <-----------------------------------------------------+
    | OPEN |
    +------+
```

### 4.5. Fallback Mode (ELMA Down)

Активируется автоматически при переходе circuit breaker в состояние OPEN (LS-FR-070..071, LS-BR-078).

**Правила fallback:**

| Отклонение | Действие | FM Reference |
|------------|----------|-------------|
| <= 5.00 п.п. | Автосогласование с пометкой `mode=fallback` | LS-FR-070 |
| > 5.00 п.п. | Очередь FIFO (приоритет: P1 > P2, внутри приоритета -- FIFO) | LS-FR-071 |

**FIFO Queue (таблица `fallback_queue`):**

```sql
-- См. phase1b_go_architecture.md, секция 3.5
-- Table: fallback_queue
-- Columns: id, process_id, priority, deviation, enqueued_at, sent_to_elma_at, position
```

**Recovery Procedure (ELMA restored):**

1. Circuit breaker переходит в HALF_OPEN (через 30 сек)
2. Тестовый запрос `GET /api/bpm/health` -- если 200, переход в CLOSED
3. Drain queue: отправить все задачи из `fallback_queue` в ELMA (P1 first, FIFO order)
4. Для каждой задачи: обновить `sent_to_elma_at`, создать ELMA task, связать `elma_task_id`
5. Emit event `evt.workflow.fallback.queue-drained.v1`
6. Уведомить согласующих о задачах, одобренных в fallback-режиме (для постфактум-контроля)

**Health Check:**

```go
// Periodic health check every 5 minutes when circuit is OPEN
func (c *ELMAClient) healthCheckLoop(ctx context.Context) {
    ticker := time.NewTicker(5 * time.Minute)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if c.circuitBreaker.State() == CircuitOpen {
                resp, err := c.httpClient.Get(c.baseURL + "/api/health")
                if err == nil && resp.StatusCode == 200 {
                    c.circuitBreaker.TransitionToHalfOpen()
                }
            }
        }
    }
}
```

### 4.6. ELMA Integration Metrics

| Metric | Type | Labels | Alert Threshold |
|--------|------|--------|-----------------|
| `elma_requests_total` | Counter | `method`, `status` | - |
| `elma_request_duration_seconds` | Histogram | `method` | p99 > 10s |
| `elma_circuit_breaker_state` | Gauge | - | state = open > 5 min |
| `elma_fallback_queue_size` | Gauge | `priority` | size > 20 |
| `elma_fallback_auto_approved_total` | Counter | - | > 10/hour |

---

## 5. ЦБ РФ Exchange Rates

### 5.1. Integration Design

**Назначение:** Мониторинг курсов валют ЦБ РФ для автотриггера НПСС (LS-BR-075). Если курс за 7 дней отклоняется более чем на 5% -- инициируется пересмотр НПСС импортных товаров.

**Endpoint:** `https://www.cbr.ru/scripts/XML_daily.asp?date_req=DD/MM/YYYY`

**Валюты:** USD (R01235), EUR (R01239), CNY (R01375)

**Расписание:** Ежедневно в 08:00 MSK (cron в integration-service).

### 5.2. XML Response Format

```xml
<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="02.03.2026" name="Foreign Currency Market">
    <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Доллар США</Name>
        <Value>91,2345</Value>
        <VunitRate>91,2345</VunitRate>
    </Valute>
    <Valute ID="R01239">
        <NumCode>978</NumCode>
        <CharCode>EUR</CharCode>
        <Nominal>1</Nominal>
        <Name>Евро</Name>
        <Value>98,7654</Value>
        <VunitRate>98,7654</VunitRate>
    </Valute>
    <Valute ID="R01375">
        <NumCode>156</NumCode>
        <CharCode>CNY</CharCode>
        <Nominal>1</Nominal>
        <Name>Китайский юань</Name>
        <Value>12,5678</Value>
        <VunitRate>12,5678</VunitRate>
    </Valute>
</ValCurs>
```

### 5.3. Exchange Rate Fetcher (integration-service)

```go
// internal/adapter/cbr/fetcher.go

type CBRFetcher struct {
    httpClient  *http.Client
    currencies  []string // ["USD", "EUR", "CNY"]
    repo        ExchangeRateRepository
    publisher   EventPublisher
    metrics     *CBRMetrics
    logger      *slog.Logger
}

type ExchangeRateRecord struct {
    Currency  string
    Rate      float64
    RateDate  time.Time
    FetchedAt time.Time
}

func (f *CBRFetcher) FetchDaily(ctx context.Context) error {
    date := time.Now().In(moscowTZ)
    url := fmt.Sprintf("https://www.cbr.ru/scripts/XML_daily.asp?date_req=%s",
        date.Format("02/01/2006"))

    // Retry 3x with backoff (1s, 5s, 15s)
    var body []byte
    var err error
    delays := []time.Duration{1*time.Second, 5*time.Second, 15*time.Second}
    for attempt, delay := range delays {
        body, err = f.fetchURL(ctx, url)
        if err == nil {
            break
        }
        f.logger.Warn("CBR fetch failed", "attempt", attempt+1, "error", err)
        if attempt < len(delays)-1 {
            time.Sleep(delay)
        }
    }
    if err != nil {
        f.metrics.FetchErrors.Inc()
        // Use cached rates -- last known good rates
        f.logger.Error("CBR unavailable, using cached rates", "error", err)
        return err
    }

    // Parse XML (windows-1251 encoding)
    rates, err := parseXML(body, f.currencies)
    if err != nil {
        return fmt.Errorf("parse CBR XML: %w", err)
    }

    // Save to DB and check trigger
    for _, rate := range rates {
        if err := f.repo.Save(ctx, rate); err != nil {
            return fmt.Errorf("save rate %s: %w", rate.Currency, err)
        }

        // Check 7-day deviation trigger (LS-BR-075)
        change7d, err := f.repo.GetChange7Days(ctx, rate.Currency, rate.RateDate)
        if err != nil {
            f.logger.Error("failed to compute 7d change", "currency", rate.Currency, "error", err)
            continue
        }

        if math.Abs(change7d) > 5.0 {
            // Trigger NPSS review for import products
            f.publisher.Publish(ctx, ExchangeRateTriggerEvent{
                Currency:    rate.Currency,
                CurrentRate: rate.Rate,
                Change7dPct: change7d,
                Date:        rate.RateDate,
            })
            f.metrics.Triggers.WithLabelValues(rate.Currency).Inc()
        }
    }

    f.metrics.FetchSuccess.Inc()
    return nil
}
```

### 5.4. Cron Schedule

```go
// internal/infrastructure/cron/scheduler.go

func (s *Scheduler) RegisterJobs() {
    // Daily at 08:00 MSK
    s.cron.AddFunc("0 8 * * *", func() {
        ctx := context.Background()
        if err := s.cbrFetcher.FetchDaily(ctx); err != nil {
            s.logger.Error("CBR daily fetch failed", "error", err)
            s.notifier.AlertChannel("cbr_fetch_failed", err.Error())
        }
    })
}
```

### 5.5. Cache Strategy

При недоступности ЦБ РФ используются последние успешно полученные курсы из таблицы `mdm_exchange_rates` (см. phase1b, секция 5.6). Курс считается актуальным в течение 3 дней (выходные + праздники). После 3 дней без обновлений генерируется alert.

---

## 6. WMS Integration

### 6.1. Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
| workflow-service   |     | WMS (LeadWMS)     |     | integration-      |
|                   |     | 172.20.0.210      |     | service           |
|                   |     |                   |     |                   |
| Approval result   | REST| POST /api/v1/     |     |                   |
| =================>| --> |   shipment-       |     |                   |
|                   |     |   control         |     |                   |
|                   |     |                   |     |                   |
|                   |     | Webhook           | POST| Fulfillment       |
|                   |     | (факт отгрузки)   | --> | webhook handler   |
|                   |     | =================>|     |                   |
+-------------------+     +-------------------+     +-------------------+
```

### 6.2. WMS Outbound (Go -> WMS)

**Назначение:** После согласования отгрузки (или блокировки) -- передать статус в WMS для разрешения/запрета физической отгрузки со склада.

**Trigger:** Потребление topic `cmd.block.shipment.v1` в integration-service.

**Endpoint:** `POST https://wms.ekf.su/api/v1/shipment-control`

**Request:**

```json
{
  "request_id": "880e8400-e29b-41d4-a716-446655440003",
  "order_id": "ЗП-000012345",
  "action": "allow",
  "approval_status": "approved",
  "approved_by": "Петров И.А.",
  "approved_at": "2026-03-02T14:30:00+03:00",
  "expires_at": "2026-03-09T14:30:00+03:00",
  "comment": "Согласовано РБЮ"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `request_id` | string (UUID) | Идемпотентный ключ |
| `order_id` | string | Номер Заказа |
| `action` | string | `allow` / `deny` / `revoke` |
| `approval_status` | string | `approved` / `rejected` / `expired` / `pending` |
| `approved_by` | string | ФИО согласующего |
| `approved_at` | string (datetime) | Время решения |
| `expires_at` | string (datetime) | Срок действия разрешения |
| `comment` | string | Комментарий |

**Response:**

```json
{
  "status": "ok",
  "request_id": "880e8400-e29b-41d4-a716-446655440003",
  "wms_internal_id": "WMS-SHP-98765"
}
```

**Circuit Breaker:** 5 failures -> open -> 30s -> half-open (аналогично ELMA, секция 4.4).

**Fallback:** При недоступности WMS -- логировать в outbox, повторить при восстановлении. Склад продолжает работать по текущим правилам (без блокировки).

### 6.3. WMS Inbound (WMS -> Go)

**Назначение:** WMS сообщает о фактической отгрузке товаров со склада. Этот факт фиксирует точку невозврата (INV-SH-03, LS-BR-018) и обновляет фактическую рентабельность.

**Endpoint (integration-service):** `POST /api/v1/webhooks/wms/fulfillment`

**Authentication:** HMAC-SHA256 подпись в заголовке `X-WMS-Signature` (shared secret из Infisical: `WMS_WEBHOOK_SECRET`).

**Request (от WMS):**

```json
{
  "event_id": "wms-evt-12345",
  "event_type": "shipment.fulfilled",
  "order_id": "ЗП-000012345",
  "warehouse_id": "МСК-СКЛАД-01",
  "fulfilled_at": "2026-03-02T16:00:00+03:00",
  "line_items": [
    {
      "product_id": "АРТ-001234",
      "quantity_ordered": 100,
      "quantity_shipped": 95,
      "reason_short": "stock_shortage"
    }
  ],
  "total_quantity_ordered": 100,
  "total_quantity_shipped": 95,
  "is_partial": true
}
```

**Processing:**

1. Validate HMAC signature
2. Dedup by `event_id` (таблица `kafka_dedup`)
3. Transform to domain event `ShipmentFulfilled` (или `ShipmentPartiallyFulfilled`)
4. Write to outbox -> Kafka topic `evt.profitability.shipment.fulfilled.v1`
5. profitability-service пересчитывает фактическую рентабельность
6. Если `is_partial=true` -- зафиксировать частичное выполнение для расчета выкупа ЛС

**Response:**

```json
{
  "status": "accepted",
  "event_id": "wms-evt-12345"
}
```

### 6.4. HMAC Signature Verification

```go
// internal/adapter/http/wms_webhook_handler.go

func (h *WMSWebhookHandler) verifySignature(body []byte, signatureHeader string) bool {
    mac := hmac.New(sha256.New, []byte(h.webhookSecret))
    mac.Write(body)
    expectedMAC := hex.EncodeToString(mac.Sum(nil))
    return hmac.Equal([]byte(expectedMAC), []byte(signatureHeader))
}
```

---

## 7. AD LDAP Integration

### 7.1. Architecture Overview

```
+-------------------+     +-------------------+
| api-gateway       |     | Active Directory  |
|                   |     | (LDAP)            |
| Auth middleware    | LDAP|                   |
| =================>| --> | Bind (auth)       |
|                   |     | Search (groups)   |
| JWT issuer        |     | User lookup       |
|                   |     |                   |
| Cache (Redis)     |     |                   |
| (roles, 15 min)   |     |                   |
+-------------------+     +-------------------+
```

### 7.2. LDAP Connection Configuration

| Параметр | Значение | Env Variable |
|----------|----------|-------------|
| URL | `ldaps://dc01.ekf.local:636` | `LDAP_URL` |
| Base DN | `DC=ekf,DC=local` | `LDAP_BASE_DN` |
| Bind DN (service account) | `CN=svc-profit,OU=ServiceAccounts,DC=ekf,DC=local` | `LDAP_BIND_DN` |
| Bind Password | (Infisical: `LDAP_BIND_PASSWORD`) | `LDAP_BIND_PASSWORD` |
| TLS | Required (LDAPS, port 636) | - |
| Timeout | 5 seconds | `LDAP_TIMEOUT` |
| Pool size | 5 connections | `LDAP_POOL_SIZE` |

### 7.3. Operations

#### 7.3.1. User Authentication (Bind)

```go
// internal/adapter/ldap/authenticator.go

func (a *LDAPAuthenticator) Authenticate(ctx context.Context, username, password string) (*User, error) {
    // 1. Search for user DN by sAMAccountName
    searchRequest := ldap.NewSearchRequest(
        a.baseDN,
        ldap.ScopeWholeSubtree, ldap.NeverDerefAliases, 1, 5, false,
        fmt.Sprintf("(&(objectClass=user)(sAMAccountName=%s))", ldap.EscapeFilter(username)),
        []string{"dn", "cn", "mail", "memberOf", "department"},
        nil,
    )

    result, err := a.conn.Search(searchRequest)
    if err != nil || len(result.Entries) == 0 {
        return nil, ErrUserNotFound
    }

    userDN := result.Entries[0].DN

    // 2. Bind with user credentials (verify password)
    err = a.pool.Bind(userDN, password)
    if err != nil {
        return nil, ErrInvalidCredentials
    }

    // 3. Extract groups -> map to app roles
    entry := result.Entries[0]
    groups := entry.GetAttributeValues("memberOf")
    role := a.mapGroupsToRole(groups)

    return &User{
        DN:         userDN,
        Username:   username,
        FullName:   entry.GetAttributeValue("cn"),
        Email:      entry.GetAttributeValue("mail"),
        Department: entry.GetAttributeValue("department"),
        Role:       role,
    }, nil
}
```

#### 7.3.2. Group Membership Query

```go
// AD Group -> App Role mapping (from phase1b, section 7.1)
var groupRoleMap = map[string]string{
    "CN=APP-PROFIT-MANAGER,OU=Applications,DC=ekf,DC=local": "manager",
    "CN=APP-PROFIT-RBU,OU=Applications,DC=ekf,DC=local":     "rbu",
    "CN=APP-PROFIT-DP,OU=Applications,DC=ekf,DC=local":      "dp",
    "CN=APP-PROFIT-GD,OU=Applications,DC=ekf,DC=local":      "gd",
    "CN=APP-PROFIT-FD,OU=Applications,DC=ekf,DC=local":      "fd",
}

func (a *LDAPAuthenticator) mapGroupsToRole(memberOf []string) string {
    // Priority: gd > fd > dp > rbu > manager
    // User gets highest available role
    priority := map[string]int{"gd": 5, "fd": 4, "dp": 3, "rbu": 2, "manager": 1}
    bestRole := ""
    bestPriority := 0

    for _, group := range memberOf {
        if role, ok := groupRoleMap[group]; ok {
            if p := priority[role]; p > bestPriority {
                bestRole = role
                bestPriority = p
            }
        }
    }

    if bestRole == "" {
        return "" // no matching group = no access
    }
    return bestRole
}
```

#### 7.3.3. User Search (for Approver Lookup)

```go
// internal/adapter/ldap/user_lookup.go

func (l *LDAPUserLookup) FindByEmployeeID(ctx context.Context, employeeID string) (*LDAPUser, error) {
    searchRequest := ldap.NewSearchRequest(
        l.baseDN,
        ldap.ScopeWholeSubtree, ldap.NeverDerefAliases, 1, 5, false,
        fmt.Sprintf("(&(objectClass=user)(employeeID=%s))", ldap.EscapeFilter(employeeID)),
        []string{"dn", "cn", "mail", "department", "title", "memberOf", "manager"},
        nil,
    )

    result, err := l.conn.Search(searchRequest)
    if err != nil || len(result.Entries) == 0 {
        return nil, ErrEmployeeNotFound
    }

    return mapEntryToUser(result.Entries[0]), nil
}
```

### 7.4. Connection Pooling

```go
// internal/adapter/ldap/pool.go

type LDAPPool struct {
    pool     chan *ldap.Conn
    config   LDAPConfig
    mu       sync.Mutex
    metrics  *LDAPMetrics
}

type LDAPConfig struct {
    URL          string
    BindDN       string
    BindPassword string
    PoolSize     int           // 5
    MaxRetries   int           // 3
    DialTimeout  time.Duration // 5s
    IdleTimeout  time.Duration // 5m
}

func NewLDAPPool(cfg LDAPConfig) (*LDAPPool, error) {
    pool := make(chan *ldap.Conn, cfg.PoolSize)
    for i := 0; i < cfg.PoolSize; i++ {
        conn, err := ldap.DialURL(cfg.URL,
            ldap.DialWithDialer(&net.Dialer{Timeout: cfg.DialTimeout}))
        if err != nil {
            return nil, fmt.Errorf("ldap dial %d: %w", i, err)
        }
        // Service account bind for searches
        if err := conn.Bind(cfg.BindDN, cfg.BindPassword); err != nil {
            return nil, fmt.Errorf("ldap bind %d: %w", i, err)
        }
        pool <- conn
    }
    return &LDAPPool{pool: pool, config: cfg}, nil
}

func (p *LDAPPool) Get(ctx context.Context) (*ldap.Conn, error) {
    select {
    case conn := <-p.pool:
        // Verify connection is alive
        if conn.IsClosing() {
            return p.reconnect()
        }
        return conn, nil
    case <-ctx.Done():
        return nil, ctx.Err()
    }
}

func (p *LDAPPool) Put(conn *ldap.Conn) {
    p.pool <- conn
}
```

### 7.5. Fallback to Cached Roles

При недоступности AD api-gateway использует кешированные роли из Redis.

```go
// internal/adapter/auth/cached_roles.go

type CachedRoleStore struct {
    redis   *redis.Client
    ttl     time.Duration // 15 minutes
}

func (s *CachedRoleStore) GetRole(ctx context.Context, username string) (string, error) {
    role, err := s.redis.Get(ctx, "auth:role:"+username).Result()
    if err == redis.Nil {
        return "", ErrRoleNotCached
    }
    return role, err
}

func (s *CachedRoleStore) SetRole(ctx context.Context, username, role string) error {
    return s.redis.Set(ctx, "auth:role:"+username, role, s.ttl).Err()
}
```

**Fallback logic:**
1. AD available -> authenticate, cache role, issue JWT
2. AD unavailable + role in cache -> issue JWT with cached role (log warning)
3. AD unavailable + no cache -> return 503 Service Unavailable

**Cache TTL:** 15 minutes. При каждом успешном логине кеш обновляется.

---

## 8. Notification Channels

Детали notification-service описаны в `phase1b_go_architecture.md`, секция 6. Здесь -- только интеграционные аспекты.

### 8.1. Telegram Bot API

| Параметр | Значение |
|----------|----------|
| API URL | `https://api.telegram.org/bot{TOKEN}/` |
| Token | Infisical: `TELEGRAM_BOT_TOKEN` |
| Methods | `sendMessage`, `editMessageText` |
| Rate limit | 30 messages/sec (Telegram limit) |
| Retry | 3x (1s, 5s, 15s) |
| Circuit breaker | 10 failures -> open -> 60s |

### 8.2. Email (SMTP)

| Параметр | Значение |
|----------|----------|
| Server | Exchange (172.20.0.176), port 587 |
| Auth | STARTTLS + SASL (service account) |
| From | `profit-system@ekf.su` |
| Retry | 3x (5s, 30s, 2min) |
| Templates | HTML (go template/html) |
| Infisical | `SMTP_USER`, `SMTP_PASSWORD` |

### 8.3. 1С Push (REST callback)

| Параметр | Значение |
|----------|----------|
| URL | `https://1c-ekf-app-01:443/EKF/hs/profit-callback/api/v1/callback/notification` |
| Auth | API key (same as callback) |
| Use case | Уведомления внутри 1С (задачи пользователю) |
| Retry | 3x (1s, 30s, 5min) |
| Fallback | Последний вариант в цепочке: Telegram -> Email -> 1С push |

---

## 9. AI Model Integration

Детали analytics-service описаны в `phase1b_go_architecture.md`, секция 4. Здесь -- только интеграционные аспекты.

### 9.1. Claude API (Anthropic)

| Параметр | Analyst (90%) | Investigator (10%) |
|----------|---------------|---------------------|
| Model | claude-sonnet-4-6-20250514 | claude-opus-4-6-20250514 |
| Timeout | 15s | 60s |
| Max tokens | 4096 | 16384 |
| Retry | 2x (2s, 10s) | 2x (5s, 30s) |
| Rate limit | 200 req/hour | 50 req/hour |
| Daily cost ceiling | $50/day total | (shared ceiling) |
| API key | Infisical: `ANTHROPIC_API_KEY` | Same |
| Prompt cache | Enabled (50% cost reduction) | Enabled |

### 9.2. AI Integration Rules

- Deterministic checks (Level 1) always run first -- no AI call needed
- AI (Level 2: Sonnet) invoked only when anomaly score > 0.7
- AI (Level 3: Opus) invoked only for investigations requiring deep analysis (>$100K impact)
- All AI calls logged to `ai_audit_log` table with cost tracking
- Daily cost check before each call: if ceiling reached, queue for next day

---

## 10. Sequence Diagrams

### 10.1. Order Created in 1С -> Profitability Calculated -> Approval -> Result in 1С

```
1С:УТ         integration-svc    Kafka           profitability-svc   workflow-svc    ELMA           1С:УТ (callback)
  |                 |               |                   |                |              |                |
  |  POST /events   |               |                   |                |              |                |
  |  order.created  |               |                   |                |              |                |
  |================>|               |                   |                |              |                |
  |  202 Accepted   |               |                   |                |              |                |
  |<================|               |                   |                |              |                |
  |                 |  outbox->Kafka |                   |                |              |                |
  |                 |  1c.order.     |                   |                |              |                |
  |                 |  created.v1   |                   |                |              |                |
  |                 |==============>|                   |                |              |                |
  |                 |               |  consume          |                |              |                |
  |                 |               |==================>|                |              |                |
  |                 |               |                   | transform,     |              |                |
  |                 |               |                   | create Shipment|              |                |
  |                 |               |                   | calculate      |              |                |
  |                 |               |                   | profitability  |              |                |
  |                 |               |                   |                |              |                |
  |                 |               |  evt.profitability|                |              |                |
  |                 |               |  .threshold.      |                |              |                |
  |                 |               |  violated.v1      |                |              |                |
  |                 |               |<==================|                |              |                |
  |                 |               |                   |                |              |                |
  |                 |               |  consume          |                |              |                |
  |                 |               |===============================>   |              |                |
  |                 |               |                   |                |              |                |
  |                 |               |                   |                | POST /tasks  |                |
  |                 |               |                   |                |=============>|                |
  |                 |               |                   |                |  task created |                |
  |                 |               |                   |                |<============ |                |
  |                 |               |                   |                |              |                |
  |                 |               |                   |                |              | (approver      |
  |                 |               |                   |                |              |  decides)      |
  |                 |               |                   |                |              |                |
  |                 |               |                   |                | callback     |                |
  |                 |               |                   |                |<============ |                |
  |                 |               |                   |                |              |                |
  |                 |               | cmd.approval.     |                |              |                |
  |                 |               | result.v1         |                |              |                |
  |                 |               |<==============================    |              |                |
  |                 |               |                   |                |              |                |
  |                 |  consume      |                   |                |              |                |
  |                 |<==============|                   |                |              |                |
  |                 |               |                   |                |              |                |
  |                 |  PUT /callback|                   |                |              |                |
  |                 |  /approval/   |                   |                |              |                |
  |                 |  {id}/result  |                   |                |              |                |
  |                 |=================================================================>|                |
  |                 |               |                   |                |              |  200 OK        |
  |                 |<================================================================ |                |
  |                 |               |                   |                |              |                |
```

### 10.2. NPSS Updated -> Cache Invalidation -> Recalculation -> Notification

```
1С:УТ         integration-svc    Kafka           profitability-svc   notification-svc
  |                 |               |                   |                |
  |  POST /events   |               |                   |                |
  |  price.npss-    |               |                   |                |
  |  updated        |               |                   |                |
  |================>|               |                   |                |
  |  202 Accepted   |               |                   |                |
  |<================|               |                   |                |
  |                 |               |                   |                |
  |                 | Update MDM    |                   |                |
  |                 | temporal table|                   |                |
  |                 | (close old,   |                   |                |
  |                 |  insert new)  |                   |                |
  |                 |               |                   |                |
  |                 | outbox->Kafka |                   |                |
  |                 | evt.integ.    |                   |                |
  |                 | price.npss-   |                   |                |
  |                 | updated.v1    |                   |                |
  |                 |==============>|                   |                |
  |                 |               |  consume          |                |
  |                 |               |==================>|                |
  |                 |               |                   |                |
  |                 |               |                   | Invalidate     |
  |                 |               |                   | price cache    |
  |                 |               |                   | (Redis)        |
  |                 |               |                   |                |
  |                 |               |                   | Find active LS |
  |                 |               |                   | with this      |
  |                 |               |                   | product_id     |
  |                 |               |                   |                |
  |                 |               |                   | Recalculate    |
  |                 |               |                   | profitability  |
  |                 |               |                   | for each       |
  |                 |               |                   | pending order  |
  |                 |               |                   |                |
  |                 |               | evt.profitability |                |
  |                 |               | .calculation.     |                |
  |                 |               | completed.v1      |                |
  |                 |               |<==================|                |
  |                 |               |                   |                |
  |                 |               |  consume          |                |
  |                 |               |===============================>   |
  |                 |               |                   |                |
  |                 |               |                   |           Notify manager
  |                 |               |                   |           (Telegram)
  |                 |               |                   |                |
```

### 10.3. ELMA Down -> Fallback -> Recovery -> Queue Drain

```
workflow-svc      ELMA         Kafka           notification-svc
    |                |            |                |
    | POST /tasks    |            |                |
    |==============> |            |                |
    |  timeout/error |            |                |
    |<============== |            |                |
    |                |            |                |
    | (failure 1..5) |            |                |
    | Circuit breaker|            |                |
    | -> OPEN        |            |                |
    |                |            |                |
    | New approval   |            |                |
    | (dev <= 5pp)   |            |                |
    | -> FALLBACK_   |            |                |
    |   AUTO_APPROVED|            |                |
    |                |            |                |
    | evt.workflow.  |            |                |
    | fallback.      |            |                |
    | activated.v1   |            |                |
    |========================>    |                |
    |                |            |  consume       |
    |                |            |==============> |
    |                |            |                | CRITICAL alert
    |                |            |                | (Telegram+Email)
    |                |            |                |
    | New approval   |            |                |
    | (dev > 5pp)    |            |                |
    | -> FALLBACK_   |            |                |
    |   QUEUED       |            |                |
    | (FIFO queue)   |            |                |
    |                |            |                |
    |    ...30 sec...|            |                |
    |                |            |                |
    | health check   |            |                |
    | GET /health    |            |                |
    |==============> |            |                |
    |  200 OK        |            |                |
    |<============== |            |                |
    |                |            |                |
    | HALF_OPEN      |            |                |
    | test request   |            |                |
    | POST /tasks    |            |                |
    |==============> |            |                |
    |  201 Created   |            |                |
    |<============== |            |                |
    |                |            |                |
    | CLOSED         |            |                |
    |                |            |                |
    | Drain queue    |            |                |
    | (P1 first,     |            |                |
    |  then P2)      |            |                |
    |                |            |                |
    | POST /tasks    |            |                |
    | (queued item 1)|            |                |
    |==============> |            |                |
    |  201 Created   |            |                |
    |<============== |            |                |
    |                |            |                |
    | POST /tasks    |            |                |
    | (queued item N)|            |                |
    |==============> |            |                |
    |  201 Created   |            |                |
    |<============== |            |                |
    |                |            |                |
    | evt.workflow.  |            |                |
    | fallback.      |            |                |
    | queue-drained  |            |                |
    | .v1            |            |                |
    |========================>    |                |
    |                |            |  consume       |
    |                |            |==============> |
    |                |            |                | Notify approvers
    |                |            |                | about fallback items
```

---

## 11. Error Handling and Retry Strategy

### 11.1. Per-Integration Error Handling

| # | Интеграция | Retry | Backoff | DLQ | Fallback |
|---|------------|-------|---------|-----|----------|
| 1-9 | 1С -> Kafka (inbound) | 100 попыток (1С retry queue) + 3 уровня (Go consumer) | Exponential (1С), 1s/30s/5min (Go) | `1c.{domain}.dlq` | Регистр сведений в 1С |
| 10-12 | Kafka -> 1С (outbound) | 3 (integration-service -> 1С REST) | 1s, 30s, 5min | `cmd.{type}.dlq` | DLQ + alert |
| 13 | ELMA | 3 (HTTP client) | 1s, 5s, 15s | N/A | Circuit breaker + fallback mode |
| 14 | WMS outbound | 3 (HTTP client) | 1s, 5s, 15s | Outbox retry | Log + retry on restore |
| 15 | WMS inbound | N/A (webhook) | N/A | N/A | WMS retries webhook delivery |
| 16 | ЦБ РФ | 3 (HTTP GET) | 1s, 5s, 15s | N/A | Cached rates (до 3 дней) |
| 17 | AD LDAP | 3 (LDAP reconnect) | 1s, 3s, 5s | N/A | Cached roles (Redis, 15 min) |

### 11.2. Error Categories

| Категория | HTTP Codes | Action | Retry |
|-----------|-----------|--------|-------|
| Client error | 400, 401, 403 | Log, не повторять | Нет |
| Not found | 404 | Log, проверить данные | Нет |
| Conflict (idempotent) | 409 | Считать успехом | Нет |
| Rate limit | 429 | Повторить через `Retry-After` | Да |
| Server error | 500 | Log, повторить | Да |
| Service unavailable | 502, 503, 504 | Log, повторить | Да |
| Network error | timeout, DNS, TLS | Log, повторить | Да |

### 11.3. Dead Letter Queue (DLQ) Processing

Сообщения в DLQ содержат дополнительные заголовки:

| Header | Описание |
|--------|----------|
| `X-Original-Topic` | Исходный топик |
| `X-Error-Message` | Текст последней ошибки |
| `X-Retry-Count` | Количество попыток |
| `X-Failed-At` | Время последней ошибки (RFC 3339) |
| `X-Original-Timestamp` | Время исходного сообщения |

**DLQ dashboard (Grafana):** Количество сообщений в DLQ по топикам, скорость поступления, возраст самого старого сообщения.

**Manual reprocessing:** Администратор может переместить сообщения из DLQ обратно в исходный топик через admin CLI.

```bash
# Reprocess all messages from DLQ
kafka-console-consumer --bootstrap-server kafka:9092 \
  --topic 1c.order.dlq --from-beginning \
  | kafka-console-producer --bootstrap-server kafka:9092 \
  --topic 1c.order.created.v1
```

---

## 12. Monitoring and Alerting

### 12.1. Per-Integration Monitoring

| # | Интеграция | Metrics | Alert Condition | Alert Channel | Severity |
|---|------------|---------|-----------------|---------------|----------|
| 1-9 | 1С -> Kafka | `integration_1c_events_total{type,status}`, `integration_1c_event_lag_seconds`, `integration_1c_retry_queue_size` | retry_queue > 100 OR lag > 5min | Telegram + Email | HIGH |
| 10-12 | Kafka -> 1С | `integration_callback_total{type,status}`, `integration_callback_duration_seconds`, `integration_callback_dlq_size` | dlq_size > 0 OR error_rate > 5% | Telegram + Email | HIGH |
| 13 | ELMA | `elma_requests_total{status}`, `elma_circuit_breaker_state`, `elma_fallback_queue_size` | circuit_breaker=open > 5min OR queue > 20 | Telegram + Email | CRITICAL |
| 14-15 | WMS | `wms_outbound_total{status}`, `wms_inbound_total{status}`, `wms_circuit_breaker_state` | error_rate > 10% | Telegram | HIGH |
| 16 | ЦБ РФ | `cbr_fetch_total{status}`, `cbr_rate_age_hours`, `cbr_trigger_total{currency}` | rate_age > 72h (3 дня) | Telegram + Email | MEDIUM |
| 17 | AD LDAP | `ldap_auth_total{result}`, `ldap_search_duration_seconds`, `ldap_pool_available`, `ldap_fallback_cache_used` | pool_available=0 OR fallback_used > 10/min | Telegram | HIGH |

### 12.2. Kafka Lag Monitoring

| Consumer Group | Expected Lag | Alert Threshold |
|----------------|-------------|-----------------|
| `integration-1c-consumer` | < 10 messages | > 100 messages or > 5 min |
| `profitability-consumer` | < 50 messages | > 500 messages or > 10 min |
| `workflow-consumer` | < 50 messages | > 500 messages or > 10 min |
| `analytics-consumer` | < 100 messages | > 1000 messages or > 30 min |
| `notification-consumer` | < 50 messages | > 500 messages or > 10 min |
| `callback-1c-consumer` | < 10 messages | > 50 messages or > 5 min |

### 12.3. Health Check Endpoints

Каждый сервис предоставляет `GET /health` и `GET /ready`, проверяющие подключения ко всем зависимым системам (см. phase1b, секции 2-7, Dependencies).

| Service | Health checks |
|---------|---------------|
| integration-service | PostgreSQL, Kafka (consumer + producer), CBR (cached rate freshness) |
| workflow-service | PostgreSQL, Kafka, ELMA (circuit breaker state), Redis |
| profitability-service | PostgreSQL, Kafka, Redis |
| analytics-service | PostgreSQL, Kafka, Claude API (rate limit status) |
| notification-service | PostgreSQL, Kafka, Telegram API, SMTP |
| api-gateway | LDAP (pool), Redis, all downstream services (gRPC) |

### 12.4. Alerting Escalation

| Severity | Response Time | Notification | Escalation |
|----------|--------------|--------------|------------|
| CRITICAL | < 5 min | Telegram + Email + 1С задача | -> ДП через 15 мин |
| HIGH | < 30 min | Telegram + Email | -> Тимлид через 1 час |
| MEDIUM | < 4 hours | Telegram | N/A |
| LOW | Next business day | Daily digest (email) | N/A |

### 12.5. Grafana Dashboards

| Dashboard | Panels | Refresh |
|-----------|--------|---------|
| Integration Overview | All 17 integrations status, error rates, latency | 30s |
| Kafka Health | Consumer lag, topic throughput, partition skew | 10s |
| ELMA Circuit Breaker | State timeline, fallback queue, auto-approved count | 10s |
| 1С Pipeline | Event flow rate, retry queue size, DLQ depth | 30s |
| AD/Auth | Login success rate, LDAP latency, cache hit ratio | 60s |

---

## Appendix A. Integration Checklist

**Coverage verification (17/17):**

- [x] 1. Заказ создан (1С -> Go) -- секция 2.6.1
- [x] 2. Заказ изменен (1С -> Go) -- секция 2.6.1
- [x] 3. Отгрузка проведена (1С -> Go) -- секция 2.6.2
- [x] 4. Возврат товаров (1С -> Go) -- секция 2.6.3
- [x] 5. НПСС обновлена (1С -> Go) -- секция 2.6.4
- [x] 6. Закупочная цена изменена (1С -> Go) -- секция 2.6.5
- [x] 7. Контрагент обновлен (1С -> Go) -- секция 2.6.6
- [x] 8. ЛС создана (1С -> Go) -- секция 2.6.7
- [x] 9. План ЛС изменен (1С -> Go) -- секция 2.6.8
- [x] 10. Результат согласования (Go -> 1С) -- секция 3.2.1
- [x] 11. Санкция применена (Go -> 1С) -- секция 3.2.2
- [x] 12. Блокировка отгрузки (Go -> 1С) -- секция 3.2.3
- [x] 13. ELMA согласование (Go <-> ELMA) -- секция 4
- [x] 14. WMS разрешение отгрузки (Go -> WMS) -- секция 6.2
- [x] 15. WMS факт отгрузки (WMS -> Go) -- секция 6.3
- [x] 16. Курсы ЦБ РФ (ЦБ -> Go) -- секция 5
- [x] 17. AD аутентификация (Go <-> AD) -- секция 7

**Cross-reference with phase1b Kafka Topic Catalog (section 9):**

- 9 inbound topics (1c.*.v1) -- all covered with JSON schemas (секция 2.6)
- 3 outbound topics (cmd.*.v1) -- all covered with REST callback specs (секция 3.2)
- 24 internal event topics (evt.*.v1) -- defined in phase1b, not duplicated here
- 8 DLQ topics -- covered in error handling (секция 11)

---

## Appendix B. Configuration Reference

| Setting | Service | Default | Infisical Key |
|---------|---------|---------|---------------|
| 1С API key (inbound) | integration | - | `INTEGRATION_1C_API_KEY` |
| 1С API key (outbound callback) | integration | - | `CALLBACK_1C_API_KEY` |
| 1С callback base URL | integration | - | `CALLBACK_1C_URL` |
| ELMA API key | workflow | - | `ELMA_API_KEY` |
| ELMA base URL | workflow | `https://elma.ekf.su` | `ELMA_BASE_URL` |
| WMS outbound URL | integration | - | `WMS_API_URL` |
| WMS webhook secret | integration | - | `WMS_WEBHOOK_SECRET` |
| LDAP URL | api-gateway | - | `LDAP_URL` |
| LDAP bind password | api-gateway | - | `LDAP_BIND_PASSWORD` |
| Anthropic API key | analytics | - | `ANTHROPIC_API_KEY` |
| Telegram bot token | notification | - | `TELEGRAM_BOT_TOKEN` |
| SMTP credentials | notification | - | `SMTP_USER`, `SMTP_PASSWORD` |

All secrets managed via Infisical (Universal Auth). Rotation policy: monthly for API keys, quarterly for LDAP service account.

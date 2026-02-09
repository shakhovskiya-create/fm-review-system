# Camunda Cloud - пробная интеграция

Конвертация JSON-описаний BPMN-процессов в стандартный BPMN 2.0 XML
и рендер в PNG. Опциональный деплой в Camunda Cloud (Zeebe).

## Статус

| Компонент | Статус |
|-----------|--------|
| JSON -> BPMN 2.0 XML | Работает (13/13 процессов) |
| BPMN -> PNG рендер | Работает (13/13 PNG) |
| Camunda OAuth | Работает |
| Zeebe топология | Работает (3 брокера) |
| Zeebe деплой | HTTP 403 - требуется настройка Identity |

## Быстрый старт

```bash
# Установить зависимости
cd scripts/experimental/camunda
npm install

# Конвертировать все JSON -> BPMN
node json_to_bpmn.js --all

# Рендер BPMN -> PNG
node render_png.js --all

# Или все сразу
bash run_trial.sh
```

PNG файлы появятся в `output/`.

## Деплой в Camunda Cloud

```bash
# Переменные окружения
export ZEEBE_CLIENT_ID='...'
export ZEEBE_CLIENT_SECRET='...'
export CAMUNDA_CLUSTER_ID='...'
export CAMUNDA_CLUSTER_REGION='dsm-1'

# Деплой всех BPMN
python3 camunda_client.py deploy

# Деплой одного файла
python3 camunda_client.py deploy output/process-1-rentability.bpmn
```

### Проблема 403 при деплое

Деплой возвращает `FORBIDDEN: Insufficient permissions to perform operation 'CREATE' on resource 'RESOURCE'`.

**Причина:** API-клиент имеет scope `Zeebe` в Console, но не имеет авторизации на CREATE в Identity.

**Решение:**
1. Открыть Camunda Console -> Organization -> API
2. Найти API-клиента (или создать нового)
3. Нажать "Configure authorizations in Identity"
4. Добавить авторизацию: Resource = `deployment`, Permission = `CREATE`
5. Или назначить роль `Zeebe` с полными правами

## Файлы

| Файл | Описание |
|------|----------|
| `json_to_bpmn.js` | JSON (наш формат) -> BPMN 2.0 XML |
| `render_png.js` | BPMN XML -> PNG (через bpmn-to-image) |
| `camunda_client.py` | OAuth + Console API + Zeebe API (деплой) |
| `run_trial.sh` | Полный пайплайн: install -> auth -> convert -> render |
| `package.json` | Зависимости (bpmn-to-image) |
| `output/` | Сгенерированные BPMN и PNG файлы |

## 13 процессов

| # | Файл | Процесс |
|---|------|---------|
| 0 | process-0-overview | Общая обзорная схема |
| 1 | process-1-rentability | Контроль рентабельности |
| 2 | process-2-approval | Согласование |
| 3 | process-3-emergency | Экстренное согласование |
| 4 | process-4-order-lifecycle | Жизненный цикл Заказа |
| 5 | process-5-ls-lifecycle | Жизненный цикл ЛС |
| 6 | process-6-wms-integration | Интеграция с WMS |
| 7 | process-7-return | Возврат товара |
| 8 | process-8-ls-closing | Закрытие ЛС |
| 9 | process-9-npss-control | Контроль возраста НПСС |
| 10 | process-10-profitability-change | Изменение плановой рентабельности |
| 11 | process-11-demand-fixation | Фиксация потребности (Этап 2) |
| 12 | process-12-sanctions | Санкции за невыкуп (Этап 2) |

## Техническое

- BPMN 2.0 XML совместим с Camunda 8 (Zeebe): conditionExpression, default flows, errorRef
- Ортогональная маршрутизация стрелок (горизонтально-вертикально-горизонтально)
- Автоматическая раскладка BFS (слева направо по уровням)
- Кириллица в ID транслитерируется в латиницу (требование NCName)
- bpmn-to-image использует Puppeteer для рендера (нужен Chrome/Chromium)

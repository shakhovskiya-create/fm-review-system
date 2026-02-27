# Выбор моделей для агентов

> Обоснование выбора моделей для каждого субагента системы.

---

## Текущее распределение

### FM Review Phase

| Агент | Модель | Обоснование |
|-------|--------|-------------|
| Agent 0 (Creator) | `opus` | Создание ФМ требует глубокого понимания бизнес-процессов, интервью, структурирования |
| Agent 1 (Architect+Defender) | `opus` | Критический агент: аудит + defense mode (A-I классификация). Два прохода в pipeline |
| Agent 2 (Simulator) | `sonnet` | Симуляция ролей — структурированная задача по чеклисту |
| Agent 5 (Tech Architect) | `opus` | Проектирование архитектуры 1С: сложные решения, ТЗ, ARC-документы |
| Agent 7 (Publisher) | `opus` | Работа с Confluence API + стилизация XHTML. Критический для публикации |
| Agent 8 (BPMN Designer) | `sonnet` | Генерация drawio-диаграмм — структурированная задача |
| Agent 9 (SE Go+React) | `opus` | Senior Engineer ревью — глубокий анализ кода и архитектуры |
| Agent 10 (SE 1С) | `opus` | Senior Engineer ревью — глубокий анализ 1С расширений |
| Agent 15 (Trainer) | `sonnet` | Генерация документации — структурированная задача |

### Development Phase (on demand)

| Агент | Модель | Обоснование |
|-------|--------|-------------|
| Agent 11 (Dev 1С) | `opus` | Кодогенерация 1С — сложная задача, BSL стандарты, ITS 455 |
| Agent 12 (Dev Go+React) | `opus` | Кодогенерация Go+React — Clean Architecture, OpenAPI |
| Agent 13 (QA 1С) | `sonnet` | Генерация тестов YAxUnit/Vanessa — структурированная задача |
| Agent 14 (QA Go+React) | `sonnet` | Генерация тестов Go/React — структурированная задача |

### DEPRECATED

| Агент | Причина |
|-------|---------|
| ~~Agent 3 (Defender)~~ | Merged into Agent 1 (defense mode) |
| ~~Agent 4 (QA Tester)~~ | Replaced by Agent 13 (QA 1С) + Agent 14 (QA Go) |
| ~~Agent 6 (Presenter)~~ | Replaced by Agent 15 (Trainer) |

## Принцип выбора

```
opus  → Глубокий анализ, принятие решений, творческие задачи
sonnet → Структурированные задачи, форматирование, API-операции
haiku  → Не используется (субагенты требуют контекст ФМ)
```

**Правило:** Агенты с `disallowedTools: Write, Edit` (read-only) могут быть переведены на `sonnet` для экономии, если качество не падает.

## Когда менять модель

- **Повысить до opus:** агент регулярно пропускает проблемы или генерирует поверхностные результаты
- **Понизить до sonnet:** задача агента стала более шаблонной, качество не страдает
- **haiku:** только для вспомогательных одноразовых запросов (не для субагентов с полным контекстом ФМ)

## Бюджеты на агент (config/pipeline.json)

Каждый агент имеет `budget_usd` — максимальный расход на один запуск. Определено в `AGENT_REGISTRY` (`config/pipeline.json`).

| Агент | Модель | Бюджет | Обоснование |
|-------|--------|--------|-------------|
| Agent 0 (Creator) | opus | $8 | Длинное интервью, генерация ФМ |
| Agent 1 (Architect+Defender) | opus | $12 | Аудит + defense mode (два прохода) |
| Agent 2 (Simulator) | sonnet | $6 | Симуляция 3-5 ролей |
| Agent 5 (Tech Architect) | opus | $10 | Полный ТЗ с архитектурой |
| Agent 7 (Publisher) | opus | $6 | Публикация в Confluence |
| Agent 8 (BPMN Designer) | sonnet | $3 | Генерация drawio |
| Agent 9 (SE Go) | opus | $10 | SE ревью Go+React (conditional) |
| Agent 10 (SE 1С) | opus | $10 | SE ревью 1С (conditional) |
| Agent 11 (Dev 1С) | opus | $10 | Кодогенерация 1С (dev phase) |
| Agent 12 (Dev Go) | opus | $10 | Кодогенерация Go+React (dev phase) |
| Agent 13 (QA 1С) | sonnet | $5 | Тесты 1С (dev phase) |
| Agent 14 (QA Go) | sonnet | $5 | Тесты Go+React (dev phase) |
| Agent 15 (Trainer) | sonnet | $5 | Документация и обучение |

### Pipeline budgets (три режима)

| Режим | Стоимость | Порядок |
|-------|-----------|---------|
| Quick | ~$25 | 1 → 5 → 7 |
| Standard | ~$35 | 1(audit) → 2 → 1(defense) → 5 → [9\|10] → QG → 7 → [8, 15] |
| Full (+ dev) | ~$55 | Standard + [11\|12] → [13\|14] → 7 |

**Pipeline budget:** $70 (запас для полного цикла с dev). При превышении пайплайн останавливается.

**Override:** `--max-budget 15.0` переопределяет бюджет для всех агентов. `--model opus` форсирует opus для всех, игнорируя per-agent модели.

## Стоимость

| Модель | Относительная стоимость | Скорость |
|--------|------------------------|----------|
| opus | Базовая (1x) | Медленная |
| sonnet | ~0.3x | Быстрая |
| haiku | ~0.05x | Очень быстрая |

Текущее соотношение: 7 opus + 6 sonnet (15 агентов, 2 фазы). Standard прогон: ~$35 (зависит от размера ФМ).

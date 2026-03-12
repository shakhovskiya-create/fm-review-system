# Review Findings Enforcement — обязательное правило

## Принцип

**ВСЕ замечания от ревью (Agent 9 SE, OpenAI GPT-5.4, Qodo bot, любой reviewer) ДОЛЖНЫ быть исправлены в текущем спринте.**

Нельзя:
- Откладывать как "заметка на будущее"
- Маркировать "accepted as note"
- Переносить в следующий спринт как tech debt
- Игнорировать LOW/MEDIUM findings

## Единственные исключения

1. **False positive** — замечание ошибочно (нет бага). Требует аргументации
2. **Out of scope** — замечание к коду, который не менялся в этом спринте. Создать отдельную задачу
3. **Архитектурное решение** — reviewer не знает контекст. Объяснить почему так сделано

## Workflow

1. Код написан → PR создан → CI green
2. Agent 9 SE review → findings → **FIX ALL** → Agent 9 re-review → PASS
3. OpenAI review → findings → Agent 9 оценивает → **FIX accepted** → PASS
4. Bot reviews (Qodo и др.) → **проверить ВСЕ комментарии** → FIX real bugs
5. **Только после 0 unaddressed findings** → Sprint Completion Protocol
6. **Согласовать с пользователем** перед закрытием спринта

## Guard Hook

`guard-sprint-close.sh` + `sprint-completion.sh` проверяют:
- Наличие файлов ревью для текущего спринта
- Отсутствие unresolved findings (через `review-findings-check.sh`)

## Ответственность

Оркестратор обязан:
1. Запустить ОБА цикла ревью (Agent 9 + OpenAI)
2. Проверить ВСЕ bot reviews на PR
3. Убедиться что ВСЕ findings обработаны (fix или обоснованный reject)
4. **СПРОСИТЬ пользователя** перед закрытием спринта: "Все замечания исправлены, можно закрывать?"

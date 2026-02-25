---
globs: scripts/gh-tasks.sh, .claude/agents/**
---

# Definition of Done (DoD) — Universal Checklist

Every GitHub Issue closed by an agent or orchestrator MUST satisfy this DoD.
Agents include DoD checklist in the closing comment (`gh-tasks.sh done <N> --comment "..."`).

## 8 обязательных пунктов

### Auto-enforced (проверяются хуками/скриптами):

1. **Tests pass** — `pytest tests/ -x -q` returns 0 failures (если менялся код/скрипты)
2. **_summary.json** — создан по схеме `schemas/agent-contracts.json` (для агентов 0-8)
3. **No regression** — существующие тесты не сломаны новыми изменениями
4. **CI green** — если был push, GitHub Actions зелёный (`gh run watch --exit-status`)

### Self-reported (заполняются агентом в closing comment):

5. **AC met** — все Acceptance Criteria из issue body выполнены
6. **Artifacts listed** — перечислены созданные/изменённые файлы или Confluence-страницы
7. **Docs updated** — документация обновлена (или "N/A" если не затронута)
8. **No hidden debt** — нет скрытого техдолга (или явно указан как TODO с issue)

### Conditional (применяются по контексту):

- **Confluence verified** — если менялась ФМ: GET подтвердил изменения (COMMON_RULES правило 9)
- **Smoke test** — если менялась инфраструктура: скрипты запущены, exit 0 (правило 24)

## Шаблон closing comment

```markdown
## Результат
[Кратко что сделано, 1-3 строки]

## Было -> Стало
- [Конкретное изменение]

## DoD
- [x] Tests pass
- [x] No regression
- [x] AC met
- [x] Artifacts: [файлы/страницы]
- [x] Docs updated (или N/A)
- [x] No hidden debt
```

## Шаблон creation comment (--body)

```markdown
## Образ результата
[Что конкретно должно появиться/измениться]

## Acceptance Criteria
- [ ] AC1: конкретный критерий
- [ ] AC2: конкретный критерий

## Scope
Файлы: [список затрагиваемых файлов]
```

## Artifact cross-check (автоматический)

При `gh-tasks.sh done` скрипт сверяет `git diff HEAD~1 --name-only` с текстом `--comment`.
Если файлы из diff не упомянуты в комментарии — выводит WARNING со списком пропущенных.
Это не блокирует закрытие, но напоминает агенту перечислить все артефакты.

## Anti-patterns (НЕ делать)

- "Всё сделано" без деталей — бесполезный комментарий
- Закрытие без `--comment` — скрипт не позволит (exit 1)
- DoD без конкретных артефактов — "Artifacts: да" вместо списка файлов
- Пропуск пунктов DoD без объяснения — если пункт N/A, написать почему
- Checkbox-ticking: проставить все [x] без реальной проверки — cross-check ловит это

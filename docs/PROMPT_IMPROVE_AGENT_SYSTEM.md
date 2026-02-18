# Промпт: Улучшение мультиагентной системы на Claude Code

> Универсальный промпт для применения 5 проверенных улучшений к любой системе
> из нескольких AI-агентов, работающих через Claude Code CLI.
>
> Источник: опыт проекта FM Review System (9 агентов, Confluence, 1С).
> Дата обновления: 18.02.2026

---

## Как использовать

Скопируй весь текст ниже (начиная с "---НАЧАЛО ПРОМПТА---") и вставь в новый чат Claude Code в рабочей директории целевого проекта. Claude прочитает структуру проекта и предложит план реализации каждого шага.

---

## ---НАЧАЛО ПРОМПТА---

Я хочу применить 5 системных улучшений к моей мультиагентной системе на Claude Code. Каждое улучшение проверено на практике. Реализуй их последовательно, от простого к сложному.

Перед началом - изучи структуру моего проекта (прочитай README, CLAUDE.md, файлы агентов, скрипты запуска). Затем адаптируй каждый шаг под мою конкретную структуру.

**Правило моделей: ВСЕГДА используй последнюю версию каждой модели Claude.**
На момент создания этого промпта (февраль 2026):
- Opus: `claude-opus-4-6`
- Sonnet: `claude-sonnet-4-6`

Если к моменту запуска вышли новые версии - используй их. Проверь актуальные model ID на https://docs.anthropic.com/en/docs/about-claude/models

---

### ШАГ 1: Adaptive Thinking - оптимизация моделей по агентам (~30 мин)

**Суть:** Не все агенты требуют самую дорогую модель. Подбираем модель под задачу.

**Что сделать:**

1. Составь таблицу всех агентов с колонками: Агент | Текущая модель | Тип задачи | Рекомендуемая модель | Обоснование

2. Критерии выбора модели (два уровня):
   - **Opus** - задачи, требующие глубокого аналитического мышления: поиск противоречий в документах, сложная архитектура, создание контента с нуля из интервью, принятие неочевидных решений
   - **Sonnet** - структурированные задачи: генерация по шаблонам, классификация, стандартные сценарии, форматирование, CRUD-операции с API, публикация, простые преобразования

3. Для каждого агента, который нужно переключить:
   - Если агенты определены в `.claude/agents/*.md` - измени поле `model:` в YAML frontmatter
   - Если агенты запускаются скриптом - измени параметр модели в скрипте запуска
   - Если модель передается через CLI - обнови значение по умолчанию

4. Посчитай экономию:
   ```
   Стоимость за 1M токенов:
   Opus:   $15 input, $75 output
   Sonnet: $3 input,  $15 output (в 5 раз дешевле)
   ```

**Результат:** Таблица моделей по агентам, обновленные конфиги, расчет экономии.

---

### ШАГ 2: Дедупликация агентов - единый источник правил (~1-2 часа)

**Суть:** Общие правила для всех агентов выносятся в один файл. Агенты ссылаются на него вместо копирования.

**Что сделать:**

1. Прочитай ВСЕ файлы агентов. Найди секции, которые повторяются в 3+ файлах:
   - Правила форматирования текста
   - Структура проекта
   - Правила сохранения результатов
   - Формат выходных данных
   - Правила работы с внешними системами (API, базы, хранилища)
   - Протокол взаимодействия с пользователем

2. Создай файл `agents/COMMON_RULES.md` (или аналогичный):
   - Каждое правило - отдельная пронумерованная секция (## 1. Название)
   - Формулировки - точные копии из агентов (не переписывай, перенеси)
   - В начале файла - оглавление

3. В каждом файле агента замени дублирующиеся секции на ссылку:
   ```markdown
   > См. COMMON_RULES.md, правило N - [название правила]
   ```
   Если у агента есть УТОЧНЕНИЕ к общему правилу - оставь уточнение после ссылки.

4. Проверь:
   - Уникальные инструкции каждого агента СОХРАНЕНЫ (не затерты)
   - Каждый агент при старте читает COMMON_RULES.md
   - Если есть CLAUDE.md - обнови секцию структуры, добавь COMMON_RULES.md

**Результат:** COMMON_RULES.md + облегченные файлы агентов. Одно место для обновления правил.

---

### ШАГ 3: GitHub Actions - автоматический PR review (~1-2 часа)

**Суть:** Каждый PR автоматически проверяется Claude на соответствие стандартам проекта.

**Что сделать:**

1. Создай `.github/workflows/claude.yml`:

```yaml
name: Claude Code

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]
    paths:
      # АДАПТИРУЙ: укажи пути к файлам, которые важно ревьюить
      - "agents/**"
      - "scripts/**"
      - "docs/**"
      - "CLAUDE.md"

  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  auto-review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      pull-requests: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          use_sticky_comment: true
          track_progress: true
          prompt: |
            # АДАПТИРУЙ: опиши свою систему и правила ревью
            Ты ревьюер для [НАЗВАНИЕ СИСТЕМЫ].
            Проверь PR по стандартам из CLAUDE.md.
            Обрати внимание на:
            1. [ПРАВИЛО 1 - например: формат файлов агентов]
            2. [ПРАВИЛО 2 - например: нет захардкоженных секретов]
            3. [ПРАВИЛО 3 - например: соответствие API контрактам]
            Используй inline comments для замечаний.

          claude_args: |
            --model claude-sonnet-4-6
            --max-turns 10
            --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*),Read,Glob,Grep"

  interactive:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude'))
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          use_sticky_comment: false
          claude_args: |
            --model claude-sonnet-4-6
            --max-turns 15
```

2. Добавь `ANTHROPIC_API_KEY` в GitHub Secrets:
   - Settings -> Secrets and variables -> Actions -> New repository secret

3. PAT для пуша workflow файла должен иметь scope `workflow`

**Два режима:**
- `auto-review` - автоматически на каждый PR (только читает)
- `interactive` - по команде `@claude` в комментариях (может вносить правки)

**Стоимость:** ~$0.50-2.00 за PR (Sonnet). ~$20/мес при 5 PR/неделю.

---

### ШАГ 4: Langfuse - отслеживание стоимости и использования (~2-4 часа)

**Суть:** Каждая сессия Claude Code автоматически отправляет метрики (токены, стоимость, инструменты) в Langfuse для аналитики.

**Архитектура:**
```
Claude Code сессия завершается
  -> Stop hook (.claude/hooks/langfuse-trace.sh)
    -> Python tracer (scripts/lib/langfuse_tracer.py)
      -> Langfuse API (Cloud или self-hosted)
```

**Что сделать:**

#### 4.1. Выбери вариант Langfuse:

**Вариант A: Langfuse Cloud (быстрый старт, бесплатно до 50k событий/мес)**
- Зарегистрируйся на https://cloud.langfuse.com
- Создай проект, получи API ключи (pk-lf-..., sk-lf-...)

**Вариант B: Self-hosted (полный контроль, нужен сервер с 16 GB RAM)**
- Создай `infra/langfuse/docker-compose.yml` с сервисами:
  - langfuse-web (image: langfuse/langfuse:3, port 3000)
  - langfuse-worker (image: langfuse/langfuse-worker:3)
  - postgres (image: postgres:17, 2 GB RAM)
  - clickhouse (image: clickhouse/clickhouse-server:24, 4 GB RAM)
  - redis (image: redis:7, 512 MB RAM)
  - minio (image: minio/minio, 512 MB RAM, для S3 event storage)
- Создай `.env.langfuse` с секретами (ENCRYPTION_KEY, NEXTAUTH_SECRET, SALT, пароли)
- `docker compose up -d`

#### 4.2. Создай tracer скрипт `scripts/lib/langfuse_tracer.py`:

```python
#!/usr/bin/env python3
"""
Langfuse tracer: парсит JSONL транскрипт Claude Code,
отправляет метрики (токены, стоимость, инструменты) в Langfuse.
Вызывается из Stop hook. Использует Langfuse SDK v3.
"""
import json, os, re, sys
from pathlib import Path
from dataclasses import dataclass, field

# АДАПТИРУЙ: актуальные цены моделей (проверь docs.anthropic.com/en/docs/about-claude/models)
MODEL_PRICING = {
    "claude-opus-4-6":   {"input": 15.0, "output": 75.0, "cache_creation": 18.75, "cache_read": 1.50},
    "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0, "cache_creation": 3.75,  "cache_read": 0.30},
}
DEFAULT_PRICING = {"input": 3.0, "output": 15.0, "cache_creation": 3.75, "cache_read": 0.30}

# АДАПТИРУЙ: имена твоих агентов
AGENT_PATTERNS = {
    # regex паттерн в транскрипте -> (agent_id, agent_name)
    r"AGENT_(\d+)_(\w+)": lambda m: (int(m.group(1)), m.group(2)),
}

@dataclass
class SessionStats:
    session_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    tool_calls: dict = field(default_factory=dict)
    turn_count: int = 0
    agent_name: str = "interactive"

def parse_transcript(path: str, start_offset: int = 0):
    """Парсит JSONL транскрипт Claude Code. Дедупликация по message.id."""
    stats = SessionStats()
    seen_ids = set()
    line_count = 0

    with open(path) as f:
        for i, line in enumerate(f):
            line_count = i + 1
            if i < start_offset:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            if entry.get("type") != "assistant" or msg.get("role") != "assistant":
                continue

            # Дедупликация (стриминг создает дубли с одним message.id)
            msg_id = msg.get("id", "")
            if msg_id in seen_ids:
                continue
            if msg_id:
                seen_ids.add(msg_id)

            # Модель
            if msg.get("model"):
                stats.model = msg["model"]

            # Токены
            usage = msg.get("usage", {})
            if usage.get("input_tokens", 0) > 0:
                stats.input_tokens += usage.get("input_tokens", 0)
                stats.output_tokens += usage.get("output_tokens", 0)
                stats.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                stats.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                stats.turn_count += 1

            # Инструменты
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool = block.get("name", "unknown")
                        stats.tool_calls[tool] = stats.tool_calls.get(tool, 0) + 1

    return stats, line_count

def calculate_cost(stats):
    pricing = MODEL_PRICING.get(stats.model, DEFAULT_PRICING)
    return round(
        stats.input_tokens * pricing["input"] / 1e6
        + stats.output_tokens * pricing["output"] / 1e6
        + stats.cache_creation_tokens * pricing["cache_creation"] / 1e6
        + stats.cache_read_tokens * pricing["cache_read"] / 1e6,
        6
    )

def detect_agent(path):
    """Определяет агента по содержимому транскрипта."""
    try:
        with open(path) as f:
            sample = f.read(50_000)
    except OSError:
        return "interactive"
    for pattern, extractor in AGENT_PATTERNS.items():
        m = re.search(pattern, sample)
        if m:
            _, name = extractor(m)
            return name
    return "interactive"

def send_to_langfuse(stats, cost, session_id):
    """Отправка в Langfuse SDK v3. API v3: get_client() + start_span() + update_trace()."""
    from langfuse import get_client

    langfuse = get_client()  # Читает LANGFUSE_* из env

    trace_name = stats.agent_name
    root = langfuse.start_span(name=trace_name)
    root.update_trace(
        name=trace_name,
        session_id=session_id,
        metadata={
            "model": stats.model,
            "turns": stats.turn_count,
            "tools": stats.tool_calls,
            "cost_usd": cost,
        },
        tags=[f"agent:{stats.agent_name}", f"model:{stats.model}"],
    )

    pricing = MODEL_PRICING.get(stats.model, DEFAULT_PRICING)
    gen = root.start_generation(
        name="session",
        model=stats.model,
        usage_details={
            "input": stats.input_tokens,
            "output": stats.output_tokens,
            "cache_creation_input_tokens": stats.cache_creation_tokens,
            "cache_read_input_tokens": stats.cache_read_tokens,
        },
        cost_details={
            "input": stats.input_tokens * pricing["input"] / 1e6,
            "output": stats.output_tokens * pricing["output"] / 1e6,
        },
        metadata={"cost_usd": cost},
    )
    gen.end()

    for tool, count in stats.tool_calls.items():
        tool_span = root.start_span(name=f"tool:{tool}", metadata={"calls": count})
        tool_span.end()

    root.end()
    langfuse.flush()

# --- Инкрементальный offset (не парсить транскрипт заново) ---
STATE_DIR = Path(__file__).resolve().parent.parent / ".langfuse_state"

def get_offset(path):
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / (Path(path).stem + ".offset")
    return int(state_file.read_text()) if state_file.exists() else 0

def save_offset(path, offset):
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / (Path(path).stem + ".offset")).write_text(str(offset))

def main():
    try:
        data = json.loads(sys.stdin.read())
        session_id = data.get("session_id", "")
        transcript = data.get("transcript_path", "")

        if not transcript or not Path(transcript).exists():
            sys.exit(0)
        if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
            sys.exit(0)

        # SDK v3 использует LANGFUSE_HOST, не LANGFUSE_BASE_URL
        if not os.environ.get("LANGFUSE_HOST") and os.environ.get("LANGFUSE_BASE_URL"):
            os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

        offset = get_offset(transcript)
        stats, new_offset = parse_transcript(transcript, offset)

        if stats.turn_count == 0:
            save_offset(transcript, new_offset)
            sys.exit(0)

        stats.agent_name = detect_agent(transcript)
        stats.session_id = session_id
        cost = calculate_cost(stats)
        send_to_langfuse(stats, cost, session_id)
        save_offset(transcript, new_offset)
    except Exception:
        sys.exit(0)  # Никогда не блокировать Claude Code

if __name__ == "__main__":
    main()
```

#### 4.3. Создай hook обертку `.claude/hooks/langfuse-trace.sh`:

```bash
#!/bin/bash
INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PYTHON="${PROJECT_DIR}/.venv/bin/python3"
TRACER="${PROJECT_DIR}/scripts/lib/langfuse_tracer.py"

[ -f "$TRACER" ] || exit 0
[ -f "${PROJECT_DIR}/.env" ] && set -a && source "${PROJECT_DIR}/.env" && set +a
[ -z "$LANGFUSE_PUBLIC_KEY" ] && exit 0

echo "$INPUT" | "$PYTHON" "$TRACER" &>/dev/null &
disown
exit 0
```

Сделай исполняемым: `chmod +x .claude/hooks/langfuse-trace.sh`

#### 4.4. Зарегистрируй hook в `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/langfuse-trace.sh",
        "timeout": 5
      }
    ]
  }
}
```

#### 4.5. Добавь переменные в `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
# ВАЖНО: SDK v3 использует LANGFUSE_HOST (НЕ LANGFUSE_BASE_URL)
LANGFUSE_HOST=https://cloud.langfuse.com  # или http://localhost:3000
```

#### 4.6. Установи зависимость:

```bash
pip install langfuse>=3.0.0
```

#### 4.7. Добавь в .gitignore:

```
# Langfuse
scripts/.langfuse_state/
infra/langfuse/.env.langfuse
```

**Ключевые решения:**
- Hook запускает tracer в фоне (`& disown`) - не блокирует Claude Code (таймаут hook = 5 секунд)
- Langfuse SDK v3: `get_client()` + `start_span()` + `update_trace()` + `start_generation()`, все с `.end()`
- Дедупликация по message.id - Claude Code стримит ответы, один message.id появляется в JSONL несколько раз
- Инкрементальный парсинг с offset - не перечитывать весь транскрипт каждый раз
- При любой ошибке - тихий выход (sys.exit(0)), никогда не ломать сессию Claude Code

---

### ШАГ 5: Параллельный запуск агентов (~1-2 часа)

**Суть:** Агенты, не зависящие друг от друга, запускаются одновременно через ThreadPoolExecutor.

**Что сделать:**

#### 5.1. Определи граф зависимостей агентов:

Для каждого агента ответь: "Какие результаты других агентов он ЧИТАЕТ?"

Пример:
```
Agent 1: нет зависимостей (читает исходные данные)
Agent 2: читает результаты Agent 1
Agent 4: читает результаты Agent 1
Agent 5: читает результаты Agent 1 + 2 + 4
```

Из этого вытекают параллельные стадии:
```
Stage 1: [Agent 1]           - один, база для всех
Stage 2: [Agent 2, Agent 4]  - параллельно, оба зависят только от Agent 1
Stage 3: [Agent 5]           - один, зависит от 1+2+4
```

**Критерий параллельности:** два агента можно запустить параллельно, если:
- Оба зависят от ОДНИХ И ТЕХ ЖЕ предыдущих агентов (уже завершенных)
- Они пишут в РАЗНЫЕ директории/файлы (нет конфликта записи)

#### 5.2. Добавь в скрипт запуска:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# Последовательный порядок (существующий)
PIPELINE_ORDER = [1, 2, 4, 5, 7, 8, 6]

# Параллельные стадии (новый)
PARALLEL_STAGES = [
    [1],        # Stage 1: один
    [2, 4],     # Stage 2: параллельно
    [5],        # Stage 3: один
    [7],        # Stage 4: один
    [8, 6],     # Stage 5: параллельно
]

def run_stage_parallel(agent_ids, project, model, dry_run, max_budget, timeout):
    """Запуск нескольких агентов параллельно."""
    results = {}
    with ThreadPoolExecutor(max_workers=len(agent_ids)) as executor:
        futures = {
            executor.submit(
                run_single_agent, aid, project, "/auto",
                model, dry_run, max_budget, timeout,
            ): aid
            for aid in agent_ids
        }
        for future in as_completed(futures):
            aid = futures[future]
            try:
                results[aid] = future.result()
            except Exception as e:
                results[aid] = AgentResult(
                    agent_id=aid, status="failed", error=str(e),
                )
    return results
```

#### 5.3. Модифицируй функцию конвейера:

```python
def run_pipeline(project, ..., parallel=False):
    if parallel:
        # Итерируем по стадиям
        for stage in PARALLEL_STAGES:
            if len(stage) == 1:
                # Один агент - обычный запуск
                result = run_single_agent(stage[0], ...)
            else:
                # Несколько агентов - параллельный запуск
                results = run_stage_parallel(stage, ...)

            # Если любой агент в стадии failed - остановить конвейер
            if any(r.status == "failed" for r in results.values()):
                break
    else:
        # Оригинальное последовательное поведение
        for agent_id in PIPELINE_ORDER:
            result = run_single_agent(agent_id, ...)
```

#### 5.4. Добавь CLI аргумент:

```python
parser.add_argument("--parallel", action="store_true",
                    help="Параллельный запуск независимых агентов")
```

**Ключевые решения:**
- ThreadPoolExecutor, НЕ asyncio - агенты это subprocess.run() (I/O-bound), потоки проще
- Без `--parallel` - поведение идентично текущему (обратная совместимость)
- Ошибка одного агента не убивает другие в той же стадии, но останавливает переход к следующей
- Фильтр `--agents 1,2,4` работает с обоими режимами

---

### Порядок реализации

```
ШАГ 1: Adaptive Thinking     [~30 мин]   Самое простое, мгновенная экономия
ШАГ 2: Дедупликация           [~1-2 часа] Уменьшает объем файлов, упрощает поддержку
ШАГ 3: GitHub Actions         [~1-2 часа] Автоматический контроль качества
ШАГ 4: Langfuse               [~2-4 часа] Самое сложное, но дает полную видимость
ШАГ 5: Параллельный запуск    [~1-2 часа] Ускорение, после того как конвейер стабилен
```

### Чеклист завершения

После каждого шага:
- [ ] Функциональность работает (тест / dry-run)
- [ ] Обратная совместимость сохранена
- [ ] Документация обновлена (README, CLAUDE.md)
- [ ] Git commit + push
- [ ] Секреты НЕ попали в коммит (.env в .gitignore)

---

## ---КОНЕЦ ПРОМПТА---

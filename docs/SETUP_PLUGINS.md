# Настройка плагинов и MCP-серверов

## 1. MCP Confluence (mcp-atlassian) - УСТАНОВЛЕН

Production-ready MCP-сервер для on-premise Confluence Server.

### Статус: Установлен и настроен

- Пакет: `mcp-atlassian` (pip)
- Конфигурация: `.mcp.json`
- 11 инструментов: search, get_page, update_page, create_page, comments, labels и др.

### Если нужна переустановка:

```bash
# Активировать venv
source .venv/bin/activate

# Установить
pip install mcp-atlassian

# Добавить CONFLUENCE_TOKEN в .env
echo "CONFLUENCE_TOKEN=your_pat_here" >> .env
```

---

## 2. ~~Episodic Memory~~ — DEPRECATED (2026-02-28)

> **Не используется.** Заменено на: Graphiti (temporal KG) + MCP memory (KG) + Agent Memory (per-agent).
> Конфигурация ниже оставлена для справки.

~~Семантическая память между сессиями Claude Code. Агенты "помнят" предыдущие аудиты ФМ.~~

### Установка

**Способ 1: Через Claude Code плагин (рекомендуется)**

Выполнить ВНУТРИ чата Claude Code (это slash-команды, не bash):
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install episodic-memory@superpowers-marketplace
```

**Способ 2: Через npm + MCP (в терминале)**

```bash
npm install -g episodic-memory
# Затем добавить MCP-сервер (см. ниже)
```

### MCP-конфигурация (если способ 2):

Добавить в `~/.claude/settings.json` или `.mcp.json`:
```json
{
  "mcpServers": {
    "episodic-memory": {
      "command": "episodic-memory-mcp-server",
      "args": []
    }
  }
}
```

### Что дает:

- `episodic_memory_search` - семантический поиск по прошлым сессиям
- `episodic_memory_show` - показ полного разговора
- Автоиндексация при завершении сессии
- Локальные эмбеддинги (Transformers.js, нет внешних API)
- SQLite + sqlite-vec для векторного поиска

### Команды CLI:

```bash
episodic-memory sync     # Синхронизировать сессии
episodic-memory search "аудит ФМ рентабельность"  # Поиск
episodic-memory stats    # Статистика
```

### Рекомендуется также:

В `~/.claude/settings.json` увеличить срок хранения логов:
```json
{
  "cleanupPeriodDays": 365
}
```

---

## 3. Confluence Agent Skill - НЕ ПОДХОДИТ

**Причина**: mastering-confluence-agent-skill поддерживает ТОЛЬКО Confluence Cloud.
Наш сервер (https://confluence.ekf.su) - on-premise Confluence Server.
Используем mcp-atlassian (пункт 1) вместо этого.

---

## 4. Будущие интеграции (Roadmap)

| Приоритет | Технология | Статус |
|-----------|-----------|--------|
| P2 | Langfuse (observability) | Запланировано |
| P2 | GitHub Actions (PR review) | Запланировано |
| P3 | Agent Teams (параллельная работа) | Эксперимент |
| P3 | Agent SDK (Python) | Наблюдение |

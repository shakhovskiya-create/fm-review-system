# Testing Audit: fm-review-system

**Дата:** 2026-02-18
**Тип:** Python - AI agents для ревью функциональных моделей 1С ERP + Confluence publishing
**Общая оценка: 🟡 40% покрытия, нет integration tests с реальными агентами**

---

## Unit тесты

### Что есть (5 файлов)

| Файл | Что тестирует | Оценка |
|------|--------------|--------|
| conftest.py | Shared fixtures | ✅ |
| test_agent_configs.py | Agent configuration loading/validation | ✅ |
| test_confluence_utils.py | Confluence API utilities | ✅ |
| test_pipeline.py | Review pipeline logic | ✅ |
| test_publish_to_confluence.py | Publishing workflow | ✅ |

### Source modules (scripts/)

| Файл | Тесты | Приоритет |
|------|-------|-----------|
| run_agent.py | ❌ | 🔴 |
| publish_to_confluence.py | ✅ (test_publish_to_confluence) | ✅ |
| check_confluence_macros.py | ❌ | 🟡 |
| export_from_confluence.py | ❌ | 🟡 |
| import_docx.py | ❌ | 🟡 |
| seed_memory.py | ❌ | 🟠 |

### Дополнительные элементы

| Элемент | Статус |
|---------|--------|
| pytest.ini | ✅ Настроен |
| conftest.py | ✅ С fixtures |
| schemas/agent-contracts.json | ✅ Agent contract schema |
| scripts/experimental/contract_validator | ✅ Валидация контрактов |

---

## CI/CD

### Что есть

| Workflow | Содержание |
|----------|-----------|
| claude.yml | Claude Code integration |
| security-review.yml | Security review на PR |

### Что отсутствует

| Категория | Статус | Приоритет |
|-----------|--------|-----------|
| **CI workflow для pytest** | ❌ | 🔴 |
| Coverage reporting | ❌ | 🔴 |
| Coverage gate | ❌ | 🟡 |
| bandit SAST | ❌ | 🟡 |
| Dependabot | ❌ | 🟡 |

**Проблема:** Тесты есть, но CI их не запускает. Аналогично cio-dashboard - тесты только локально.

---

## Agent-специфичное тестирование

### Что есть
- ✅ agent-contracts.json - схема контрактов агентов
- ✅ contract_validator - валидация контрактов
- ✅ test_agent_configs - проверка конфигов

### Что отсутствует

| Категория | Описание | Приоритет |
|-----------|----------|-----------|
| **Agent output quality** | DeepEval metrics для ответов агентов | 🔴 |
| **Full pipeline test** | Document → agents → review → publish | 🔴 |
| **Confluence integration** | Real API smoke test (staging) | 🟡 |
| **Agent hallucination check** | Faithfulness metric на реальных FM | 🟡 |
| **Regression suite** | Golden samples с expected outputs | 🟡 |

---

## Infrastructure

| Элемент | Статус |
|---------|--------|
| infra/langfuse/docker-compose.yml | ✅ Langfuse для observability |
| .claude/hooks/ | ✅ Pre-compact hooks |
| Docker для приложения | ❌ |
| Тесты hooks | ❌ |

---

## Security

| Элемент | Статус |
|---------|--------|
| security-review.yml | ✅ |
| bandit | ❌ |
| safety (deps) | ❌ |
| API key handling | Не тестируется |
| Confluence credentials | Не тестируется |

---

## Рекомендации

1. 🔴 **CI workflow с pytest:**
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: pip install pytest-cov bandit
      - run: pytest --cov=. --cov-report=xml --cov-fail-under=40
      - run: bandit -r scripts/ -x tests/
```

2. 🔴 **Agent quality tests (DeepEval):**
```python
# tests/test_agent_quality.py
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric

def test_review_agent_faithfulness():
    """Agent review должен быть faithful к исходному FM документу"""
    metric = FaithfulnessMetric(threshold=0.7)
    # ...

def test_review_agent_relevancy():
    """Agent должен отвечать на конкретные вопросы из checklist"""
    metric = AnswerRelevancyMetric(threshold=0.8)
    # ...
```

3. 🔴 **Full pipeline integration test:**
```python
@pytest.mark.integration
def test_full_review_pipeline():
    """Document upload → agent review → structured output → ready for publish"""
    # Load sample FM document
    # Run through pipeline
    # Verify output structure matches agent-contracts.json
    # Verify all sections reviewed
```

4. 🟡 **Golden sample regression:**
```
tests/golden/
├── input_fm_sample_1.docx
├── expected_review_1.json
├── input_fm_sample_2.docx
└── expected_review_2.json
```

5. 🟡 **Тесты для run_agent.py** - основной entry point, 0 тестов

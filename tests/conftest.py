"""
Fixtures for FM Review System tests.
Mocks Confluence API, provides temporary project structures.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path so we can import fm_review
SRC_DIR = Path(__file__).parent.parent / "src"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


SAMPLE_XHTML = """<p><strong>Код проекта:</strong> FM-LS-PROFIT
<strong>Версия ФМ:</strong> 1.0.2
<strong>Дата:</strong> 10.02.2026
<strong>Автор:</strong> Шаховский А.С.
<strong>Платформа:</strong> 1С:УТ</p>
<h1>Функциональная модель</h1>
<table class="confluenceTable"><tbody>
<tr><th class="confluenceTh" style="background-color: rgb(255,250,230);"><strong>Версия</strong></th>
<th class="confluenceTh" style="background-color: rgb(255,250,230);"><strong>Дата</strong></th>
<th class="confluenceTh" style="background-color: rgb(255,250,230);"><strong>Автор</strong></th>
<th class="confluenceTh" style="background-color: rgb(255,250,230);"><strong>Изменения</strong></th></tr>
<tr><td class="confluenceTd">1.0.0</td>
<td class="confluenceTd">01.02.2026</td>
<td class="confluenceTd">Шаховский А.С.</td>
<td class="confluenceTd">Первая публикация</td></tr>
<tr><td class="confluenceTd">1.0.1</td>
<td class="confluenceTd">05.02.2026</td>
<td class="confluenceTd">Шаховский А.С.</td>
<td class="confluenceTd">Уточнены формулы расчета</td></tr>
<tr><td class="confluenceTd">1.0.2</td>
<td class="confluenceTd">10.02.2026</td>
<td class="confluenceTd">Шаховский А.С.</td>
<td class="confluenceTd">Добавлены SLA</td></tr>
</tbody></table>
<h2>3. Бизнес-правила</h2>
<p>Основные правила работы системы.</p>"""


def make_confluence_response(page_id="83951683", version=42, title="FM-LS-PROFIT",
                             body=None):
    """Build a mock Confluence API response."""
    return {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": version, "message": "test"},
        "body": {
            "storage": {
                "value": body or SAMPLE_XHTML,
                "representation": "storage"
            }
        }
    }


@pytest.fixture
def sample_xhtml():
    """Return sample XHTML content for testing."""
    return SAMPLE_XHTML


@pytest.fixture
def confluence_response():
    """Return a factory for Confluence API responses."""
    return make_confluence_response


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project structure for testing."""
    project_dir = tmp_path / "PROJECT_TEST"
    project_dir.mkdir()
    (project_dir / "CONFLUENCE_PAGE_ID").write_text("99999999\n")
    (project_dir / "README.md").write_text("# Test Project\n")

    changes_dir = project_dir / "CHANGES"
    changes_dir.mkdir()

    for agent_num, name in [(1, "ARCHITECT"), (2, "ROLE_SIMULATOR"),
                             (4, "QA_TESTER"), (5, "TECH_ARCHITECT")]:
        agent_dir = project_dir / f"AGENT_{agent_num}_{name}"
        agent_dir.mkdir()

    return project_dir


@pytest.fixture
def mock_urllib(confluence_response):
    """Mock urllib.request to simulate Confluence API calls."""
    response_data = confluence_response()

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        mock_open._response_data = response_data
        yield mock_open

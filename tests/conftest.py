"""Global pytest configuration and fixtures for RippleMap test suite.

Ensures unit and integration tests do not consume live Groq API quota or require
network access, while preserving explicit mock tests in test_groq_integration.py.
"""

from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def mock_groq_narratives_for_non_groq_tests(request):
    """Prevents non-Groq test modules (like test_investigation_agent.py) from making
    live external LLM API calls during standard test suite execution.
    """
    if "test_groq_integration" in request.module.__name__:
        yield
        return

    with patch(
        "app.investigation_agent.generate_briefing_narrative",
        return_value=(None, "DETERMINISTIC_ONLY"),
    ), patch(
        "app.investigation_agent.generate_question_narrative",
        return_value=(None, "DETERMINISTIC_ONLY"),
    ):
        yield

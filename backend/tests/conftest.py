"""
Shared pytest fixtures.

Deliberately minimal — most of this suite targets pure-computation agents
(no DB, no network) precisely because those are the parts of this
codebase that can be tested without a running Postgres/Redis/ChromaDB.
DB-backed integration tests (services/, api/) are a natural Phase 14+
follow-up once there's a test database to point at — flagged as the next
layer to add, not silently treated as covered by this suite.
"""
import pytest


@pytest.fixture
def rubric_criteria():
    """A representative rubric — the shape every Theory/Course analytics
    test in this suite that needs one starts from."""
    return [
        {"name": "correctness", "weight": 0.5},
        {"name": "efficiency", "weight": 0.15},
        {"name": "edge_cases", "weight": 0.15},
        {"name": "readability", "weight": 0.1},
        {"name": "naming", "weight": 0.05},
        {"name": "documentation", "weight": 0.05},
    ]

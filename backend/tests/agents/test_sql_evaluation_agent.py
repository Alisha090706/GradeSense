"""
agents/sql_evaluation_agent.py — mirrors the real sqlite3 verification
session from Phase 6 (five scenarios run against real SQLite while
building this: correct query, blocked injection, blocked multi-statement,
syntax error, and a legitimate WITH...SELECT CTE — see that phase's
README section).
"""
import pytest

from app.agents.sql_evaluation_agent import _rows_match, _run_query, validate_select_only

SCHEMA = "CREATE TABLE students(id INTEGER, name TEXT, grade INTEGER);"
SEED = "INSERT INTO students VALUES (1,'Alice',90),(2,'Bob',72),(3,'Carol',85);"


class TestValidateSelectOnly:
    def test_plain_select_is_allowed(self):
        assert validate_select_only("SELECT * FROM students") is None

    def test_with_select_cte_is_allowed(self):
        query = "WITH top AS (SELECT * FROM students WHERE grade > 80) SELECT name FROM top"
        assert validate_select_only(query) is None

    def test_drop_table_is_blocked(self):
        assert validate_select_only("DROP TABLE students") is not None

    def test_multi_statement_injection_is_blocked(self):
        assert validate_select_only("SELECT * FROM students; DELETE FROM students") is not None

    def test_update_is_blocked(self):
        assert validate_select_only("UPDATE students SET grade = 100") is not None


class TestRunQuery:
    def test_correct_query_returns_expected_rows(self):
        rows, error = _run_query(SCHEMA, SEED, "SELECT name FROM students WHERE grade > 80 ORDER BY id")
        assert error is None
        assert rows == [("Alice",), ("Carol",)]

    def test_syntax_error_is_captured_not_raised(self):
        rows, error = _run_query(SCHEMA, SEED, "SELECT nam FROM studnts")
        assert rows == []
        assert error is not None
        assert "no such table" in error.lower()


class TestRowsMatch:
    def test_order_insensitive_by_default(self):
        actual = [("Carol",), ("Alice",)]
        expected = [["Alice"], ["Carol"]]
        assert _rows_match(actual, expected, order_matters=False) is True

    def test_order_sensitive_when_requested(self):
        actual = [("Carol",), ("Alice",)]
        expected = [["Alice"], ["Carol"]]
        assert _rows_match(actual, expected, order_matters=True) is False

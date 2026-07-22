"""
agents/evaluation/codegen.py — the literal-codegen module that makes
Java/C++ grading work off the same JSON test cases Python/JS use (see
that module's docstring). Assertions here mirror values verified by hand
against real g++ output while building Phase 5 — see the backend README's
Phase 5 section for the actual compile-and-run session this suite
formalizes into repeatable tests.
"""
import pytest

from app.agents.evaluation.codegen import (
    UnsupportedTypeError, canonical_repr, cpp_literal, cpp_type, java_literal, java_repr_expr, java_type,
)


class TestCanonicalRepr:
    def test_int(self):
        assert canonical_repr(3) == "3"

    def test_float(self):
        assert canonical_repr(3.0) == "3.0"

    def test_bool_true_is_lowercase(self):
        assert canonical_repr(True) == "true"

    def test_bool_false_is_lowercase(self):
        assert canonical_repr(False) == "false"

    def test_string_passthrough(self):
        assert canonical_repr("hi") == "hi"

    def test_list(self):
        assert canonical_repr([1, 2, 3]) == "[1, 2, 3]"

    def test_empty_list(self):
        assert canonical_repr([]) == "[]"

    def test_unsupported_type_raises(self):
        with pytest.raises(UnsupportedTypeError):
            canonical_repr({"a": 1})


class TestJavaCodegen:
    def test_java_type_int_list(self):
        assert java_type([1, 2, 3]) == "int[]"

    def test_java_literal_int_list(self):
        assert java_literal([1, 2, 3]) == "new int[]{1, 2, 3}"

    def test_java_type_string(self):
        assert java_type("hi") == "String"

    def test_java_literal_string_is_quoted(self):
        assert java_literal("hi") == '"hi"'

    def test_java_repr_expr_uses_string_valueOf_for_scalars(self):
        # Not raw concatenation — assigning a primitive boolean straight into a
        # String won't compile; String.valueOf is required. See codegen.py's
        # fix note for why this specific assertion exists.
        assert java_repr_expr("actual", True) == "String.valueOf(actual)"

    def test_java_repr_expr_uses_arrays_toString_for_lists(self):
        assert java_repr_expr("actual", [1, 2, 3]) == "java.util.Arrays.toString(actual)"

    def test_empty_list_raises(self):
        with pytest.raises(UnsupportedTypeError):
            java_type([])


class TestCppCodegen:
    def test_cpp_type_int_vector(self):
        assert cpp_type([1, 2, 3]) == "std::vector<int>"

    def test_cpp_literal_int_vector(self):
        assert cpp_literal([1, 2, 3]) == "{1, 2, 3}"

    def test_cpp_type_string(self):
        assert cpp_type("hi") == "std::string"

    def test_cpp_literal_string_is_quoted(self):
        assert cpp_literal("hi") == '"hi"'

    def test_cpp_literal_float_always_has_decimal_point(self):
        # repr(3) has no ".", so cpp_literal must add one — a bare "3" for a
        # value that's supposed to be a double would silently become an int
        # literal in the generated C++.
        assert cpp_literal(3.0) == "3.0"

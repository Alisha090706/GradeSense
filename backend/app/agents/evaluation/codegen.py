"""
Shared value <-> source-literal conversion for the compiled-language runners
(java_runner.py, cpp_runner.py).

The core trick that makes one JSON test-case format work across Python
(dynamic, runs test cases at runtime via the harness), JavaScript (also
dynamic, same approach), AND Java/C++ (statically typed, can't parse
arbitrary JSON into a typed value at runtime without a JSON library
we can't assume is available) is: for the compiled languages, don't parse
JSON at runtime at all — generate source code with the test values as
literals, baked in at compile time. `canonical_repr` defines ONE string
format for every value (ints, floats, bools, strings, and 1D lists of
those) that every language's generated comparison code is made to match
exactly, so "does actual == expected" becomes "does canonical_repr(actual)
== canonical_repr(expected)" — a plain string comparison, sidestepping
type-specific equality entirely.

Known scope limit, intentional: only int/float/bool/str and flat (1D)
lists of those are supported for Java/C++. Nested lists, dicts, or custom
objects as args/return values aren't — that covers the large majority of
introductory DSA-style problems (the platform's primary use case per the
architecture doc's subject list) without the substantial extra complexity
of general recursive type codegen. Flagged here rather than failing
silently: unsupported types raise UnsupportedTypeError with a clear message
at test-generation/submission time, not a confusing compiler error.
"""


class UnsupportedTypeError(ValueError):
    pass


def canonical_repr(value) -> str:
    """The one true string format every language's runner must reproduce."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(canonical_repr(v) for v in value) + "]"
    raise UnsupportedTypeError(f"Unsupported value type for compiled-language grading: {type(value).__name__}")


def _scalar_java_type(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "String"
    raise UnsupportedTypeError(f"Unsupported scalar type for Java: {type(value).__name__}")


def java_type(value) -> str:
    if isinstance(value, list):
        if not value:
            raise UnsupportedTypeError("Cannot infer a Java array type from an empty list.")
        return _scalar_java_type(value[0]) + "[]"
    return _scalar_java_type(value)


def _java_scalar_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value) + ("" if "." in repr(value) or "e" in repr(value) else ".0")
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise UnsupportedTypeError(f"Unsupported scalar literal for Java: {type(value).__name__}")


def java_literal(value) -> str:
    if isinstance(value, list):
        elem_type = _scalar_java_type(value[0]) if value else "int"
        items = ", ".join(_java_scalar_literal(v) for v in value)
        return f"new {elem_type}[]{{{items}}}"
    return _java_scalar_literal(value)


def java_repr_expr(var_name: str, value) -> str:
    """Java source expression that formats `var_name` (of the type inferred from
    `value`) into canonical_repr's format at runtime."""
    if isinstance(value, list):
        return f"java.util.Arrays.toString({var_name})"
    # String.valueOf has overloads for boolean/int/double/Object — for a boolean
    # this correctly yields "true"/"false" (matching canonical_repr) rather than
    # trying to assign a primitive boolean straight into a String, which won't
    # compile.
    return f"String.valueOf({var_name})"


def _scalar_cpp_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "std::string"
    raise UnsupportedTypeError(f"Unsupported scalar type for C++: {type(value).__name__}")


def cpp_type(value) -> str:
    if isinstance(value, list):
        if not value:
            raise UnsupportedTypeError("Cannot infer a C++ vector type from an empty list.")
        return f"std::vector<{_scalar_cpp_type(value[0])}>"
    return _scalar_cpp_type(value)


def _cpp_scalar_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        r = repr(value)
        return r if ("." in r or "e" in r) else r + ".0"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise UnsupportedTypeError(f"Unsupported scalar literal for C++: {type(value).__name__}")


def cpp_literal(value) -> str:
    if isinstance(value, list):
        items = ", ".join(_cpp_scalar_literal(v) for v in value)
        return f"{{{items}}}"
    return _cpp_scalar_literal(value)


def _java_json_scalar_expr(var_name: str, value) -> str:
    """Java expression producing valid JSON text for a single scalar variable."""
    if isinstance(value, bool):
        return f"String.valueOf({var_name})"
    if isinstance(value, int):
        return f"String.valueOf({var_name})"
    if isinstance(value, float):
        return f"String.valueOf({var_name})"
    if isinstance(value, str):
        return f"jsonQuote({var_name})"
    raise UnsupportedTypeError(f"Unsupported scalar type for Java JSON capture: {type(value).__name__}")


def java_json_repr_expr(var_name: str, value) -> str:
    """Java source expression that serializes `var_name` (of the type inferred from
    `value`, a Python value used only as a type hint) into valid JSON text — used by
    java_reference_runner.py to capture a reference solution's real return value and
    hand it back to Python as an actual typed value (via json.loads), rather than just
    a pass/fail string comparison like java_repr_expr (used for grading real student
    submissions, where there's nothing to hand a value back to)."""
    if isinstance(value, list):
        return f"jsonArray({var_name})"
    return _java_json_scalar_expr(var_name, value)


# Helper Java methods embedded verbatim into the generated Main class by
# java_reference_runner.py — kept here so the two files' contracts (which
# helper names java_json_repr_expr's output calls) stay next to each other.
JAVA_JSON_HELPERS = """
    static String jsonQuote(String s) {
        StringBuilder b = new StringBuilder("\\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\\\') b.append('\\\\');
            b.append(c);
        }
        return b.append('"').toString();
    }

    static String jsonArray(int[] a) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) { if (i > 0) b.append(", "); b.append(a[i]); }
        return b.append("]").toString();
    }

    static String jsonArray(double[] a) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) { if (i > 0) b.append(", "); b.append(a[i]); }
        return b.append("]").toString();
    }

    static String jsonArray(boolean[] a) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) { if (i > 0) b.append(", "); b.append(a[i]); }
        return b.append("]").toString();
    }

    static String jsonArray(String[] a) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) { if (i > 0) b.append(", "); b.append(jsonQuote(a[i])); }
        return b.append("]").toString();
    }
"""

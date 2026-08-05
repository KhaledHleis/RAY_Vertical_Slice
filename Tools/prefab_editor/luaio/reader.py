"""A parser for the data-only subset of Lua used by `definitions.lua`.

Deliberately narrow. It understands table constructors, string/number/boolean
literals, `Vector.new(x, y)`, `math.pi`, `math.rad(x)` and simple arithmetic --
and nothing else. Anything outside that raises `LuaSyntaxError` with a line and
column, rather than silently dropping data on the floor. A prefab file we cannot
fully understand is a prefab file we must not overwrite.

Using a real Lua interpreter would accept more syntax, but it would also need a
native dependency and could not preserve the source text of expressions or the
comments attached to each entry.
"""

from __future__ import annotations

import math
import re

from .types import LuaSyntaxError, LuaTable, Num, Vec2

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<long_comment>--\[(?P<eq>=*)\[.*?\](?P=eq)\])
  | (?P<comment>--[^\n]*)
  | (?P<number>
        0[xX][0-9a-fA-F]+
      | (?:\d+\.\d*|\.\d+|\d+) (?:[eE][+-]?\d+)?
    )
  | (?P<name>[A-Za-z_]\w*)
  | (?P<string>"(?:\\.|[^"\\])*" | '(?:\\.|[^'\\])*')
  | (?P<punct>\.\.\.|[-+*/%^#(){}\[\],;=.:])
    """,
    re.VERBOSE | re.DOTALL,
)

_KEYWORDS = {"true", "false", "nil", "return", "local", "function", "end"}

_MATH_CONSTANTS = {"pi": math.pi, "huge": math.inf}
_MATH_FUNCTIONS = {
    "rad": math.radians,
    "deg": math.degrees,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}


class _Token:
    __slots__ = ("kind", "value", "line", "column", "start", "end")

    def __init__(self, kind, value, line, column, start, end):
        self.kind = kind
        self.value = value
        self.line = line
        self.column = column
        self.start = start
        self.end = end

    def __repr__(self):
        return f"<{self.kind} {self.value!r} @{self.line}:{self.column}>"


def tokenize(source):
    """Return (tokens, comments) where comments maps token index -> comment text."""
    tokens = []
    comments = {}
    pending = []
    pos = 0
    line = 1
    line_start = 0
    length = len(source)

    while pos < length:
        match = _TOKEN_RE.match(source, pos)
        if not match:
            column = pos - line_start + 1
            raise LuaSyntaxError(f"unexpected character {source[pos]!r}", line, column)

        kind = match.lastgroup
        text = match.group()
        column = pos - line_start + 1

        if kind in ("comment", "long_comment"):
            pending.append(_strip_comment(text))
        elif kind != "ws":
            if kind == "name" and text in _KEYWORDS:
                kind = "keyword"
            if pending:
                comments[len(tokens)] = "\n".join(pending)
                pending = []
            tokens.append(
                _Token(kind, text, line, column, match.start(), match.end())
            )

        newlines = text.count("\n")
        if newlines:
            line += newlines
            line_start = match.start() + text.rfind("\n") + 1
        pos = match.end()

    tokens.append(_Token("eof", "", line, pos - line_start + 1, pos, pos))
    return tokens, comments


def _strip_comment(text):
    if text.startswith("--[["):
        return text[4:-2].strip("\n")
    return text[2:].strip()


class LuaReader:
    def __init__(self, source):
        self.source = source
        self.tokens, self.comments = tokenize(source)
        self.index = 0

    # -- token helpers -----------------------------------------------------

    @property
    def current(self):
        return self.tokens[self.index]

    def peek(self, offset=0):
        return self.tokens[min(self.index + offset, len(self.tokens) - 1)]

    def advance(self):
        token = self.tokens[self.index]
        self.index += 1
        return token

    def check(self, kind, value=None):
        token = self.current
        return token.kind == kind and (value is None or token.value == value)

    def accept(self, kind, value=None):
        if self.check(kind, value):
            return self.advance()
        return None

    def expect(self, kind, value=None):
        token = self.accept(kind, value)
        if token is None:
            wanted = value if value is not None else kind
            raise LuaSyntaxError(
                f"expected {wanted!r} but found {self.current.value!r}",
                self.current.line,
                self.current.column,
            )
        return token

    def take_comment(self):
        return self.comments.get(self.index)

    # -- entry point -------------------------------------------------------

    def parse_module(self):
        """Skip leading `local x = require(...)` lines and parse `return <value>`."""
        while not self.check("keyword", "return"):
            if self.check("eof"):
                raise LuaSyntaxError("no `return` statement found", self.current.line, 1)
            self._skip_local_statement()

        self.expect("keyword", "return")
        value = self.parse_value()
        self.accept("punct", ";")

        # Anything after the returned table is content we cannot represent.
        # Refuse rather than load it and silently drop it on the next save.
        if not self.check("eof"):
            raise LuaSyntaxError(
                f"unexpected {self.current.value!r} after the returned table; "
                f"the editor only supports a module that returns a single table",
                self.current.line,
                self.current.column,
            )
        return value

    def _skip_local_statement(self):
        if not self.accept("keyword", "local"):
            raise LuaSyntaxError(
                "only `local ... = require(...)` statements may precede `return`",
                self.current.line,
                self.current.column,
            )
        self.expect("name")
        self.expect("punct", "=")
        depth = 0
        while True:
            token = self.current
            if token.kind == "eof":
                raise LuaSyntaxError("unterminated statement", token.line, token.column)
            if token.kind == "punct" and token.value == "(":
                depth += 1
            elif token.kind == "punct" and token.value == ")":
                depth -= 1
                self.advance()
                if depth <= 0:
                    return
                continue
            elif depth == 0 and (
                token.kind == "keyword" or (token.kind == "name" and self.peek(1).value == "=")
            ):
                return
            self.advance()

    # -- values ------------------------------------------------------------

    def parse_value(self):
        token = self.current

        if token.kind == "string":
            self.advance()
            return _decode_string(token.value)

        if token.kind == "keyword":
            if token.value == "true":
                self.advance()
                return True
            if token.value == "false":
                self.advance()
                return False
            if token.value == "nil":
                self.advance()
                return None

        if token.kind == "punct" and token.value == "{":
            return self.parse_table()

        return self.parse_expression()

    def parse_table(self):
        open_token = self.expect("punct", "{")
        table = LuaTable()

        while not self.check("punct", "}"):
            if self.check("eof"):
                raise LuaSyntaxError(
                    "unterminated table constructor", open_token.line, open_token.column
                )

            comment = self.take_comment()

            # `[expr] = value`
            if self.check("punct", "["):
                self.advance()
                key = self.parse_value()
                self.expect("punct", "]")
                self.expect("punct", "=")
                value = self.parse_value()
                key = float(key) if isinstance(key, (int, float)) else key
                table.set(key, value)
                if comment:
                    table.comments[key] = comment

            # `name = value`
            elif self.current.kind == "name" and self.peek(1).value == "=" and self.peek(1).kind == "punct":
                key = self.advance().value
                self.advance()  # '='
                table.set(key, self.parse_value())
                if comment:
                    table.comments[key] = comment

            # positional item
            else:
                table.append(self.parse_value())
                if comment:
                    table.comments[len(table.array) - 1] = comment

            if not (self.accept("punct", ",") or self.accept("punct", ";")):
                break

        self.expect("punct", "}")
        return table

    # -- arithmetic --------------------------------------------------------

    def parse_expression(self):
        start = self.current.start
        value = self._parse_additive()
        end = self.tokens[self.index - 1].end
        src = self.source[start:end].strip()

        if isinstance(value, Vec2):
            return value
        return Num(value, src if src != _plain_number_text(value) else None)

    def _parse_additive(self):
        value = self._parse_multiplicative()
        while self.check("punct", "+") or self.check("punct", "-"):
            op = self.advance().value
            rhs = self._parse_multiplicative()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _parse_multiplicative(self):
        value = self._parse_unary()
        while self.check("punct", "*") or self.check("punct", "/") or self.check("punct", "%"):
            op = self.advance().value
            rhs = self._parse_unary()
            if op == "*":
                value = value * rhs
            elif op == "/":
                value = value / rhs
            else:
                value = value % rhs
        return value

    def _parse_unary(self):
        if self.accept("punct", "-"):
            return -self._parse_unary()
        if self.accept("punct", "+"):
            return self._parse_unary()
        return self._parse_atom()

    def _parse_atom(self):
        token = self.current

        if token.kind == "punct" and token.value == "(":
            self.advance()
            value = self._parse_additive()
            self.expect("punct", ")")
            return value

        if token.kind == "number":
            self.advance()
            return _decode_number(token.value)

        if token.kind == "name":
            if token.value == "math":
                return self._parse_math()
            if token.value == "Vector":
                return self._parse_vector()
            raise LuaSyntaxError(
                f"unsupported identifier {token.value!r}; only numbers, "
                f"`math.*` and `Vector.new` are understood",
                token.line,
                token.column,
            )

        raise LuaSyntaxError(
            f"unexpected {token.value!r} where a value was expected",
            token.line,
            token.column,
        )

    def _parse_math(self):
        token = self.expect("name")  # 'math'
        self.expect("punct", ".")
        field = self.expect("name").value

        if self.accept("punct", "("):
            function = _MATH_FUNCTIONS.get(field)
            if function is None:
                raise LuaSyntaxError(
                    f"unsupported function math.{field}", token.line, token.column
                )
            argument = self._parse_additive()
            self.expect("punct", ")")
            return function(argument)

        if field not in _MATH_CONSTANTS:
            raise LuaSyntaxError(
                f"unsupported constant math.{field}", token.line, token.column
            )
        return _MATH_CONSTANTS[field]

    def _parse_vector(self):
        self.expect("name")  # 'Vector'
        # Both `Vector.new(x, y)` and the __call form `Vector(x, y)` are valid.
        if self.accept("punct", "."):
            field = self.expect("name").value
            if field != "new":
                raise LuaSyntaxError(
                    f"unsupported Vector.{field}", self.current.line, self.current.column
                )
        self.expect("punct", "(")
        x = self._numeric_argument()
        self.expect("punct", ",")
        y = self._numeric_argument()
        self.expect("punct", ")")
        return Vec2(x, y, Vec2.CALL)

    def _numeric_argument(self):
        start = self.current.start
        value = self._parse_additive()
        end = self.tokens[self.index - 1].end
        src = self.source[start:end].strip()
        return Num(value, src if src != _plain_number_text(value) else None)


def _plain_number_text(value):
    """The text a bare literal would have produced, used to decide if src matters."""
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if as_float.is_integer():
        return str(int(as_float))
    return repr(as_float)


def _decode_number(text):
    if text.lower().startswith("0x"):
        return float(int(text, 16))
    return float(text)


_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b",
    "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'", "\n": "\n",
}


def _decode_string(text):
    body = text[1:-1]
    out = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            nxt = body[index + 1]
            out.append(_ESCAPES.get(nxt, nxt))
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def parse(source):
    """Parse a Lua data module, returning the value of its `return` statement."""
    return LuaReader(source).parse_module()


def parse_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return parse(handle.read())

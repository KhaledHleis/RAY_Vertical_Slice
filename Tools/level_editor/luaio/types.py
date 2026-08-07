"""Value types shared by the Lua reader and writer.

The point of `Num` is source preservation: `coneAngle = math.pi / 3` should come
back out of the writer as `math.pi / 3`, not `1.0471975511965976`. `Num`
subclasses `float`, so every consumer (lint rules, the raytracer, the UI) can
treat it as an ordinary number and simply ignore the `src` attribute.

When the UI assigns a new value it stores a plain `float`, which has no `src`,
so the writer falls back to emitting a literal. That is exactly the behaviour we
want: untouched expressions survive, edited ones become numbers.
"""

from __future__ import annotations


class Num(float):
    """A float that remembers the Lua expression it was parsed from."""

    __slots__ = ("src",)

    def __new__(cls, value, src=None):
        self = float.__new__(cls, value)
        self.src = src
        return self

    def __repr__(self):
        return f"Num({float(self)!r}, src={self.src!r})"


def num_src(value):
    """Return the preserved source for `value`, or None."""
    return getattr(value, "src", None)


class Vec2:
    """A 2D value written either as `Vector.new(x, y)` or as `{ x = ..., y = ... }`.

    Both forms are interchangeable at runtime -- the engine only ever reads `.x`
    and `.y` -- but `definitions.lua` uses the call form for light segments and
    the table form for sprite scale/offset. `style` remembers which one the
    source used so saving does not churn the file.
    """

    __slots__ = ("x", "y", "style")

    CALL = "call"
    TABLE = "table"

    def __init__(self, x=0.0, y=0.0, style=None):
        self.x = x
        self.y = y
        self.style = style

    def copy(self):
        return Vec2(self.x, self.y, self.style)

    def as_tuple(self):
        return (float(self.x), float(self.y))

    def __eq__(self, other):
        if isinstance(other, Vec2):
            return self.as_tuple() == other.as_tuple()
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return self.as_tuple() == (float(other[0]), float(other[1]))
        return NotImplemented

    def __repr__(self):
        return f"Vec2({float(self.x)!r}, {float(self.y)!r})"


class LuaTable:
    """A Lua table constructor: positional items, keyed items, or both.

    `comments` maps an array index (int) or a key (str) to the comment block
    that preceded that entry in the source file, so hand-written documentation
    survives a round trip.
    """

    __slots__ = ("array", "hash", "key_order", "comments")

    def __init__(self):
        self.array = []
        self.hash = {}
        self.key_order = []
        self.comments = {}

    def set(self, key, value):
        if key not in self.hash:
            self.key_order.append(key)
        self.hash[key] = value

    def append(self, value):
        self.array.append(value)

    def get(self, key, default=None):
        return self.hash.get(key, default)

    def items(self):
        for key in self.key_order:
            yield key, self.hash[key]

    def __len__(self):
        return len(self.array) + len(self.hash)

    def __repr__(self):
        return f"LuaTable(array={self.array!r}, hash={self.hash!r})"


class LuaSyntaxError(ValueError):
    """Raised when the reader meets syntax outside the supported subset."""

    def __init__(self, message, line, column):
        super().__init__(f"line {line}, column {column}: {message}")
        self.line = line
        self.column = column

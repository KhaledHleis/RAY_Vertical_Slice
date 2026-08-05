# RAY prefab editor

A PyQt6 editor for `Frontend/prefabs/definitions.lua`: add and remove
components, edit their arguments, drag collider and light-segment gizmos, and
watch light bounce off the prefab while you work.

## Running

```bash
cd Tools
python -m prefab_editor                 # finds the project root automatically
python -m prefab_editor --project ..    # or point at it explicitly
python -m prefab_editor --lint          # headless checks, non-zero exit on error
python -m prefab_editor.tests.run_tests # self-tests, no Qt required
```

Requires `PyQt6`. The `--lint` and test paths need only the standard library,
so they work on the handheld and in CI.

## Viewport

| Input | Action |
|---|---|
| Left drag on a handle | Move that handle |
| Left drag on empty space, or middle drag | Pan |
| Wheel | Zoom about the cursor |
| `F` | Frame the prefab and the light probe |

White squares resize the collider about its opposite edge; the round handle at
its centre moves the collider `offset`; the handle on the stalk sets the collider
`angle`. Segment endpoints and midpoints drag directly. The orange crosshair is
the light probe — drag the centre to move it, the outer dot to aim it.

`Snap` is in game pixels. Keep it at 1 or 8: at 320x240 a fractional coordinate
in a prefab is nearly always a mistake.

## What it will not do

`HingeJoint` is offered but blocked, because it needs a live object reference
that only `Level.load` resolves from `extraComponents` + `connectedObjectId`.
A prefab-level `HingeJoint` fails the assert in `OnAttach`. Joints belong in the
level file.

Only one component of each type is allowed, because `Object:AddComponent` keys
`self.components` by `tostring(component)` — a second `SpriteRenderer` silently
replaces the first rather than stacking.

## File handling

`definitions.lua` is read and written directly. The parser covers the data
subset only: table constructors, numbers, strings, booleans, `Vector.new(x, y)`,
`math.pi`, `math.rad(x)` and simple arithmetic. Anything else raises a
`LuaSyntaxError` and the file refuses to load, rather than loading partially and
silently deleting what it could not represent on the next save.

Three things survive a round trip:

* expressions — `coneAngle = math.pi / 3` comes back as written, not as
  `1.0471975511965976`;
* comments attached to a prefab or a component entry;
* `Vector.new(x, y)` versus `{ x = ..., y = ... }` for two-component values.

An argument is written when it was present in the source file *or* when it
differs from the engine default, so loading and saving without edits is a no-op.
Save shows a unified diff first and keeps the previous version as `.bak`.

## Checks

The lint panel encodes constraints that are otherwise only discoverable by
running the game:

* collider extents outside Box2D's tuned 0.1–10 m band (read live from
  `World.PIXELS_PER_METER`), which is what makes bodies rest in mid-air;
* a `LightCollider` on a dynamic body without `dynamic = true`, whose segments
  freeze at spawn while the body moves;
* `fixedRotation` on a body carrying light segments, which can then never change
  angle in play;
* `shape = "circle"` with no `radius`, which has no fallback and crashes on
  attach;
* components missing from `component_registry.lua`;
* duplicate component types, missing sprite files, sprite/collider size
  mismatch, zero-length or inert segments, `rayCount < 2` (a divide by zero in
  `LightSource:Update`), and a `GodrayRenderer` with no `LightSource` beside it.

Double-click a row to jump to the prefab.

## Light preview

`preview/raytrace.py` is a line-for-line port of `ray_math.lua`,
`LightWorld.raycast` and `LightSource:castRay`, including the epsilon, the
normal-flipping rule and the recursion order. `tests/run_tests.py` checks it
against the Lua when an interpreter is available. Segment colours match
`debug_light_renderer.lua`: yellow mirror, blue glass, red absorber, white
inert. If a prefab has its own `LightSource` it is traced from the origin at the
preview rotation, exactly as the engine would.

Godray fills reproduce `GodrayRenderer:drawQuadPair`, recursion included, so
what you see is what the game draws.

## Extending it

`model/schema.py` is the single source of truth. Adding a component to the
engine means adding one `ComponentSpec` there — the Add menu, the inspector
widgets, the defaults, the "is this still default" check used by the writer and
the lint's component-set rules all follow. Keep each `Field` default identical
to the `args.x or <default>` fallback in the Lua, since the writer relies on it
to decide what it can leave out.

New widget kinds go in `ui/fields.py` and are dispatched from `build_field`.
New gizmos go in `ui/viewport.py` by appending `Handle` objects during paint.

## Layout

```
model/schema.py       component definitions -- start here
model/library.py      Prefab / Component, explicit-key tracking
model/document.py     snapshot undo, save, diff
model/project.py      project discovery, registry and px/m read from the engine
model/generators.py   fit-collider-to-sprite, segments-from-collider
luaio/reader.py       restricted-subset Lua parser
luaio/writer.py       emitter
ui/                   viewport, inspector, fields, segment table, main window
preview/raytrace.py   engine-parity light propagation
validate/lint.py      the checks
tests/run_tests.py    self-tests
```

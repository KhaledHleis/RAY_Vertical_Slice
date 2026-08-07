# RAY level editor

A PyQt6 editor for `Frontend/levels/*.lua`: place prefabs, drag and rotate them,
override their components per instance, wire up joints, and watch the whole
room's light solution update while you work.

Standalone. It reads `Frontend/prefabs/definitions.lua` but never writes it, and
shares no code with `Tools/prefab_editor` — the two can be edited independently.

## Running

```bash
cd Tools
python -m level_editor                    # finds the project root automatically
python -m level_editor --project ..       # or point at it explicitly
python -m level_editor --level ../Frontend/levels/demo.lua
python -m level_editor --lint             # headless checks, non-zero exit on error
python -m level_editor --system-theme     # use the desktop theme, not the dark one
python -m level_editor.tests.run_tests    # self-tests, no Qt required
```

Requires `PyQt6`. `--lint` and the tests need only the standard library, so they
work on the handheld and in CI.

## Viewport

| Input | Action |
|---|---|
| Click a prefab in the palette, then click the canvas | Place it |
| Shift-click while placing | Keep placing |
| `Esc` | Cancel placement |
| Left drag on an object | Move it (snapped) |
| Left drag on empty space | Rubber-band select |
| Shift/Ctrl click | Add to or remove from the selection |
| Middle or right drag | Pan |
| Wheel | Zoom about the cursor |
| Drag the dot on the stalk | Rotate, in 15-degree steps while snap is on |
| Arrows | Nudge by the snap step; hold Shift for 1 px |
| `Del` | Delete |
| `Ctrl+D` | Duplicate |
| `F` | Frame the selection, or the screen if nothing is selected |
| `Ctrl+P` | Play this level |

Colours follow `debug_light_renderer.lua`, so the editor and the in-game debug
overlay agree at a glance: yellow mirror, blue glass, red absorber, white inert.
Collider outlines are green for dynamic bodies and blue for static ones. A red
cross means the prefab named by that object is not in `definitions.lua`.

The `320 x 240` frame is the screen the game actually renders. There is no
camera in the engine, so anything outside that rectangle never appears. The
spinners in the toolbar change it if you want to design against a different
resolution; they default to whatever `Libraries/renderer/screen.lua` declares.

## Defaults and overrides

Every field in the inspector shows the value the engine would end up using.
A field the level file does not touch is muted and reads through to the prefab —
change the prefab later and this object follows. Edit it and it turns amber,
its revert arrow lights up, and the level file pins it from then on.

That distinction is the whole point of the panel, because `Prefab.Instantiate`
merges `entry.components[Type]` over the prefab's args key by key. An override
that happens to equal the prefab value is a no-op that only makes the file
noisier, so setting a field back to the prefab value deletes the key rather than
writing it out.

Light segments are read-only here. Editing a mirror's surface is a prefab
decision that should apply everywhere the prefab is used; doing it per instance
forks one mirror into seven slightly different mirrors, which is the exact
failure a prefab system exists to prevent. Use `Tools/prefab_editor`.

## Draw order

The object list is the draw order. `Scene:Draw` walks `scene.objects` with
`ipairs`, so entries lower in the list paint on top, and Raise/Lower is the only
layering control the engine has. An object with overrides is marked `*`.

(Component order *within* an object is not controllable from anywhere:
`Object:AddComponent` keys `self.components` by `tostring(component)` and
`Object:Draw` iterates with `pairs`.)

## Joints

`HingeJoint` is the one component that belongs in the level rather than in a
prefab: it needs a live object reference that only `Level.load` can resolve from
`extraComponents` + `connectedObjectId`. A prefab-level `HingeJoint` fails the
assert in `OnAttach`.

Add one from the inspector, pick the target from the dropdown — it lists the ids
in this level — and drag the pink crosshair in the viewport to place the anchor.
The anchor is in **world** pixels, not object-local, which is the single easiest
thing to get wrong when writing the joint by hand.

## Light preview

`preview/scene_light.py` collects every `LightCollider` in the level into one
world-space segment list, exactly as `LightWorld` accumulates them at runtime,
then traces a fan from every `LightSource` through all of them.
`preview/raytrace.py` is a line-for-line port of `ray_math.lua`,
`LightWorld.raycast` and `LightSource:castRay`, epsilon and normal-flipping rule
included, and the godray fills reproduce `GodrayRenderer:drawQuadPair`.

Detectors draw as a ring, filled green when the current solution actually lands
on one of their segments — the same test `LightWorld.resolveDetectors` does.

Solving is cached and only redone when the level changes, so dragging a mirror
across the room re-traces once per frame rather than once per mouse event.
A budget of 4000 rays caps a room full of high-`rayCount` sources; past it a
source simply does not light rather than stalling the window.

## Checks

The lint panel encodes things you would otherwise find only by running the game.
Errors are the cases the engine asserts on — the level will not load:

* an unknown prefab name (`Prefab.Instantiate` asserts);
* a duplicate `id` — `Level.load` builds `objectsById` by assignment, so the
  second entry silently wins and any joint pointing there attaches to the wrong
  object;
* a `HingeJoint` with no `connectedObjectId`, a dangling one, a missing anchor,
  or either end lacking a `RigidBody`;
* an `extraComponents` type missing from `component_registry.lua`;
* a resolved `rayCount` below 2, which divides by zero in `LightSource:Update`.

Warnings are the expensive ones, because nothing tells you at runtime:

* an override for a component the prefab does not declare — `mergeArgs` only
  walks the prefab's own components, so the whole block is dropped on the floor;
* an override key no component constructor reads;
* a resolved collider outside Box2D's tuned 0.1–10 m band, which is what makes
  bodies rest slightly above the floor;
* a moving body carrying light segments without `dynamic = true`, whose surface
  freezes at spawn while the body falls;
* a `GodrayRenderer` with no `LightSource` beside it;
* a fractional position, which at 320x240 is a shimmering half-pixel seam.

Double-click a row to select and frame the object.

## File handling

Level files are read and written directly, with the same restricted-subset
parser the prefab editor uses: table constructors, numbers, strings, booleans,
`Vector.new(x, y)`, `math.pi`, `math.rad(x)` and simple arithmetic. Anything
else raises a `LuaSyntaxError` and the file refuses to load, rather than loading
partially and silently deleting what it could not represent on the next save.

Three things survive a round trip: expressions (`rotation = math.pi / 6` comes
back as written, not as `0.5235987755982988`), comments, and `Vector.new(x, y)`
versus `{ x = ..., y = ... }`. Moving an object with the mouse does replace its
expression with a literal, which is correct — the number no longer means what
the source said.

Save shows a unified diff first and keeps the previous version as `.bak`.

The emitted array is one indented block per entry rather than the run-on
`{{ ... }, { ... }}` style currently in `demo.lua`. The first save reformats;
after that a two-pixel move is a two-line diff.

## Play

`Ctrl+P` launches LOVE with `RAY_LEVEL` set to the module path of the level you
are editing. For that to do anything, `main.lua` has to read it:

```lua
Level.load(os.getenv('RAY_LEVEL') or 'Frontend.levels.demo', scene)
```

The editor checks whether that line is there and says so if it is not. It
prefers `love` on `PATH`; `runtime/love` is the aarch64 handheld binary the
deploy script bundles and will not run on a desktop.

## Extending it

`model/schema.py` is the single source of truth, as in the prefab editor: adding
a component to the engine means adding one `ComponentSpec` there and the
inspector rows, defaults and lint rules follow.

`model/level.py` is where to start reading. `resolve(obj, library)` produces the
effective `Prefab` the engine would build for one entry, and everything else —
the viewport, the raytracer, the inspector, the lint — is written against that
one function.

```
model/level.py        LevelObject / Level, override storage, resolve()
model/document.py     snapshot undo, save, diff
model/library.py      the prefab side, read-only
model/schema.py       component definitions
model/project.py      project discovery, screen size, level discovery
model/sprites.py      sprite footprint and object extents
luaio/reader.py       restricted-subset Lua parser
luaio/level_writer.py level emitter
preview/raytrace.py   engine-parity light propagation
preview/scene_light.py whole-level solve
ui/viewport.py        canvas, placement, selection, gizmos
ui/inspector.py       transform, overrides, extra components
ui/main_window.py     layout and actions
validate/lint.py      the checks
tests/run_tests.py    self-tests
```

## What it will not do

Multi-select edits the transform of every selected object but shows the
inspector for the first one only.

There is no level metadata — no name, spawn point, or bounds — because
`Level.load` reads a bare array and adding a wrapper table would break it. If
you want metadata, that is an engine change first.

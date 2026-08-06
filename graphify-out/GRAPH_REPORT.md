# Graph Report - Ray_005  (2026-08-05)

## Corpus Check
- 57 files · ~20,820 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 589 nodes · 1183 edges · 34 communities (29 shown, 5 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 68 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `66de874f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.lua
- light_world.lua
- vector.lua
- component.lua
- Viewport
- object.lua
- fields.py
- light_collider.lua
- Project README
- LuaReader
- MainWindow
- SegmentTable
- raytrace.py
- Vec2
- run_tests.py
- Project
- writer.py
- library.py
- lint.py
- Document
- main_window.py
- RAY prefab editor
- light_source.lua
- schema.py
- Prefab
- Field
- godray_renderer.lua

## God Nodes (most connected - your core abstractions)
1. `Viewport` - 49 edges
2. `MainWindow` - 36 edges
3. `Vec2` - 32 edges
4. `V` - 32 edges
5. `LuaReader` - 26 edges
6. `SegmentTable` - 21 edges
7. `LuaSyntaxError` - 18 edges
8. `Document` - 16 edges
9. `Project` - 16 edges
10. `Inspector` - 16 edges

## Surprising Connections (you probably didn't know these)
- `love.load()` --calls--> `Prefab.Register()`  [INFERRED]
  main.lua → Libraries/universal/prefab.lua
- `love.load()` --calls--> `Scene.new()`  [INFERRED]
  main.lua → Libraries/universal/scene.lua
- `HingeJoint.new()` --calls--> `Component.new()`  [INFERRED]
  Libraries/physics/hinge_joint.lua → Libraries/universal/component.lua
- `Anchor.new()` --calls--> `RigidBody.new()`  [INFERRED]
  Frontend/prefabs/pivots/anchor.lua → Libraries/physics/rigid_body.lua
- `Box.new()` --calls--> `RigidBody.new()`  [INFERRED]
  Frontend/prefabs/tiles/box.lua → Libraries/physics/rigid_body.lua

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Light Engine Test Sprite Set** — resources_sprites_test_box_box_sprite, resources_sprites_test_lense_lens_sprite, resources_sprites_test_mirror_mirror_sprite [INFERRED 0.75]

## Communities (34 total, 5 thin omitted)

### Community 0 - "main.lua"
Cohesion: 0.07
Nodes (21): LightWorld.resolveDetectors(), HingeJoint.new(), World.init(), World.reset(), World.toMeters(), World.toPixels(), World.update(), Screen.beginDraw() (+13 more)

### Community 1 - "light_world.lua"
Cohesion: 0.28
Nodes (4): LightDetector:OnAttach(), LightDetector:OnDestroy(), LightWorld.registerDetector(), LightWorld.unregisterDetector()

### Community 2 - "vector.lua"
Cohesion: 0.25
Nodes (5): Vector.__add(), Vector.__mul(), Vector.new(), Vector:normalized(), Vector.__sub()

### Community 3 - "component.lua"
Cohesion: 0.15
Nodes (5): LightCollider.new(), LightDetector.new(), LightSource.new(), DebugLightRenderer.new(), Component.new()

### Community 4 - "Viewport"
Cohesion: 0.07
Nodes (12): Minimal 2D vector matching Libraries/transform/vector.lua., V, Handle, QWidget, Zoom and centre so the prefab's extents fill the view., Resize about the opposite edge, so that edge stays put., Mirrors GodrayRenderer:drawQuadPair, including its recursion., A draggable dot in world space. (+4 more)

### Community 5 - "object.lua"
Cohesion: 0.07
Nodes (9): Anchor.new(), Box.new(), RigidBody.new(), RigidBody:OnAttach(), World.get(), SpriteRenderer.new(), Rotation.new(), Transform.new() (+1 more)

### Community 6 - "fields.py"
Cohesion: 0.07
Nodes (18): BooleanField, build_field(), ColorField, EnumField, FieldWidget, NumberField, OptionalNumberField, PathField (+10 more)

### Community 7 - "light_collider.lua"
Cohesion: 0.18
Nodes (8): LightCollider:OnAttach(), LightCollider:OnDestroy(), LightCollider:syncSegments(), LightWorld.registerSegments(), LightWorld.unregisterSegments(), Box Sprite, Lens Test Sprite, Mirror Test Sprite

### Community 10 - "LuaReader"
Cohesion: 0.09
Nodes (17): float, _decode_number(), _decode_string(), LuaReader, _plain_number_text(), Skip leading `local x = require(...)` lines and parse `return <value>`., The text a bare literal would have produced, used to decide if src matters., Return (tokens, comments) where comments maps token index -> comment text. (+9 more)

### Community 11 - "MainWindow"
Cohesion: 0.10
Nodes (6): QDialog, QMainWindow, DiffDialog, MainWindow, Shows what saving would change before it touches the file., Levels reference prefabs by string; renaming breaks them silently.

### Community 12 - "SegmentTable"
Cohesion: 0.11
Nodes (8): QFrame, ComponentCard, Inspector, QWidget, _warning(), material_label(), QWidget, SegmentTable

### Community 13 - "raytrace.py"
Cohesion: 0.12
Nodes (19): cast_fan(), cast_ray(), A faithful Python port of the engine's light propagation. This mirrors, line…, Ray/segment intersection. Returns (t, point, normal) or None., Closest hit among `segments`, matching LightWorld.raycast., Recursive ray propagation, matching LightSource:castRay., The full fan a LightSource emits in one frame, matching LightSource:Update., Build world-space Segments from a prefab's LightCollider component. Mirrors… (+11 more)

### Community 14 - "Vec2"
Cohesion: 0.13
Nodes (14): Value types shared by the Lua reader and writer. The point of `Num` is source…, A 2D value written either as `Vector.new(x, y)` or as `{ x = ..., y = ... }`.…, Vec2, fit_collider_to_sprite(), new_segment(), One-click derivations between components. These exist because doing them by…, A fresh horizontal segment, placed below the previous one if given., The on-screen pixel size of a SpriteRenderer, or None if unknowable. (+6 more)

### Community 15 - "run_tests.py"
Cohesion: 0.23
Nodes (19): parse(), parse_file(), A parser for the data-only subset of Lua used by `definitions.lua`.…, Parse a Lua data module, returning the value of its `return` statement., library_from_table(), A brand-new component holding only the engine defaults., check(), main() (+11 more)

### Community 16 - "Project"
Cohesion: 0.14
Nodes (9): main(), Entry point. python -m prefab_editor # discover the project, open the GUI…, _resolve_project(), run_lint(), Project, Walk upwards from `start` looking for the project root., Component names present in component_registry.lua., Every image under Resources/, as project-relative posix paths. (+1 more)

### Community 17 - "writer.py"
Cohesion: 0.22
Nodes (18): num_src(), Return the preserved source for `value`, or None., _emit_args(), _emit_comment(), _emit_segments(), format_color(), format_number(), format_string() (+10 more)

### Community 18 - "library.py"
Cohesion: 0.22
Nodes (7): Component, component_from_table(), _convert_segments(), _convert_value(), prefab_from_table(), In-memory model of `definitions.lua`. `explicit` on a Component is what keeps…, Coerce a parsed Lua value into what the schema says the field holds.

### Community 19 - "lint.py"
Cohesion: 0.26
Nodes (12): _check_body(), _check_component_set(), _check_cross_component(), _check_light_collider(), _check_light_source(), _check_sprite(), _image_size(), Issue (+4 more)

### Community 21 - "main_window.py"
Cohesion: 0.21
Nodes (4): Editing session state: the library, the file it came from, and undo history.…, PrefabLibrary, Locates the RAY project on disk and reads the few facts the editor needs.…, Application shell: prefab list, viewport, inspector, lint dock, save flow.

### Community 22 - "RAY prefab editor"
Cohesion: 0.20
Nodes (9): Checks, Extending it, File handling, Layout, Light preview, RAY prefab editor, Running, Viewport (+1 more)

### Community 23 - "light_source.lua"
Cohesion: 0.31
Nodes (6): LightSource:castRay(), LightSource:Update(), LightWorld.raycast(), RayMath.reflect(), RayMath.refract(), RayMath.segmentIntersect()

### Community 24 - "schema.py"
Cohesion: 0.25
Nodes (4): prefab_component_types(), The single source of truth for what a component looks like. Every entry here…, Component types that may legally appear inside a prefab definition., spec_for()

## Ambiguous Edges - Review These
- `light_collider.lua` → `Box Sprite`  [AMBIGUOUS]
  Resources/sprites/test/box.png · relation: conceptually_related_to

## Knowledge Gaps
- **10 isolated node(s):** `Running`, `Viewport`, `What it will not do`, `File handling`, `Checks` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `light_collider.lua` and `Box Sprite`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Vec2` connect `Vec2` to `Viewport`, `fields.py`, `LuaReader`, `SegmentTable`, `run_tests.py`, `writer.py`, `library.py`, `schema.py`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `Viewport` connect `Viewport` to `MainWindow`, `main_window.py`, `Vec2`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `Project`, `Viewport`, `SegmentTable`, `main_window.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Viewport` (e.g. with `DiffDialog` and `MainWindow`) actually correct?**
  _`Viewport` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MainWindow` (e.g. with `Inspector` and `Viewport`) actually correct?**
  _`MainWindow` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Vec2` (e.g. with `LuaReader` and `_Token`) actually correct?**
  _`Vec2` has 2 INFERRED edges - model-reasoned connections that need verification._
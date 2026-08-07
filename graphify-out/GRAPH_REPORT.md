# Graph Report - Ray_005  (2026-08-06)

## Corpus Check
- 58 files · ~21,482 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 599 nodes · 1200 edges · 29 communities (26 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bc0d7531`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.lua
- light_world.lua
- vector.lua
- Component.new
- Viewport
- object.lua
- fields.py
- light_collider.lua
- Project README
- LuaReader
- MainWindow
- Vec2
- raytrace.py
- Inspector
- run_tests.py
- Project
- component.lua
- schema.py
- Document
- RAY prefab editor
- light_source.lua
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
- `love.load()` --calls--> `Scene.new()`  [INFERRED]
  main.lua → Libraries/universal/scene.lua
- `love.load()` --calls--> `Prefab.Register()`  [INFERRED]
  main.lua → Libraries/universal/prefab.lua
- `love.update()` --calls--> `LightWorld.resolveDetectors()`  [INFERRED]
  main.lua → Libraries/light_engine/light_world.lua
- `love.load()` --calls--> `World.init()`  [INFERRED]
  main.lua → Libraries/physics/world.lua
- `love.update()` --calls--> `World.update()`  [INFERRED]
  main.lua → Libraries/physics/world.lua

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Light Engine Test Sprite Set** — resources_sprites_test_box_box_sprite, resources_sprites_test_lense_lens_sprite, resources_sprites_test_mirror_mirror_sprite [INFERRED 0.75]

## Communities (29 total, 3 thin omitted)

### Community 0 - "main.lua"
Cohesion: 0.08
Nodes (25): LightWorld.resolveDetectors(), beginContact(), endContact(), World.init(), World.reset(), World.toMeters(), World.toPixels(), World.update() (+17 more)

### Community 1 - "light_world.lua"
Cohesion: 0.22
Nodes (6): LightCollider:OnDestroy(), LightDetector:OnAttach(), LightDetector:OnDestroy(), LightWorld.registerDetector(), LightWorld.unregisterDetector(), LightWorld.unregisterSegments()

### Community 2 - "vector.lua"
Cohesion: 0.25
Nodes (5): Vector.__add(), Vector.__mul(), Vector.new(), Vector:normalized(), Vector.__sub()

### Community 3 - "Component.new"
Cohesion: 0.17
Nodes (5): LightCollider.new(), LightDetector.new(), HingeJoint.new(), DebugLightRenderer.new(), Component.new()

### Community 4 - "Viewport"
Cohesion: 0.07
Nodes (11): Minimal 2D vector matching Libraries/transform/vector.lua., V, Handle, QWidget, Zoom and centre so the prefab's extents fill the view., Resize about the opposite edge, so that edge stays put., Mirrors GodrayRenderer:drawQuadPair, including its recursion., A draggable dot in world space. (+3 more)

### Community 5 - "object.lua"
Cohesion: 0.07
Nodes (9): Anchor.new(), Box.new(), RigidBody.new(), RigidBody:OnAttach(), World.get(), SpriteRenderer.new(), Rotation.new(), Transform.new() (+1 more)

### Community 6 - "fields.py"
Cohesion: 0.07
Nodes (18): BooleanField, build_field(), ColorField, EnumField, FieldWidget, NumberField, OptionalNumberField, PathField (+10 more)

### Community 7 - "light_collider.lua"
Cohesion: 0.22
Nodes (6): LightCollider:OnAttach(), LightCollider:syncSegments(), LightWorld.registerSegments(), Box Sprite, Lens Test Sprite, Mirror Test Sprite

### Community 10 - "LuaReader"
Cohesion: 0.09
Nodes (18): float, _decode_number(), _decode_string(), LuaReader, _plain_number_text(), A parser for the data-only subset of Lua used by `definitions.lua`.…, Skip leading `local x = require(...)` lines and parse `return <value>`., The text a bare literal would have produced, used to decide if src matters. (+10 more)

### Community 11 - "MainWindow"
Cohesion: 0.11
Nodes (6): QDialog, QMainWindow, DiffDialog, MainWindow, Shows what saving would change before it touches the file., Levels reference prefabs by string; renaming breaks them silently.

### Community 12 - "Vec2"
Cohesion: 0.13
Nodes (10): A 2D value written either as `Vector.new(x, y)` or as `{ x = ..., y = ... }`.…, Vec2, new_segment(), A fresh horizontal segment, placed below the previous one if given., Emit light segments tracing the RigidBody rectangle's edges. `faces` is "all"…, segments_from_collider(), material_label(), QWidget (+2 more)

### Community 13 - "raytrace.py"
Cohesion: 0.12
Nodes (19): cast_fan(), cast_ray(), A faithful Python port of the engine's light propagation. This mirrors, line…, Ray/segment intersection. Returns (t, point, normal) or None., Closest hit among `segments`, matching LightWorld.raycast., Recursive ray propagation, matching LightSource:castRay., The full fan a LightSource emits in one frame, matching LightSource:Update., Build world-space Segments from a prefab's LightCollider component. Mirrors… (+11 more)

### Community 14 - "Inspector"
Cohesion: 0.16
Nodes (5): QFrame, ComponentCard, Inspector, QWidget, _warning()

### Community 15 - "run_tests.py"
Cohesion: 0.06
Nodes (46): parse(), parse_file(), Parse a Lua data module, returning the value of its `return` statement., num_src(), Return the preserved source for `value`, or None., _emit_args(), _emit_comment(), _emit_segments() (+38 more)

### Community 16 - "Project"
Cohesion: 0.13
Nodes (10): main(), Entry point. python -m prefab_editor # discover the project, open the GUI…, _resolve_project(), run_lint(), Project, Locates the RAY project on disk and reads the few facts the editor needs.…, Walk upwards from `start` looking for the project root., Component names present in component_registry.lua. (+2 more)

### Community 17 - "component.lua"
Cohesion: 0.19
Nodes (5): Component:Subscribe(), Component:Unsubscribe(), Component:UnsubscribeAll(), EventBus.subscribe(), EventBus.unsubscribe()

### Community 19 - "schema.py"
Cohesion: 0.07
Nodes (27): Value types shared by the Lua reader and writer. The point of `Num` is source…, fit_collider_to_sprite(), One-click derivations between components. These exist because doing them by…, The on-screen pixel size of a SpriteRenderer, or None if unknowable., Resize the RigidBody rectangle to match the drawn sprite footprint., sprite_drawn_size(), ComponentSpec, Field (+19 more)

### Community 22 - "RAY prefab editor"
Cohesion: 0.20
Nodes (9): Checks, Extending it, File handling, Layout, Light preview, RAY prefab editor, Running, Viewport (+1 more)

### Community 23 - "light_source.lua"
Cohesion: 0.27
Nodes (7): LightSource:castRay(), LightSource.new(), LightSource:Update(), LightWorld.raycast(), RayMath.reflect(), RayMath.refract(), RayMath.segmentIntersect()

## Ambiguous Edges - Review These
- `light_collider.lua` → `Box Sprite`  [AMBIGUOUS]
  Resources/sprites/test/box.png · relation: conceptually_related_to

## Knowledge Gaps
- **10 isolated node(s):** `Running`, `Viewport`, `What it will not do`, `File handling`, `Checks` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `light_collider.lua` and `Box Sprite`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Vec2` connect `Vec2` to `Viewport`, `fields.py`, `LuaReader`, `run_tests.py`, `schema.py`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `Viewport` connect `Viewport` to `MainWindow`, `schema.py`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `Viewport`, `Inspector`, `run_tests.py`, `Project`, `schema.py`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Viewport` (e.g. with `DiffDialog` and `MainWindow`) actually correct?**
  _`Viewport` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MainWindow` (e.g. with `Inspector` and `Viewport`) actually correct?**
  _`MainWindow` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Vec2` (e.g. with `LuaReader` and `_Token`) actually correct?**
  _`Vec2` has 2 INFERRED edges - model-reasoned connections that need verification._
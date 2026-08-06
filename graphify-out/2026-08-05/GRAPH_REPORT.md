# Graph Report - Ray_005  (2026-08-05)

## Corpus Check
- 32 files · ~4,743 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 140 nodes · 206 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 76% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 48 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4b177e69`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.lua
- light_world.lua
- vector.lua
- Light Rendering & Components
- Component.new
- object.lua
- rigid_body.lua
- light_collider.lua
- Project README

## God Nodes (most connected - your core abstractions)
1. `Vector.new()` - 13 edges
2. `Component.new()` - 9 edges
3. `love.load()` - 6 edges
4. `Object.new()` - 5 edges
5. `RigidBody.new()` - 4 edges
6. `Box.new()` - 4 edges
7. `LightSource:castRay()` - 4 edges
8. `Transform.new()` - 4 edges
9. `Level.load()` - 4 edges
10. `Prefab.Instantiate()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Anchor.new()` --calls--> `RigidBody.new()`  [INFERRED]
  Frontend/prefabs/pivots/anchor.lua → Libraries/physics/rigid_body.lua
- `love.load()` --calls--> `World.init()`  [INFERRED]
  main.lua → Libraries/physics/world.lua
- `Box.new()` --calls--> `Object.new()`  [INFERRED]
  Frontend/prefabs/tiles/box.lua → Libraries/universal/object.lua
- `love.load()` --calls--> `Prefab.Register()`  [INFERRED]
  main.lua → Libraries/universal/prefab.lua
- `love.load()` --calls--> `Scene.new()`  [INFERRED]
  main.lua → Libraries/universal/scene.lua

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Light Engine Test Sprite Set** — resources_sprites_test_box_box_sprite, resources_sprites_test_lense_lens_sprite, resources_sprites_test_mirror_mirror_sprite [INFERRED 0.75]

## Communities (11 total, 2 thin omitted)

### Community 0 - "main.lua"
Cohesion: 0.15
Nodes (13): Screen.beginDraw(), Screen.endDraw(), Screen.init(), Screen.updateScale(), Level.load(), toVector(), mergeArgs(), Prefab.Instantiate() (+5 more)

### Community 1 - "light_world.lua"
Cohesion: 0.18
Nodes (8): LightDetector.new(), LightDetector:OnAttach(), LightDetector:OnDestroy(), LightWorld.registerDetector(), LightWorld.resolveDetectors(), LightWorld.unregisterDetector(), World.update(), love.update()

### Community 2 - "vector.lua"
Cohesion: 0.14
Nodes (12): LightSource:castRay(), LightSource.new(), LightSource:Update(), LightWorld.raycast(), RayMath.reflect(), RayMath.refract(), RayMath.segmentIntersect(), Vector.__add() (+4 more)

### Community 4 - "Component.new"
Cohesion: 0.15
Nodes (5): Box.new(), HingeJoint.new(), RigidBody.new(), SpriteRenderer.new(), Component.new()

### Community 5 - "object.lua"
Cohesion: 0.13
Nodes (4): Anchor.new(), Rotation.new(), Transform.new(), Object.new()

### Community 6 - "rigid_body.lua"
Cohesion: 0.18
Nodes (6): RigidBody:OnAttach(), World.get(), World.init(), World.reset(), World.toMeters(), World.toPixels()

### Community 7 - "light_collider.lua"
Cohesion: 0.17
Nodes (9): LightCollider.new(), LightCollider:OnAttach(), LightCollider:OnDestroy(), LightCollider:syncSegments(), LightWorld.registerSegments(), LightWorld.unregisterSegments(), Box Sprite, Lens Test Sprite (+1 more)

## Ambiguous Edges - Review These
- `light_collider.lua` → `Box Sprite`  [AMBIGUOUS]
  Resources/sprites/test/box.png · relation: conceptually_related_to

## Knowledge Gaps
- **2 isolated node(s):** `RAY_Vertical_Slice`, `Mirror Test Sprite`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `light_collider.lua` and `Box Sprite`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Component.new()` connect `Component.new` to `light_world.lua`, `vector.lua`, `Light Rendering & Components`, `light_collider.lua`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `Vector.new()` connect `vector.lua` to `main.lua`, `object.lua`, `rigid_body.lua`, `light_collider.lua`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `RigidBody.new()` connect `Component.new` to `object.lua`, `rigid_body.lua`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `Vector.new()` (e.g. with `LightCollider:OnAttach()` and `LightCollider:syncSegments()`) actually correct?**
  _`Vector.new()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Component.new()` (e.g. with `GodrayRenderer.new()` and `LightCollider.new()`) actually correct?**
  _`Component.new()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `love.load()` (e.g. with `World.init()` and `Screen.init()`) actually correct?**
  _`love.load()` has 5 INFERRED edges - model-reasoned connections that need verification._
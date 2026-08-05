# Graph Report - .  (2026-08-05)

## Corpus Check
- Corpus is ~5,165 words - fits in a single context window. You may not need a graph.

## Summary
- 151 nodes · 225 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 76% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 52 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Scene & Prefab Bootstrap
- Light Engine Runtime
- Level Zones & Vector Math
- Light Rendering & Components
- Tile Prefabs & Sprite Rendering
- Transform & Object Core
- Physics World & Joints
- Ray Casting & Optics Math
- Project README

## God Nodes (most connected - your core abstractions)
1. `Vector.new()` - 14 edges
2. `Component.new()` - 9 edges
3. `love.load()` - 6 edges
4. `Object.new()` - 5 edges
5. `Box.new()` - 4 edges
6. `LightSource:castRay()` - 4 edges
7. `RigidBody.new()` - 4 edges
8. `World.toMeters()` - 4 edges
9. `Transform.new()` - 4 edges
10. `Level.load()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Anchor.new()` --calls--> `Object.new()`  [INFERRED]
  Frontend/prefabs/pivots/anchor.lua → Libraries/universal/object.lua
- `Box.new()` --calls--> `Object.new()`  [INFERRED]
  Frontend/prefabs/tiles/box.lua → Libraries/universal/object.lua
- `love.load()` --calls--> `World.init()`  [INFERRED]
  main.lua → Libraries/physics/world.lua
- `love.load()` --calls--> `Prefab.Register()`  [INFERRED]
  main.lua → Libraries/universal/prefab.lua
- `love.load()` --calls--> `Scene.new()`  [INFERRED]
  main.lua → Libraries/universal/scene.lua

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Light Engine Test Sprite Set** — resources_sprites_test_box_box_sprite, resources_sprites_test_lense_lens_sprite, resources_sprites_test_mirror_mirror_sprite [INFERRED 0.75]

## Communities (10 total, 1 thin omitted)

### Community 0 - "Scene & Prefab Bootstrap"
Cohesion: 0.11
Nodes (13): Screen.beginDraw(), Screen.endDraw(), Screen.init(), Screen.updateScale(), Level.load(), toVector(), mergeArgs(), Prefab.Instantiate() (+5 more)

### Community 1 - "Light Engine Runtime"
Cohesion: 0.10
Nodes (16): LightCollider:OnAttach(), LightCollider:OnDestroy(), LightCollider:syncSegments(), LightDetector.new(), LightDetector:OnAttach(), LightDetector:OnDestroy(), LightWorld.registerDetector(), LightWorld.registerSegments() (+8 more)

### Community 2 - "Level Zones & Vector Math"
Cohesion: 0.10
Nodes (7): RigidBody:Update(), World.toPixels(), Vector.__add(), Vector.__mul(), Vector.new(), Vector:normalized(), Vector.__sub()

### Community 3 - "Light Rendering & Components"
Cohesion: 0.12
Nodes (4): GodrayRenderer.new(), LightCollider.new(), DebugLightRenderer.new(), Component.new()

### Community 4 - "Tile Prefabs & Sprite Rendering"
Cohesion: 0.14
Nodes (4): Anchor.new(), Box.new(), RigidBody.new(), SpriteRenderer.new()

### Community 5 - "Transform & Object Core"
Cohesion: 0.15
Nodes (3): Rotation.new(), Transform.new(), Object.new()

### Community 6 - "Physics World & Joints"
Cohesion: 0.24
Nodes (7): HingeJoint.new(), HingeJoint:OnAttach(), RigidBody:OnAttach(), World.get(), World.init(), World.reset(), World.toMeters()

### Community 7 - "Ray Casting & Optics Math"
Cohesion: 0.27
Nodes (7): LightSource:castRay(), LightSource.new(), LightSource:Update(), LightWorld.raycast(), RayMath.reflect(), RayMath.refract(), RayMath.segmentIntersect()

## Ambiguous Edges - Review These
- `light_collider.lua` → `Box Sprite`  [AMBIGUOUS]
  Resources/sprites/test/box.png · relation: conceptually_related_to

## Knowledge Gaps
- **2 isolated node(s):** `RAY_Vertical_Slice`, `Mirror Test Sprite`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `light_collider.lua` and `Box Sprite`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Vector.new()` connect `Level Zones & Vector Math` to `Scene & Prefab Bootstrap`, `Light Engine Runtime`, `Transform & Object Core`, `Physics World & Joints`, `Ray Casting & Optics Math`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `Component.new()` connect `Light Rendering & Components` to `Light Engine Runtime`, `Tile Prefabs & Sprite Rendering`, `Physics World & Joints`, `Ray Casting & Optics Math`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `love.load()` connect `Scene & Prefab Bootstrap` to `Physics World & Joints`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `Vector.new()` (e.g. with `LightCollider:OnAttach()` and `LightCollider:syncSegments()`) actually correct?**
  _`Vector.new()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Component.new()` (e.g. with `GodrayRenderer.new()` and `LightCollider.new()`) actually correct?**
  _`Component.new()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `love.load()` (e.g. with `World.init()` and `Screen.init()`) actually correct?**
  _`love.load()` has 5 INFERRED edges - model-reasoned connections that need verification._
# engine_tests

Headless regression checks that run outside LOVE, on plain `lua5.1`, against a
minimal `love` stand-in (`love_mock.lua`). Optional -- delete this folder if you
do not want it; nothing in the game requires it.

    lua5.1 Tools/engine_tests/level_manager_test.lua
    lua5.1 Tools/engine_tests/tilemap_test.lua
    lua5.1 Tools/engine_tests/door_test.lua

`level_manager_test.lua` boots the engine the way `main.lua` does, runs the
splash through to the demo level, reloads, and fully unloads -- asserting at each
step that Box2D bodies and joints, light-world registrations, level-scoped event
listeners and the level module itself are all released, and that nothing
accumulates across a switch.

`tilemap_test.lua` covers the `Tilemap` component: the row-major index formula
(which the level editor writes and the engine reads, so the two must agree), the
top-left origin `CellAt` depends on, and the SpriteBatch lifecycle -- allocated
once, rebuilt in place on an edit, released on destroy, and safe to release
twice.

`door_test.lua` covers the detector -> door -> next level chain against the real
`Frontend/levels/level`: the detector swapping sprite on the lit transition, the
door refusing to count as passable until the open clip has actually *finished*
(a door that reports itself open on frame one lets the player walk through a
shut door), a player already standing in the doorway when the puzzle is solved
still triggering, and the level switch leaving no bodies, segments or detectors
behind.

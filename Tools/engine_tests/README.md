# engine_tests

Headless regression checks that run outside LOVE, on plain `lua5.1`, against a
minimal `love` stand-in (`love_mock.lua`). Optional -- delete this folder if you
do not want it; nothing in the game requires it.

    lua5.1 Tools/engine_tests/level_manager_test.lua

`level_manager_test.lua` boots the engine the way `main.lua` does, runs the
splash through to the demo level, reloads, and fully unloads -- asserting at each
step that Box2D bodies and joints, light-world registrations, level-scoped event
listeners and the level module itself are all released, and that nothing
accumulates across a switch.

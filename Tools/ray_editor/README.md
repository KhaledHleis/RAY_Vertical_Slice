# ray_editor — level and prefab editing in one window

```
cd Tools
python -m ray_editor              # opens on the first level
python -m ray_editor --prefabs    # opens in prefab mode
python -m ray_editor --level ../Frontend/levels/demo.lua
python -m ray_editor --lint       # definitions.lua + every level, exit code for CI
```

Neither `level_editor/` nor `prefab_editor/` is replaced. The shell hosts both
existing `MainWindow`s in a stack; both still run standalone exactly as before.

## What the merge buys you

**One live library.** The prefab editor's document is the only owner of the
`PrefabLibrary`. Every switch back to level mode re-points the level viewport,
palette and inspector at it — so a collider you just resized, or a sprite you
just swapped, shows up under every instance in the level *before*
`definitions.lua` is saved. Re-pointing has to happen on every switch and not
once at startup, because undo in the prefab editor replaces `document.library`
wholesale with a deep copy.

**Two clicks to fix a prefab.** Double-click a palette entry or a hierarchy
row, or hit `Ctrl+E` with an object selected, and you land in the prefab editor
on that prefab. `F1` puts you back, level selection intact. Going the other
way, `Ctrl+Shift+E` (or double-clicking a prefab in the list) returns to the
level with that prefab armed for placement.

**One keyboard.** Both windows bound `Ctrl+S`, `Ctrl+Z`, `Ctrl+O`, `Ctrl+R`,
`Ctrl+Q`. Nested in one window Qt would call those ambiguous and fire neither,
so the duplicates are stripped from the children and re-bound on the shell,
dispatching to whichever mode is on screen. Everything that is not duplicated
(`Del`, `F`, `Ctrl+D`, `Ctrl+0`, `Ctrl+P`, `Ctrl+N`) is scoped to its own page
with `WidgetWithChildrenShortcut`, which is why the active viewport is given
focus on every switch.

| key | does |
| --- | --- |
| `F1` / `F2` | level mode / prefab mode |
| `Ctrl+E` | edit the selected object's prefab |
| `Ctrl+Shift+E` | back to the level, this prefab armed |
| `Ctrl+S` `Ctrl+Z` `Ctrl+Shift+Z` `Ctrl+O` `Ctrl+R` `Ctrl+L` | the active mode's save / undo / redo / open / reload / checks |

The title bar and status bar carry both documents' dirty state, and closing
asks about each one separately.

## One fix outside the shell

`luaio/writer.py` (identical in both editors, patched in both) raised
`cannot serialize ...` on any component arg the schema did not name — RAY's own
`definitions.lua` has an `animations = { idle = "PlayerIdle", ... }` map, so
`Document.modified` threw and the file could not be saved. There is now a
generic recursive emitter for tables, dicts and lists; round-tripping the real
`definitions.lua` is idempotent and both existing test suites still pass
(30 + 85 checks).

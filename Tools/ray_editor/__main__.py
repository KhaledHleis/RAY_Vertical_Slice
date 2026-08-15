"""Entry point for the unified RAY editor.

    python -m ray_editor                    # discover the project, open the GUI
    python -m ray_editor --project PATH     # point at it explicitly
    python -m ray_editor --level PATH       # open a specific level file
    python -m ray_editor --lint             # check prefabs and every level

Run it from `Tools/` (or anywhere: the sibling packages are added to sys.path
below, so `level_editor` and `prefab_editor` import either way).
"""

from __future__ import annotations

import argparse
import os
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from level_editor.model.project import Project  # noqa: E402


def _resolve_project(explicit):
    if explicit:
        project = Project(explicit)
        if not os.path.exists(project.definitions_path):
            print(f"error: no Frontend/prefabs/definitions.lua under {project.root}",
                  file=sys.stderr)
            return None
        return project

    for start in (os.getcwd(), _TOOLS):
        project = Project.discover(start)
        if project is not None:
            return project

    print("error: could not find the RAY project root (looked for main.lua, "
          "conf.lua and Libraries/universal/prefab.lua). Pass --project.",
          file=sys.stderr)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ray_editor")
    parser.add_argument("--project", help="path to the RAY project root")
    parser.add_argument("--level", help="level file to open")
    parser.add_argument("--prefabs", action="store_true",
                        help="start in prefab mode instead of level mode")
    parser.add_argument("--lint", action="store_true",
                        help="check definitions.lua and every level, then exit")
    parser.add_argument("--system-theme", action="store_true",
                        help="use the desktop theme instead of the built-in dark one")
    args = parser.parse_args(argv)

    project = _resolve_project(args.project)
    if project is None:
        return 2

    if args.lint:
        from level_editor.__main__ import run_lint as lint_levels
        from prefab_editor.__main__ import run_lint as lint_prefabs
        return max(lint_prefabs(project), lint_levels(project, args.level))

    from PyQt6.QtWidgets import QApplication

    from level_editor.ui.theme import apply_dark_theme

    from .shell import LEVEL, PREFAB, UnifiedWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("RAY editor")
    if not args.system_theme:
        apply_dark_theme(app)

    window = UnifiedWindow(project, args.level)
    window.set_mode(PREFAB if args.prefabs else LEVEL)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

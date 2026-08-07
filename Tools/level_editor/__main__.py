"""Entry point.

    python -m level_editor                     # discover the project, open the GUI
    python -m level_editor --project PATH      # point at it explicitly
    python -m level_editor --level PATH        # open a specific level file
    python -m level_editor --lint              # check every level, exit non-zero
    python -m level_editor.tests.run_tests     # self-tests, no Qt required
"""

from __future__ import annotations

import argparse
import os
import sys

from .model.project import Project


def _resolve_project(explicit):
    if explicit:
        project = Project(explicit)
        if not os.path.exists(project.definitions_path):
            print(f"error: no Frontend/prefabs/definitions.lua under {project.root}",
                  file=sys.stderr)
            return None
        return project

    here = os.path.dirname(os.path.abspath(__file__))
    for start in (os.getcwd(), here):
        project = Project.discover(start)
        if project is not None:
            return project

    print("error: could not find the RAY project root (looked for main.lua, "
          "conf.lua and Libraries/universal/prefab.lua). Pass --project.",
          file=sys.stderr)
    return None


def run_lint(project, only=None):
    from .luaio import reader
    from .luaio.types import LuaSyntaxError
    from .model.level import level_from_table
    from .model.library import library_from_table
    from .validate import lint

    try:
        library = library_from_table(reader.parse_file(project.definitions_path))
    except (LuaSyntaxError, ValueError) as error:
        print(f"parse error in {project.definitions_path}: {error}", file=sys.stderr)
        return 2

    paths = [only] if only else project.level_files()
    if not paths:
        print(f"no level files under {project.levels_path}")
        return 0

    worst = 0
    for path in paths:
        try:
            level = level_from_table(reader.parse_file(path))
        except (LuaSyntaxError, ValueError) as error:
            print(f"parse error in {path}: {error}", file=sys.stderr)
            worst = max(worst, 2)
            continue

        issues = lint.lint_level(level, library, project)
        if not issues:
            print(f"{path}: all clear")
            continue

        print(f"{path}:")
        for issue in issues:
            print(f"  {issue.severity:>7}  {issue.location():<28} {issue.message}")
            if issue.hint:
                print(f"  {'':>7}  {'':<28} -> {issue.hint}")
        if any(i.severity == lint.ERROR for i in issues):
            worst = max(worst, 1)

    return worst


def main(argv=None):
    parser = argparse.ArgumentParser(prog="level_editor")
    parser.add_argument("--project", help="path to the RAY project root")
    parser.add_argument("--level", help="level file to open")
    parser.add_argument("--lint", action="store_true",
                        help="check the level files and exit")
    parser.add_argument("--system-theme", action="store_true",
                        help="use the desktop theme instead of the built-in dark one")
    args = parser.parse_args(argv)

    project = _resolve_project(args.project)
    if project is None:
        return 2

    if args.lint:
        return run_lint(project, args.level)

    from PyQt6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    from .ui.theme import apply_dark_theme

    app = QApplication(sys.argv[:1])
    app.setApplicationName("RAY level editor")
    if not args.system_theme:
        apply_dark_theme(app)
    window = MainWindow(project, args.level)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

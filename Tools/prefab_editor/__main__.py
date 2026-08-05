"""Entry point.

    python -m prefab_editor                 # discover the project, open the GUI
    python -m prefab_editor --project PATH  # point at a project explicitly
    python -m prefab_editor --lint          # run the checks, print, exit non-zero
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


def run_lint(project):
    from .luaio import reader
    from .luaio.types import LuaSyntaxError
    from .model.library import library_from_table
    from .validate import lint

    try:
        library = library_from_table(reader.parse_file(project.definitions_path))
    except LuaSyntaxError as error:
        print(f"parse error in {project.definitions_path}: {error}", file=sys.stderr)
        return 2

    issues = lint.lint_library(library, project)
    if not issues:
        print(f"{project.definitions_path}: all clear")
        return 0

    for issue in issues:
        print(f"{issue.severity:>7}  {issue.location():<40} {issue.message}")
        if issue.hint:
            print(f"{'':>7}  {'':<40} -> {issue.hint}")

    errors = sum(1 for i in issues if i.severity == lint.ERROR)
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="prefab_editor")
    parser.add_argument("--project", help="path to the RAY project root")
    parser.add_argument("--lint", action="store_true",
                        help="run the checks on definitions.lua and exit")
    args = parser.parse_args(argv)

    project = _resolve_project(args.project)
    if project is None:
        return 2

    if args.lint:
        return run_lint(project)

    from PyQt6.QtWidgets import QApplication
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("RAY prefab editor")
    window = MainWindow(project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

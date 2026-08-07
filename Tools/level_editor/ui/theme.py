"""A dark palette, applied by default.

The canvas is dark because the game is dark, and a light chrome around it
skews every colour judgement you make about the level. Pass --system-theme
to opt out.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

WINDOW = QColor(35, 35, 41)
BASE = QColor(26, 26, 31)
ALTERNATE = QColor(42, 42, 50)
TEXT = QColor(220, 220, 228)
DISABLED = QColor(120, 120, 132)
HIGHLIGHT = QColor(255, 170, 60)
HIGHLIGHT_TEXT = QColor(24, 24, 28)


def apply_dark_theme(app):
    app.setStyle("Fusion")

    palette = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    palette.setColor(role.Window, WINDOW)
    palette.setColor(role.WindowText, TEXT)
    palette.setColor(role.Base, BASE)
    palette.setColor(role.AlternateBase, ALTERNATE)
    palette.setColor(role.ToolTipBase, ALTERNATE)
    palette.setColor(role.ToolTipText, TEXT)
    palette.setColor(role.Text, TEXT)
    palette.setColor(role.Button, WINDOW)
    palette.setColor(role.ButtonText, TEXT)
    palette.setColor(role.BrightText, Qt.GlobalColor.red)
    palette.setColor(role.Link, HIGHLIGHT)
    palette.setColor(role.Highlight, HIGHLIGHT)
    palette.setColor(role.HighlightedText, HIGHLIGHT_TEXT)

    for disabled_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, disabled_role, DISABLED)

    app.setPalette(palette)

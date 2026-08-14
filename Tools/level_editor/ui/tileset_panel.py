"""The tile palette: which map, which tileset, which tile, which tool.

Everything that decides *what* a brush stroke does lives here; the stroke itself
happens in the viewport. The split is the same one the prefab palette already
uses -- pick on the left, act on the canvas -- and it keeps the viewport free of
tileset bookkeeping.

The panel never edits tiles. It edits the object's other Tilemap arguments
(tileset, tile size, map size), and it emits `editStarted` before each of those
so the window can snapshot for undo, exactly like the inspector does.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QSpinBox, QToolButton, QVBoxLayout, QWidget)

from ..model import tilemap as tilemap_model

GRID = QColor(70, 70, 84)
SELECTION = QColor(255, 170, 60)
BACKDROP = QColor(26, 26, 31)

BRUSH = "brush"
RECT = "rect"
FILL = "fill"
ERASER = "eraser"
PICKER = "picker"

TOOLS = (
    (BRUSH, "Brush", "Paint single cells. Drag to paint a run."),
    (RECT, "Rect", "Drag a rectangle, painted on release."),
    (FILL, "Fill", "Flood fill the contiguous run of matching tiles."),
    (ERASER, "Eraser", "Paint cell 0 -- empty. Right-drag does this with any tool."),
    (PICKER, "Picker", "Adopt the tile under the cursor. Alt-click does this too."),
)


class TilesetView(QWidget):
    """The sheet itself, sliced on the tile grid, one cell selectable."""

    tileSelected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.pixmap = None
        self.tile_width = 16
        self.tile_height = 16
        self.zoom = 2
        self.selected = 1
        self.setMouseTracking(True)

    def set_tileset(self, absolute_path, tile_width, tile_height):
        self.tile_width = max(1, int(tile_width))
        self.tile_height = max(1, int(tile_height))
        if absolute_path and os.path.exists(absolute_path):
            pixmap = QPixmap(absolute_path)
            self.pixmap = None if pixmap.isNull() else pixmap
        else:
            self.pixmap = None
        self._resize_to_content()
        self.update()

    def set_zoom(self, zoom):
        self.zoom = max(1, int(zoom))
        self._resize_to_content()
        self.update()

    def set_selected(self, tile_id):
        self.selected = int(tile_id)
        self.update()

    def columns(self):
        if self.pixmap is None:
            return 0
        return max(1, self.pixmap.width() // self.tile_width)

    def rows(self):
        if self.pixmap is None:
            return 0
        return max(1, self.pixmap.height() // self.tile_height)

    def _resize_to_content(self):
        if self.pixmap is None:
            self.setMinimumSize(120, 160)
            return
        self.setMinimumSize(self.columns() * self.tile_width * self.zoom,
                            self.rows() * self.tile_height * self.zoom)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKDROP)

        if self.pixmap is None:
            painter.setPen(QPen(QColor(130, 130, 140)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No tileset")
            painter.end()
            return

        cell_w = self.tile_width * self.zoom
        cell_h = self.tile_height * self.zoom
        columns, rows = self.columns(), self.rows()

        # Nearest-neighbour: this is pixel art, and a smoothed palette makes
        # you pick tiles that look different from the ones the game draws.
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(0, 0, columns * cell_w, rows * cell_h, self.pixmap,
                           0, 0, columns * self.tile_width, rows * self.tile_height)

        painter.setPen(QPen(GRID, 1))
        for column in range(columns + 1):
            x = column * cell_w
            painter.drawLine(x, 0, x, rows * cell_h)
        for row in range(rows + 1):
            y = row * cell_h
            painter.drawLine(0, y, columns * cell_w, y)

        if self.selected >= 1:
            index = self.selected - 1
            column, row = index % columns, index // columns
            if row < rows:
                painter.setPen(QPen(SELECTION, 2))
                painter.drawRect(QRectF(column * cell_w + 1, row * cell_h + 1,
                                        cell_w - 2, cell_h - 2))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.pixmap is None:
            return
        cell_w = self.tile_width * self.zoom
        cell_h = self.tile_height * self.zoom
        column = int(event.position().x() // cell_w)
        row = int(event.position().y() // cell_h)
        if not (0 <= column < self.columns() and 0 <= row < self.rows()):
            return
        # 1-based, matching the engine: 0 is reserved for "no tile".
        self.set_selected(row * self.columns() + column + 1)
        self.tileSelected.emit(self.selected)


class TilesetPanel(QWidget):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    structureChanged = pyqtSignal()
    targetChanged = pyqtSignal(object)
    toolChanged = pyqtSignal(str)
    tileChanged = pyqtSignal(int)
    statusMessage = pyqtSignal(str)
    newTilemapRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.level = None
        self.library = None
        self.target = None
        self.tool = BRUSH
        self.tile_id = 1
        self._suspend = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # -- which map -----------------------------------------------------
        target_row = QHBoxLayout()
        self.target_box = QComboBox()
        self.target_box.setToolTip("Which tilemap object the brush writes into.")
        self.target_box.activated.connect(self._on_target_chosen)
        new_button = QPushButton("New")
        new_button.setToolTip("Add a Tilemap object at the top-left of the screen")
        new_button.clicked.connect(self.newTilemapRequested.emit)
        target_row.addWidget(QLabel("Map"))
        target_row.addWidget(self.target_box, 1)
        target_row.addWidget(new_button)
        layout.addLayout(target_row)

        # -- tools ---------------------------------------------------------
        tool_row = QHBoxLayout()
        tool_row.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for key, label, tip in TOOLS:
            button = QToolButton()
            button.setText(label)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setChecked(key == BRUSH)
            button.clicked.connect(lambda _c=False, k=key: self._on_tool(k))
            self.tool_group.addButton(button)
            tool_row.addWidget(button)
        tool_row.addStretch(1)
        layout.addLayout(tool_row)

        # -- settings ------------------------------------------------------
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        tileset_row = QHBoxLayout()
        tileset_row.setContentsMargins(0, 0, 0, 0)
        self.tileset_box = QComboBox()
        self.tileset_box.setEditable(True)
        self.tileset_box.activated.connect(lambda _i: self._on_tileset())
        self.tileset_box.lineEdit().editingFinished.connect(self._on_tileset)
        browse = QToolButton()
        browse.setText("...")
        browse.clicked.connect(self._browse_tileset)
        tileset_row.addWidget(self.tileset_box, 1)
        tileset_row.addWidget(browse)
        tileset_holder = QWidget()
        tileset_holder.setLayout(tileset_row)
        form.addRow("Tileset", tileset_holder)

        self.tile_w_spin = self._spin(1, 256, 16, self._on_tile_size)
        self.tile_h_spin = self._spin(1, 256, 16, self._on_tile_size)
        form.addRow("Tile size", self._pair(self.tile_w_spin, self.tile_h_spin))

        self.map_w_spin = self._spin(0, 512, 20, self._on_map_size)
        self.map_h_spin = self._spin(0, 512, 15, self._on_map_size)
        self.map_w_spin.setToolTip(
            "Resizing keeps the tiles that still fit, anchored top-left -- the "
            "corner the transform sits on.")
        form.addRow("Map size", self._pair(self.map_w_spin, self.map_h_spin))

        self.zoom_spin = self._spin(1, 8, 2, lambda: self.view.set_zoom(
            self.zoom_spin.value()))
        form.addRow("Palette zoom", self.zoom_spin)
        layout.addLayout(form)

        # -- the sheet -----------------------------------------------------
        self.view = TilesetView()
        self.view.tileSelected.connect(self._on_tile_selected)
        scroll = QScrollArea()
        scroll.setWidget(self.view)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)

        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #9a9aa6;")
        layout.addWidget(self.info)

        self._refresh_info()

    # -- construction helpers ---------------------------------------------

    @staticmethod
    def _spin(low, high, value, slot):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.editingFinished.connect(slot)
        return spin

    @staticmethod
    def _pair(first, second):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(first)
        row.addWidget(QLabel("x"))
        row.addWidget(second)
        return holder

    # -- context ------------------------------------------------------------

    def set_context(self, project, level, library):
        self.project = project
        self.level = level
        self.library = library
        if project is not None:
            self._suspend = True
            current = self.tileset_box.currentText()
            self.tileset_box.clear()
            self.tileset_box.addItems([""] + project.sprite_paths())
            self.tileset_box.setCurrentText(current)
            self._suspend = False
        self.refresh_targets()

    def refresh_targets(self):
        """Rebuild the map list, keeping the current target if it survived."""
        self._suspend = True
        self.target_box.clear()
        maps = tilemap_model.tilemap_objects(self.level, self.library)
        for obj in maps:
            self.target_box.addItem(obj.label(), obj)
        if self.target not in maps:
            self.target = maps[0] if maps else None
        if self.target is not None:
            index = self.target_box.findData(self.target)
            if index >= 0:
                self.target_box.setCurrentIndex(index)
        self._suspend = False
        self.refresh()
        self.targetChanged.emit(self.target)

    def set_target(self, obj):
        """Follow the viewport selection when it lands on a tilemap."""
        if obj is None or obj is self.target:
            return
        if not tilemap_model.is_tilemap(obj, self.library):
            return
        self.target = obj
        index = self.target_box.findData(obj)
        if index >= 0:
            self._suspend = True
            self.target_box.setCurrentIndex(index)
            self._suspend = False
        self.refresh()
        self.targetChanged.emit(self.target)

    def binding(self):
        if self.target is None or self.library is None:
            return None
        found = tilemap_model.TilemapBinding(self.target, self.library)
        return found if found else None

    def refresh(self):
        """Pull every widget back from the model."""
        binding = self.binding()
        self._suspend = True

        enabled = binding is not None
        for widget in (self.tileset_box, self.tile_w_spin, self.tile_h_spin,
                       self.map_w_spin, self.map_h_spin):
            widget.setEnabled(enabled)

        if binding is not None:
            self.tileset_box.setCurrentText(binding.tileset or "")
            self.tile_w_spin.setValue(binding.tile_width)
            self.tile_h_spin.setValue(binding.tile_height)
            self.map_w_spin.setValue(binding.width)
            self.map_h_spin.setValue(binding.height)
            absolute = (self.project.resolve(binding.tileset)
                        if self.project and binding.tileset else None)
            self.view.set_tileset(absolute, binding.tile_width, binding.tile_height)
            self.view.set_selected(self.tile_id)

        self._suspend = False
        self._refresh_info()

    def _refresh_info(self):
        binding = self.binding()
        if binding is None:
            self.info.setText(
                "No tilemap in this level. Press New to add one, or place the "
                "Tilemap prefab from the palette.")
            return
        count = tilemap_model.tileset_tile_count(binding, self.project)
        painted = sum(1 for t in binding.tiles if t)
        parts = [f"{binding.width} x {binding.height} cells",
                 f"{painted} painted"]
        if count:
            parts.append(f"{count} tiles in sheet")
        parts.append(f"tile {self.tile_id}")
        self.info.setText("   ".join(parts))

    # -- handlers -----------------------------------------------------------

    def _on_target_chosen(self, index):
        obj = self.target_box.itemData(index)
        if obj is None or obj is self.target:
            return
        self.target = obj
        self.refresh()
        self.targetChanged.emit(obj)

    def _on_tool(self, key):
        self.tool = key
        self.toolChanged.emit(key)
        self.statusMessage.emit(f"Tile tool: {key}")

    def _on_tile_selected(self, tile_id):
        self.tile_id = int(tile_id)
        self.tileChanged.emit(self.tile_id)
        self._refresh_info()

    def set_tile_id(self, tile_id):
        """Adopt a tile picked in the viewport with the eyedropper."""
        self.tile_id = int(tile_id)
        self.view.set_selected(self.tile_id)
        self.tileChanged.emit(self.tile_id)
        self._refresh_info()

    def _on_tileset(self):
        if self._suspend:
            return
        binding = self.binding()
        if binding is None:
            return
        value = self.tileset_box.currentText() or None
        if value == binding.tileset:
            return
        self.editStarted.emit()
        binding.set("tileset", value)
        self.refresh()
        self.modelChanged.emit()

    def _browse_tileset(self):
        start = (self.project.resources_path if self.project else os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a tileset", start, "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        if self.project is not None:
            try:
                path = os.path.relpath(path, self.project.root).replace(os.sep, "/")
            except ValueError:
                pass
        self.tileset_box.setCurrentText(path)
        self._on_tileset()

    def _on_tile_size(self):
        if self._suspend:
            return
        binding = self.binding()
        if binding is None:
            return
        width, height = self.tile_w_spin.value(), self.tile_h_spin.value()
        if width == binding.tile_width and height == binding.tile_height:
            return
        self.editStarted.emit()
        binding.set("tileWidth", width)
        binding.set("tileHeight", height)
        # Tile ids are positions in the sheet, so a different tile size means
        # every id now points somewhere else. Nothing to migrate -- the grid is
        # simply reinterpreted, which is why this is worth a status line.
        self.statusMessage.emit(
            "Tile size changed -- existing tile ids now index the sheet differently")
        self.refresh()
        self.modelChanged.emit()

    def _on_map_size(self):
        if self._suspend:
            return
        binding = self.binding()
        if binding is None:
            return
        width, height = self.map_w_spin.value(), self.map_h_spin.value()
        if width == binding.width and height == binding.height:
            return
        self.editStarted.emit()
        binding.resize(width, height)
        self.refresh()
        self.modelChanged.emit()

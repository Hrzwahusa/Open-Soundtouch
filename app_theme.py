#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open SoundTouch – das eine App-Design: "Midnight" (dunkel, warm).

Ein einziges, durchdachtes Qt-Stylesheet statt mehrerer Themes.
Palette:
    Hintergrund   #15171C   Karten/Surface  #1E2129   erhoben/Hover  #262A33
    Rahmen        #2E333D   Text            #E7E9EE   dezent/Grau    #8A909C
    Akzent        #F5A623   Akzent-Hover    #FFB43D   Akzent-Pressed #D98C12
    Auf-Akzent    #17130A   Gefahr/Rot      #E5484D
"""

ACCENT = "#F5A623"
BG = "#15171C"
SURFACE = "#1E2129"
TEXT = "#E7E9EE"
MUTED = "#8A909C"

APP_STYLE = """
/* ===== Grundflächen ===== */
QWidget {
    background-color: #15171C;
    color: #E7E9EE;
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #15171C; }

/* ===== Tabs ===== */
QTabWidget::pane {
    border: 1px solid #2E333D;
    border-radius: 12px;
    top: -1px;
    background-color: #171A20;
}
QTabBar::tab {
    background: transparent;
    color: #8A909C;
    padding: 9px 18px;
    margin-right: 4px;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
QTabBar::tab:hover { color: #E7E9EE; }
QTabBar::tab:selected {
    color: #17130A;
    background: #F5A623;
}

/* ===== Karten / Gruppen ===== */
QGroupBox {
    background-color: #1E2129;
    border: 1px solid #2E333D;
    border-radius: 12px;
    margin-top: 30px;
    padding: 22px 16px 16px 16px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    top: 2px;
    padding: 0 4px;
    color: #F5A623;
    font-size: 13px;
    font-weight: 700;
}

/* ===== Buttons (Standard = dezent) ===== */
QPushButton {
    background-color: #262A33;
    color: #E7E9EE;
    border: 1px solid #333945;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2E333D;
    border-color: #F5A623;
    color: #FFFFFF;
}
QPushButton:pressed { background-color: #1E2129; }
QPushButton:disabled {
    background-color: #1A1C22;
    color: #565C68;
    border-color: #24272F;
}
QPushButton:focus { outline: none; border-color: #F5A623; }

/* Betonte Buttons: setProperty("accent", True) bzw. ("danger", True) */
QPushButton[accent="true"] {
    background-color: #F5A623;
    color: #17130A;
    border: none;
}
QPushButton[accent="true"]:hover { background-color: #FFB43D; }
QPushButton[accent="true"]:pressed { background-color: #D98C12; }
QPushButton[accent="true"]:disabled { background-color: #4A3A1A; color: #8A7A50; }

QPushButton[danger="true"] {
    background-color: transparent;
    color: #E5686C;
    border: 1px solid #4A2A2E;
}
QPushButton[danger="true"]:hover {
    background-color: #2A1A1C;
    border-color: #E5484D;
    color: #FF6B70;
}

/* ===== Eingaben ===== */
QLineEdit, QComboBox, QSpinBox, QTextEdit {
    background-color: #12141A;
    color: #E7E9EE;
    border: 1px solid #2E333D;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #F5A623;
    selection-color: #17130A;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border-color: #F5A623;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8A909C;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #1E2129;
    color: #E7E9EE;
    border: 1px solid #2E333D;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: #F5A623;
    selection-color: #17130A;
}

/* ===== Listen ===== */
QListWidget {
    background-color: #12141A;
    border: 1px solid #2E333D;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 8px 10px; border-radius: 6px; }
QListWidget::item:hover { background-color: #1E2129; }
QListWidget::item:selected { background-color: #F5A623; color: #17130A; }

/* ===== Labels ===== */
QLabel { background: transparent; color: #E7E9EE; }

/* ===== Scrollbars ===== */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #333945; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #454C5A; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #333945; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #454C5A; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ===== Progress ===== */
QProgressBar {
    background-color: #12141A;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background-color: #F5A623; border-radius: 6px; }

/* ===== Checkbox ===== */
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid #333945; background: #12141A;
}
QCheckBox::indicator:checked { background: #F5A623; border-color: #F5A623; }

/* ===== Menü ===== */
QMenuBar { background-color: #15171C; color: #E7E9EE; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #262A33; border-radius: 6px; }
QMenu {
    background-color: #1E2129; color: #E7E9EE;
    border: 1px solid #2E333D; border-radius: 8px; padding: 6px;
}
QMenu::item { padding: 7px 22px; border-radius: 6px; }
QMenu::item:selected { background: #F5A623; color: #17130A; }

/* ===== Dialoge / Tooltip ===== */
QMessageBox, QInputDialog { background-color: #1E2129; }
QToolTip {
    background-color: #262A33; color: #E7E9EE;
    border: 1px solid #F5A623; border-radius: 6px; padding: 6px 8px;
}
"""
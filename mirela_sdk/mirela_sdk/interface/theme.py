from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Colors:
    background: str = "#0D1117"
    surface: str = "#161B22"
    surface_elevated: str = "#21262D"
    border: str = "#30363D"
    text_primary: str = "#E6EDF3"
    text_secondary: str = "#8B949E"
    text_muted: str = "#6E7681"
    accent: str = "#FDCE01"
    accent_hover: str = "#FFE04D"
    success: str = "#3FB950"
    warning: str = "#D29922"
    error: str = "#F85149"
    info: str = "#58A6FF"


COLORS = Colors()


def get_stylesheet() -> str:
    return f"""
    * {{
        font-family: "Inter", "SF Pro Display", "Segoe UI", sans-serif;
        font-size: 13px;
    }}

    QMainWindow {{
        background-color: {COLORS.background};
    }}

    QWidget {{
        background-color: transparent;
        color: {COLORS.text_primary};
    }}

    QTabWidget::pane {{
        background-color: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: 8px;
        margin-top: -1px;
    }}

    QTabBar::tab {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_secondary};
        border: 1px solid {COLORS.border};
        border-bottom: none;
        padding: 10px 24px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: 500;
    }}

    QTabBar::tab:selected {{
        background-color: {COLORS.surface};
        color: {COLORS.accent};
        border-bottom: 2px solid {COLORS.accent};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
    }}

    QPushButton {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: {COLORS.border};
        border-color: {COLORS.text_muted};
    }}

    QPushButton:pressed {{
        background-color: {COLORS.surface};
    }}

    QPushButton:disabled {{
        background-color: {COLORS.surface};
        color: {COLORS.text_muted};
        border-color: {COLORS.surface_elevated};
    }}

    QPushButton[accent="true"] {{
        background-color: {COLORS.accent};
        color: {COLORS.background};
        border: none;
    }}

    QPushButton[accent="true"]:hover {{
        background-color: {COLORS.accent_hover};
    }}

    QPushButton[danger="true"] {{
        background-color: {COLORS.error};
        color: {COLORS.text_primary};
        border: none;
    }}

    QPushButton[success="true"] {{
        background-color: {COLORS.success};
        color: {COLORS.background};
        border: none;
    }}

    QLabel {{
        color: {COLORS.text_primary};
        background-color: transparent;
    }}

    QLabel[secondary="true"] {{
        color: {COLORS.text_secondary};
    }}

    QLabel[muted="true"] {{
        color: {COLORS.text_muted};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        padding: 8px 12px;
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {COLORS.accent};
    }}

    QComboBox {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        padding: 8px 12px;
        min-width: 120px;
    }}

    QComboBox:hover {{
        border-color: {COLORS.text_muted};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {COLORS.accent};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
        padding: 4px;
    }}

    QSlider::groove:horizontal {{
        background: {COLORS.border};
        height: 6px;
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background: {COLORS.accent};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {COLORS.accent_hover};
    }}

    QSlider::sub-page:horizontal {{
        background: {COLORS.accent};
        border-radius: 3px;
    }}

    QSlider::groove:vertical {{
        background: {COLORS.border};
        width: 6px;
        border-radius: 3px;
    }}

    QSlider::handle:vertical {{
        background: {COLORS.accent};
        width: 16px;
        height: 16px;
        margin: 0 -5px;
        border-radius: 8px;
    }}

    QSlider::sub-page:vertical {{
        background: {COLORS.border};
        border-radius: 3px;
    }}

    QSlider::add-page:vertical {{
        background: {COLORS.accent};
        border-radius: 3px;
    }}

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background-color: {COLORS.surface};
        width: 10px;
        border-radius: 5px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {COLORS.border};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS.text_muted};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: {COLORS.surface};
        height: 10px;
        border-radius: 5px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {COLORS.border};
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS.text_muted};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    QGroupBox {{
        background-color: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: 8px;
        margin-top: 16px;
        padding: 16px;
        padding-top: 24px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 8px;
        color: {COLORS.accent};
        background-color: {COLORS.surface};
    }}

    QCheckBox {{
        color: {COLORS.text_primary};
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid {COLORS.border};
        background-color: {COLORS.surface};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLORS.accent};
        border-color: {COLORS.accent};
    }}

    QCheckBox::indicator:hover {{
        border-color: {COLORS.accent};
    }}

    QTreeView, QListView, QTableView {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        alternate-background-color: {COLORS.surface_elevated};
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
    }}

    QTreeView::item, QListView::item, QTableView::item {{
        padding: 6px;
    }}

    QTreeView::item:hover, QListView::item:hover {{
        background-color: {COLORS.surface_elevated};
    }}

    QTreeView::item:selected, QListView::item:selected {{
        background-color: {COLORS.accent};
        color: {COLORS.background};
    }}

    QHeaderView::section {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_secondary};
        border: none;
        border-right: 1px solid {COLORS.border};
        border-bottom: 1px solid {COLORS.border};
        padding: 8px;
        font-weight: 600;
    }}

    QSplitter::handle {{
        background-color: {COLORS.border};
        width: 2px;
        height: 2px;
    }}

    QSplitter::handle:hover {{
        background-color: {COLORS.accent};
    }}

    QStatusBar {{
        background-color: {COLORS.surface};
        border-top: 1px solid {COLORS.border};
        color: {COLORS.text_secondary};
    }}

    QToolTip {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 4px 8px;
    }}

    QProgressBar {{
        background-color: {COLORS.border};
        border-radius: 4px;
        text-align: center;
        color: {COLORS.text_primary};
    }}

    QProgressBar::chunk {{
        background-color: {COLORS.accent};
        border-radius: 4px;
    }}

    QSpinBox, QDoubleSpinBox {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        padding: 6px 8px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {COLORS.accent};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: {COLORS.surface_elevated};
        border: none;
        width: 20px;
    }}

    QRadioButton {{
        color: {COLORS.text_primary};
        spacing: 8px;
    }}

    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 2px solid {COLORS.border};
        background-color: {COLORS.surface};
    }}

    QRadioButton::indicator:checked {{
        background-color: {COLORS.accent};
        border-color: {COLORS.accent};
    }}

    QRadioButton::indicator:hover {{
        border-color: {COLORS.accent};
    }}
    """

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """
    Mirela SDK color palette.

    A refined dark theme with amber accents, inspired by professional
    aerospace and robotics interfaces.
    """

    # Base colors
    background: str = "#0A0E14"  # Deep dark blue-black
    surface: str = "#12171E"  # Slightly elevated surface
    surface_elevated: str = "#1A212B"  # Cards and panels
    border: str = "#252D38"  # Subtle borders
    border_focus: str = "#3D4856"  # Focused state borders

    # Text hierarchy
    text_primary: str = "#E8EDF4"  # Primary text
    text_secondary: str = "#8B95A5"  # Secondary labels
    text_muted: str = "#5C6673"  # Disabled/placeholder

    # Accent - Amber/Gold (signature color)
    accent: str = "#F5A623"  # Primary amber
    accent_hover: str = "#FFBA42"  # Hover state
    accent_muted: str = "#B37A1A"  # Subtle accent

    # Semantic colors
    success: str = "#34C759"  # Green
    warning: str = "#FF9F0A"  # Orange
    error: str = "#FF453A"  # Red
    info: str = "#5AC8FA"  # Cyan


COLORS = Colors()


def get_stylesheet() -> str:
    """Generate the global application stylesheet."""
    return f"""
    * {{
        font-family: "JetBrains Mono", "SF Mono", "Consolas", monospace;
        font-size: 12px;
    }}

    QMainWindow {{
        background-color: {COLORS.background};
    }}

    QWidget {{
        background-color: transparent;
        color: {COLORS.text_primary};
    }}

    /* Tab Widget */
    QTabWidget::pane {{
        background-color: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        margin-top: -1px;
    }}

    QTabBar::tab {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_secondary};
        border: 1px solid {COLORS.border};
        border-bottom: none;
        padding: 8px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
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

    /* Buttons - Compact */
    QPushButton {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 5px 12px;
        font-weight: 500;
        min-height: 14px;
    }}

    QPushButton:hover {{
        background-color: {COLORS.border};
        border-color: {COLORS.border_focus};
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
        font-weight: 600;
    }}

    QPushButton[accent="true"]:hover {{
        background-color: {COLORS.accent_hover};
    }}

    QPushButton[accent="true"]:disabled {{
        background-color: {COLORS.accent_muted};
        color: {COLORS.text_muted};
    }}

    QPushButton[danger="true"] {{
        background-color: {COLORS.error};
        color: {COLORS.text_primary};
        border: none;
        font-weight: 600;
    }}

    QPushButton[danger="true"]:hover {{
        background-color: #FF6961;
    }}

    QPushButton[success="true"] {{
        background-color: {COLORS.success};
        color: {COLORS.background};
        border: none;
        font-weight: 600;
    }}

    QPushButton[success="true"]:hover {{
        background-color: #4CD964;
    }}

    /* Labels */
    QLabel {{
        color: {COLORS.text_primary};
        background-color: transparent;
    }}

    QLabel[secondary="true"] {{
        color: {COLORS.text_secondary};
        font-size: 11px;
    }}

    QLabel[muted="true"] {{
        color: {COLORS.text_muted};
        font-size: 10px;
    }}

    QLabel[header="true"] {{
        color: {COLORS.accent};
        font-weight: 600;
        font-size: 13px;
    }}

    /* Input Fields - Compact */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 5px 8px;
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {COLORS.accent};
    }}

    QLineEdit:disabled {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_muted};
    }}

    /* Combo Box - Compact */
    QComboBox {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 5px 8px;
        min-width: 80px;
    }}

    QComboBox:hover {{
        border-color: {COLORS.border_focus};
    }}

    QComboBox:focus {{
        border-color: {COLORS.accent};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {COLORS.accent};
        margin-right: 6px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
        padding: 2px;
    }}

    /* Sliders */
    QSlider::groove:horizontal {{
        background: {COLORS.border};
        height: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {COLORS.accent};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {COLORS.accent_hover};
    }}

    QSlider::sub-page:horizontal {{
        background: {COLORS.accent};
        border-radius: 2px;
    }}

    QSlider::groove:vertical {{
        background: {COLORS.border};
        width: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:vertical {{
        background: {COLORS.accent};
        width: 12px;
        height: 12px;
        margin: 0 -4px;
        border-radius: 6px;
    }}

    QSlider::sub-page:vertical {{
        background: {COLORS.border};
        border-radius: 2px;
    }}

    QSlider::add-page:vertical {{
        background: {COLORS.accent};
        border-radius: 2px;
    }}

    /* Scroll Area */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        border-radius: 4px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {COLORS.border};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS.border_focus};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        border-radius: 4px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {COLORS.border};
        border-radius: 4px;
        min-width: 24px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS.border_focus};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* Group Box - Compact */
    QGroupBox {{
        background-color: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        margin-top: 12px;
        padding: 8px;
        padding-top: 20px;
        font-weight: 500;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: {COLORS.accent};
        background-color: {COLORS.surface};
        font-size: 11px;
        font-weight: 600;
    }}

    /* Checkbox */
    QCheckBox {{
        color: {COLORS.text_primary};
        spacing: 6px;
    }}

    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 3px;
        border: 1px solid {COLORS.border};
        background-color: {COLORS.surface};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLORS.accent};
        border-color: {COLORS.accent};
    }}

    QCheckBox::indicator:hover {{
        border-color: {COLORS.accent};
    }}

    QCheckBox::indicator:disabled {{
        background-color: {COLORS.surface_elevated};
        border-color: {COLORS.surface_elevated};
    }}

    /* Tree/List/Table Views */
    QTreeView, QListView, QTableView {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        alternate-background-color: {COLORS.surface_elevated};
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.background};
    }}

    QTreeView::item, QListView::item, QTableView::item {{
        padding: 4px;
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
        padding: 6px;
        font-weight: 500;
        font-size: 11px;
    }}

    /* Splitter */
    QSplitter::handle {{
        background-color: {COLORS.border};
        width: 1px;
        height: 1px;
    }}

    QSplitter::handle:hover {{
        background-color: {COLORS.accent};
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {COLORS.surface};
        border-top: 1px solid {COLORS.border};
        color: {COLORS.text_secondary};
        font-size: 11px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {COLORS.surface_elevated};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }}

    /* Progress Bar */
    QProgressBar {{
        background-color: {COLORS.border};
        border-radius: 3px;
        text-align: center;
        color: {COLORS.text_primary};
        font-size: 10px;
        height: 6px;
    }}

    QProgressBar::chunk {{
        background-color: {COLORS.accent};
        border-radius: 3px;
    }}

    /* Spin Box - Compact */
    QSpinBox, QDoubleSpinBox {{
        background-color: {COLORS.surface};
        color: {COLORS.text_primary};
        border: 1px solid {COLORS.border};
        border-radius: 4px;
        padding: 4px 6px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {COLORS.accent};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: {COLORS.surface_elevated};
        border: none;
        width: 16px;
    }}

    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {COLORS.border};
    }}

    /* Radio Button */
    QRadioButton {{
        color: {COLORS.text_primary};
        spacing: 6px;
    }}

    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 7px;
        border: 1px solid {COLORS.border};
        background-color: {COLORS.surface};
    }}

    QRadioButton::indicator:checked {{
        background-color: {COLORS.accent};
        border-color: {COLORS.accent};
    }}

    QRadioButton::indicator:hover {{
        border-color: {COLORS.accent};
    }}

    /* Frame */
    QFrame[frameShape="4"] {{
        background-color: {COLORS.border};
        max-height: 1px;
    }}

    QFrame[frameShape="5"] {{
        background-color: {COLORS.border};
        max-width: 1px;
    }}
    """

"""
Styles and Design Tokens for Python PyQt6 AI OCR & Border VIP Service Receipt App
"""

MAIN_STYLESHEET = """
/* Global Application Style */
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Kantumruy Pro', 'Battambang', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #1e293b;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #475569;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #6366f1;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Header Cards & Panels */
QFrame.panel-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
}

QFrame.highlight-card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e1b4b, stop:1 #1e293b);
    border: 1px solid #6366f1;
    border-radius: 12px;
}

/* Labels */
QLabel {
    color: #cbd5e1;
}
QLabel.heading-1 {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}
QLabel.heading-2 {
    font-size: 15px;
    font-weight: bold;
    color: #818cf8;
}
QLabel.heading-3 {
    font-size: 13px;
    font-weight: bold;
    color: #38bdf8;
}
QLabel.stat-value {
    font-size: 22px;
    font-weight: bold;
    color: #34d399;
}
QLabel.badge-tag {
    background-color: #312e81;
    color: #a5b4fc;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: bold;
}

/* Inputs & Form Controls */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #0f172a;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    selection-background-color: #6366f1;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {
    border: 2px solid #6366f1;
    background-color: #111827;
}
QLineEdit:read-only {
    background-color: #182235;
    color: #94a3b8;
    border: 1px solid #334155;
}

/* Buttons */
QPushButton {
    background-color: #334155;
    color: #ffffff;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}
QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton.primary-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
    color: #ffffff;
    border: none;
}
QPushButton.primary-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
}

QPushButton.success-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    color: #ffffff;
    border: none;
}
QPushButton.success-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
}

QPushButton.warning-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
    color: #ffffff;
    border: none;
}
QPushButton.warning-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #d97706);
}

QPushButton.danger-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #f43f5e);
    color: #ffffff;
    border: none;
}
QPushButton.danger-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #be123c, stop:1 #e11d48);
}

/* GroupBox */
QGroupBox {
    border: 1px solid #334155;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: bold;
    color: #94a3b8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #1e293b;
    color: #818cf8;
    border-radius: 4px;
}

/* Tables */
QTableWidget {
    background-color: #0f172a;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #1e293b;
}
QTableWidget::item:selected {
    background-color: #312e81;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #38bdf8;
    padding: 8px 6px;
    border: 1px solid #334155;
    font-weight: bold;
    font-size: 12px;
}
QPushButton.btn-table-action {
    padding: 6px 14px;
    font-size: 13px;
    font-weight: bold;
    border-radius: 6px;
    min-height: 34px;
}

"""

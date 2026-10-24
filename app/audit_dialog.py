from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QMessageBox, QFrame
)
from datetime import datetime
import subprocess
from .log_manager import get_pruefungen, get_jahre
from .pdf_export import generiere_audit_report

_STYLE = """
QDialog { background: #F5F5F7; }
QWidget { background: #F5F5F7; }
QLabel { color: #1D1D1F; font-size: 13px; }
QComboBox {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; padding: 6px 12px;
    color: #1D1D1F; font-size: 14px; min-height: 36px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    selection-background-color: #E3F0FF; selection-color: #007AFF;
}
"""

_BTN = """
    QPushButton {{
        background: {bg}; color: {fg}; border: none;
        border-radius: 10px; padding: {pad};
        font-size: {fs}px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {hov}; }}
    QPushButton:disabled {{ background: #E5E5EA; color: #86868B; }}
"""


class AuditDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Audit-Report generieren")
        self.setFixedWidth(420)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        lbl = QLabel("Audit-Report")
        lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1D1D1F;")
        layout.addWidget(lbl)

        info = QLabel(
            "Erstellt ein schreibgeschütztes PDF mit allen Prüfungen\n"
            "des gewählten Jahres — geeignet für das kantonale Anlagenbuch."
        )
        info.setStyleSheet("color: #86868B; font-size: 13px;")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E5EA;")
        layout.addWidget(sep)

        jahr_layout = QHBoxLayout()
        jahr_lbl = QLabel("Jahr:")
        jahr_lbl.setStyleSheet("font-weight: 600;")
        jahr_layout.addWidget(jahr_lbl)
        self._jahr_combo = QComboBox()
        jahre = get_jahre()
        aktuelles_jahr = datetime.now().year
        if aktuelles_jahr not in jahre:
            jahre.insert(0, aktuelles_jahr)
        for j in jahre:
            self._jahr_combo.addItem(str(j), j)
        jahr_layout.addWidget(self._jahr_combo, 1)
        layout.addLayout(jahr_layout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #E5E5EA;")
        layout.addWidget(sep2)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_abbrechen = QPushButton("Abbrechen")
        btn_abbrechen.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#1D1D1F", hov="#E5E5EA", pad="10px 20px", fs=14
        ))
        btn_abbrechen.clicked.connect(self.reject)
        btn_generieren = QPushButton("PDF generieren")
        btn_generieren.setStyleSheet(_BTN.format(
            bg="#007AFF", fg="white", hov="#0071E3", pad="10px 20px", fs=14
        ))
        btn_generieren.setDefault(True)
        btn_generieren.clicked.connect(self._generieren)
        btn_layout.addWidget(btn_abbrechen)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(btn_generieren)
        layout.addLayout(btn_layout)

    def _generieren(self):
        jahr = self._jahr_combo.currentData()
        pruefungen = get_pruefungen(f"{jahr}-01-01", f"{jahr}-12-31")

        if not pruefungen:
            QMessageBox.information(self, "Keine Daten",
                                    f"Für {jahr} sind keine Prüfungen vorhanden.")
            return

        try:
            pfad = generiere_audit_report(self._config, pruefungen, jahr)
            msg = QMessageBox(self)
            msg.setWindowTitle("Report erstellt")
            msg.setText(f"PDF erfolgreich erstellt:\n{pfad}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Open)
            msg.button(QMessageBox.StandardButton.Open).setText("Im Finder öffnen")
            if msg.exec() == QMessageBox.StandardButton.Open:
                subprocess.run(["open", "-R", pfad])
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"PDF konnte nicht erstellt werden:\n{e}")

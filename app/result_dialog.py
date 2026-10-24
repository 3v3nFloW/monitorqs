from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt

_STYLE = """
QDialog { background: #F5F5F7; }
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
QTextEdit {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; padding: 8px;
    color: #1D1D1F; font-size: 13px;
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


class ResultDialog(QDialog):
    def __init__(self, bestanden: bool, pruefer_liste: list[str], parent=None, kriterien: list | None = None):
        super().__init__(parent)
        self._bestanden = bestanden
        self._pruefer_liste = pruefer_liste
        self._kriterien = kriterien or []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Prüfungsergebnis erfassen")
        self.setFixedWidth(600 if self._kriterien else 480)
        self.setModal(True)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Result banner
        banner = QLabel()
        if self._bestanden:
            banner.setText("✓  Konstanzprüfung BESTANDEN")
            banner.setStyleSheet(
                "background: rgba(52,199,89,40); color: #1a6b2e; "
                "font-size: 16px; font-weight: 700; "
                "border: 1px solid rgba(52,199,89,120); "
                "border-radius: 12px; padding: 14px 18px;"
            )
        else:
            banner.setText("✗  Konstanzprüfung NICHT BESTANDEN")
            banner.setStyleSheet(
                "background: rgba(255,59,48,40); color: #8b1a1a; "
                "font-size: 16px; font-weight: 700; "
                "border: 1px solid rgba(255,59,48,120); "
                "border-radius: 12px; padding: 14px 18px;"
            )
        layout.addWidget(banner)

        # Einzelkriterien (Konstanzprüfung BAG, Tabelle C)
        if self._kriterien:
            zeilen = []
            for k in self._kriterien:
                if k["erfuellt"]:
                    marke = '<span style="color:#1a6b2e;font-weight:700">✓ erfüllt</span>'
                else:
                    marke = '<span style="color:#8b1a1a;font-weight:700">✗ nicht erfüllt</span>'
                zeilen.append(f"<tr><td>{k.get('testbild', '')}</td><td>{k['id']}</td>"
                              f"<td>{k['kurz']}</td><td>{marke}</td></tr>")
            tabelle = QLabel(
                '<table cellspacing="0" cellpadding="3">' + "".join(zeilen) + "</table>"
            )
            tabelle.setTextFormat(Qt.TextFormat.RichText)
            tabelle.setStyleSheet(
                "background: #FFFFFF; border: 1px solid #E5E5EA; border-radius: 10px; "
                "padding: 8px; font-size: 12px;"
            )
            layout.addWidget(tabelle)

        # Prüfer
        pruefer_layout = QHBoxLayout()
        pruefer_lbl = QLabel("Prüfer:")
        pruefer_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        pruefer_layout.addWidget(pruefer_lbl)
        self._pruefer_combo = QComboBox()
        # Editierbar: ohne hinterlegte Prüfer (Erststart) wird der Name direkt eingetippt
        self._pruefer_combo.setEditable(True)
        self._pruefer_combo.addItems(self._pruefer_liste)
        self._pruefer_combo.lineEdit().setPlaceholderText("Name der prüfenden Person")
        pruefer_layout.addWidget(self._pruefer_combo, 1)
        layout.addLayout(pruefer_layout)

        # Kommentar
        kom_lbl = QLabel("Kommentar (optional):")
        kom_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(kom_lbl)
        self._kommentar_edit = QTextEdit()
        self._kommentar_edit.setFixedHeight(80)
        self._kommentar_edit.setPlaceholderText("z. B. Auffälligkeiten, technische Hinweise…")
        layout.addWidget(self._kommentar_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_abbrechen = QPushButton("Abbrechen")
        btn_abbrechen.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#1D1D1F", hov="#E5E5EA", pad="10px 20px", fs=14
        ))
        btn_abbrechen.clicked.connect(self.reject)
        btn_speichern = QPushButton("Speichern")
        btn_speichern.setStyleSheet(_BTN.format(
            bg="#007AFF", fg="white", hov="#0071E3", pad="10px 20px", fs=14
        ))
        btn_speichern.setDefault(True)
        btn_speichern.clicked.connect(self._speichern)
        btn_layout.addWidget(btn_abbrechen)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(btn_speichern)
        layout.addLayout(btn_layout)

    def _speichern(self):
        if not self.get_pruefer():
            QMessageBox.warning(self, "Prüfer fehlt", "Bitte den Namen der prüfenden Person angeben.")
            return
        self.accept()

    def get_pruefer(self) -> str:
        return self._pruefer_combo.currentText().strip()

    def get_kommentar(self) -> str:
        return self._kommentar_edit.toPlainText().strip()

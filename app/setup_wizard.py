from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QWidget, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from .config_manager import save_config, save_monitors, load_monitors
from .kriterien import RAUMKLASSEN

_STYLE = """
QDialog { background: #F5F5F7; }
QWidget { background: #F5F5F7; }
QLabel { color: #1D1D1F; font-size: 13px; }
QLineEdit {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; padding: 8px 12px;
    color: #1D1D1F; font-size: 14px; min-height: 36px;
}
QScrollArea { border: 1px solid #E5E5EA; border-radius: 10px; background: #FFFFFF; }
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


def erkannte_monitore() -> list:
    """Vorschlag beim Erststart: angeschlossene Bildschirme mit ihrer Panelauflösung."""
    monitore = []
    for s in QGuiApplication.screens():
        geo, dpr = s.geometry(), s.devicePixelRatio()
        monitore.append({"name": s.name() or f"Monitor {len(monitore) + 1}", "aufloesung": f"{round(geo.width() * dpr)}x{round(geo.height() * dpr)}"})
    return monitore


class MonitorListWidget(QWidget):
    def __init__(self, monitors: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #FFFFFF;")
        self._rows = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        for m in monitors:
            self._add_row(m["name"], m["aufloesung"], m.get("raumklasse", ""))
        self._add_btn = QPushButton("+ Monitor hinzufügen")
        self._add_btn.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#007AFF", hov="#E3F0FF", pad="8px 16px", fs=13
        ))
        self._add_btn.clicked.connect(lambda: self._add_row("", "", ""))
        self._layout.addWidget(self._add_btn)

    def _add_row(self, name: str, aufloesung: str, raumklasse: str = ""):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText('z. B. Samsung 43"')
        name_edit.setStyleSheet(
            "background: #F5F5F7; border: 1px solid #E5E5EA; border-radius: 8px; "
            "padding: 6px 10px; font-size: 13px;"
        )
        aufl_edit = QLineEdit(aufloesung)
        aufl_edit.setPlaceholderText("z. B. 3840×2160")
        aufl_edit.setFixedWidth(130)
        aufl_edit.setStyleSheet(
            "background: #F5F5F7; border: 1px solid #E5E5EA; border-radius: 8px; "
            "padding: 6px 10px; font-size: 13px;"
        )
        # Raumklasse (BAG-Wegleitung Tab. 3) bestimmt das Kriterium «QUALITY CONTROL» im schwarzen Feld
        rk_combo = QComboBox()
        for rk in RAUMKLASSEN:
            rk_combo.addItem(rk or "RK –", rk)
        rk_combo.setCurrentIndex(max(0, rk_combo.findData(raumklasse)))
        rk_combo.setFixedWidth(90)
        rk_combo.setToolTip("Raumklasse: RK1 Befundungsraum ≤ 50 lx, RK2 ≤ 100 lx, RK3 ≤ 500 lx")
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30, 30)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: none; font-size: 15px; }"
            "QPushButton:hover { color: #FF3B30; }"
        )
        del_btn.clicked.connect(lambda checked, r=row: self._remove_row(r))
        hl.addWidget(name_edit, 1)
        hl.addWidget(aufl_edit)
        hl.addWidget(rk_combo)
        hl.addWidget(del_btn)
        self._rows.append((row, name_edit, aufl_edit, rk_combo))
        self._layout.insertWidget(self._layout.count() - 1, row)

    def _remove_row(self, row_widget):
        self._rows = [t for t in self._rows if t[0] is not row_widget]
        row_widget.deleteLater()

    def get_monitors(self) -> list:
        result = []
        for _, name_edit, aufl_edit, rk_combo in self._rows:
            name = name_edit.text().strip()
            if name:
                result.append({"name": name, "aufloesung": aufl_edit.text().strip(),
                               "raumklasse": rk_combo.currentData() or ""})
        return result


class SetupWizard(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("MonitorQS — Ersteinrichtung")
        self.setMinimumWidth(580)
        self.setModal(True)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 28)

        # Title
        title = QLabel("Ersteinrichtung")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1D1D1F;")
        layout.addWidget(title)
        sub = QLabel("Diese Angaben erscheinen in der Kopfzeile Ihrer Audit-Reports.")
        sub.setStyleSheet("color: #86868B; font-size: 13px;")
        layout.addWidget(sub)

        layout.addWidget(self._sep())

        # Praxis fields
        self._praxis_edit  = self._field(layout, "Praxisname *", "z. B. Tierarztpraxis Mustermann",
                                          self._config.get("praxis_name", ""))
        self._adresse_edit = self._field(layout, "Adresse", "Musterstrasse 1",
                                          self._config.get("adresse", ""))
        self._ortplz_edit  = self._field(layout, "Ort / PLZ", "8000 Zürich",
                                          self._config.get("ort_plz", ""))
        self._bewill_edit  = self._field(layout, "Röntgen-Bewilligung Nr.", "KT-2024-XXXX",
                                          self._config.get("roentgen_bewilligung", ""))
        self._pruefer_edit = self._field(layout, "Prüfer (kommagetrennt)", "z. B. A. Muster, B. Beispiel",
                                          ", ".join(self._config.get("pruefer", [])))

        layout.addWidget(self._sep())

        mon_lbl = QLabel("Monitore")
        mon_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1D1D1F;")
        layout.addWidget(mon_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(180)
        self._monitor_list = MonitorListWidget(load_monitors() or erkannte_monitore())
        scroll.setWidget(self._monitor_list)
        layout.addWidget(scroll)

        layout.addWidget(self._sep())

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("Einrichtung abschließen")
        btn_ok.setStyleSheet(_BTN.format(
            bg="#007AFF", fg="white", hov="#0071E3", pad="12px 24px", fs=15
        ))
        btn_ok.setMinimumHeight(44)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._speichern)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _field(self, layout, label, placeholder, value="") -> QLineEdit:
        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        layout.addWidget(lbl)
        layout.addWidget(edit)
        return edit

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #E5E5EA;")
        return line

    def _speichern(self):
        if not self._praxis_edit.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte Praxisname eingeben.")
            return

        config = self._config.copy()
        config["praxis_name"] = self._praxis_edit.text().strip()
        config["adresse"] = self._adresse_edit.text().strip()
        config["ort_plz"] = self._ortplz_edit.text().strip()
        config["roentgen_bewilligung"] = self._bewill_edit.text().strip()
        config["pruefer"] = [p.strip() for p in self._pruefer_edit.text().split(",") if p.strip()]
        config["setup_done"] = True

        monitors = self._monitor_list.get_monitors()
        if not monitors:
            QMessageBox.warning(self, "Kein Monitor", "Bitte mindestens einen Monitor eintragen.")
            return

        try:
            save_config(config)
            save_monitors(monitors)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler beim Speichern", str(exc))
            return
        self.accept()

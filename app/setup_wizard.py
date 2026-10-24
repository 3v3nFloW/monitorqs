from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QWidget, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from .config_manager import save_config, save_monitors, load_monitors
from .bildschirme import beschreibe, kennung, zuordnung
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


def _als_monitor(b: dict, n: int) -> dict:
    return {"name": b["name"] or f"Monitor {n}", "aufloesung": f"{b['px'][0]}x{b['px'][1]}", "kennung": kennung(b)}


def erkannte_monitore() -> list:
    """Vorschlag beim Erststart: angeschlossene Bildschirme mit Panelauflösung und Kennung."""
    return [_als_monitor(b, n) for n, b in enumerate(beschreibe(QGuiApplication.screens()), 1)]


class MonitorListWidget(QWidget):
    def __init__(self, monitors: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #FFFFFF;")
        self._rows = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Monitor hinzufügen")
        self._add_btn.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#007AFF", hov="#E3F0FF", pad="8px 16px", fs=13
        ))
        self._add_btn.clicked.connect(lambda: self._add_row("", "", ""))
        erkennen_btn = QPushButton("+ Angeschlossene Bildschirme")
        erkennen_btn.setToolTip("Fügt jeden angeschlossenen Bildschirm hinzu, der noch keinem Monitor zugeordnet ist")
        erkennen_btn.setStyleSheet(self._add_btn.styleSheet())
        erkennen_btn.clicked.connect(self._angeschlossene_hinzufuegen)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(erkennen_btn)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)
        # Zeilen kommen vor die Knopfzeile, in der gespeicherten Reihenfolge
        for m in monitors:
            self._add_row(m["name"], m["aufloesung"], m.get("raumklasse", ""), m.get("kennung"))

    def _angeschlossene_hinzufuegen(self):
        bildschirme = beschreibe(QGuiApplication.screens())
        belegt = set(zuordnung(self.get_monitors(), bildschirme).values())
        neu = [(n, b) for n, b in enumerate(bildschirme, 1) if n - 1 not in belegt]
        if not neu:
            QMessageBox.information(self, "Nichts hinzuzufügen",
                                    "Alle angeschlossenen Bildschirme sind bereits einem Monitor zugeordnet.")
        for n, b in neu:
            m = _als_monitor(b, n)
            self._add_row(m["name"], m["aufloesung"], "", m["kennung"])

    def _add_row(self, name: str, aufloesung: str, raumklasse: str = "", kennung_: dict | None = None):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText('z. B. Samsung 43"')
        if kennung_:
            name_edit.setToolTip(f"Wird wiedererkannt an: {kennung_.get('name') or 'Gerätekennung'}")
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
        self._rows.append((row, name_edit, aufl_edit, rk_combo, kennung_))
        self._layout.insertWidget(self._layout.count() - 1, row)

    def _remove_row(self, row_widget):
        self._rows = [t for t in self._rows if t[0] is not row_widget]
        row_widget.deleteLater()

    def get_monitors(self) -> list:
        result = []
        for _, name_edit, aufl_edit, rk_combo, kennung_ in self._rows:
            name = name_edit.text().strip()
            if name:
                m = {"name": name, "aufloesung": aufl_edit.text().strip(), "raumklasse": rk_combo.currentData() or ""}
                if kennung_:
                    m["kennung"] = kennung_
                result.append(m)
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

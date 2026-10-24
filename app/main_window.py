from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QAction, QGuiApplication
from PyQt6.QtWidgets import QProgressDialog

from .config_manager import load_config, load_monitors
from .log_manager import init_db, get_pruefungen
from .image_loader import list_testbilder, load_as_qpixmap, waehle_oiq, un80_qpixmap
from .kriterien import oiq_kriterien, un80_kriterien
from .display_window import DisplayWindow
from .result_dialog import ResultDialog
from .settings_dialog import SettingsDialog
from .audit_dialog import AuditDialog
from .notifications import send_notification
from . import testbilder


_STYLE = """
QMainWindow, QWidget#central {
    background: #F5F5F7;
}
QLabel { color: #1D1D1F; font-size: 13px; }
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 12px;
    margin-top: 8px;
    padding: 16px 14px 14px 14px;
    font-size: 11px; color: #86868B;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; }
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
QTableWidget {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; gridline-color: #F5F5F7;
    font-size: 12px; color: #1D1D1F;
}
QTableWidget::item { padding: 6px 10px; border: none; }
QTableWidget::item:selected { background: #E3F0FF; color: #007AFF; }
QHeaderView::section {
    background: #F5F5F7; color: #86868B; font-size: 11px;
    font-weight: 600; border: none; border-bottom: 1px solid #E5E5EA;
    padding: 6px 10px;
}
QScrollBar:vertical { background: #F5F5F7; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #C7C7CC; border-radius: 4px; min-height: 20px; }
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


def _screen_pixel_size(screen) -> tuple[int, int]:
    """Physische (Geräte-)Pixelmaße eines Screens: logische Größe × devicePixelRatio."""
    geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    return round(geo.width() * dpr), round(geo.height() * dpr)


def _parse_aufloesung(text: str) -> tuple[int, int] | None:
    """'5120x1440' / '5120×2880' → (5120, 1440); None wenn nicht parsebar."""
    if not text:
        return None
    norm = text.lower().replace("×", "x").replace(" ", "")
    parts = norm.split("x")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return None


class _TestbilderLaden(QThread):
    fortschritt = pyqtSignal(str, int)
    fertig = pyqtSignal(str)  # leer = ok, sonst Fehlermeldung

    def run(self):
        try:
            testbilder.herunterladen(lambda text, anteil: self.fortschritt.emit(text, int(anteil * 100)))
            self.fertig.emit("")
        except Exception as e:
            self.fertig.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self._config = load_config()
        self._display_win = None
        self._aktueller_monitor = None
        self._aktuelles_bild = None
        self._setup_ui()
        self._setup_menu()
        self._lade_log_tabelle()

    def _setup_ui(self):
        self.setWindowTitle("MonitorQS — Konstanzprüfung")
        self.setMinimumSize(QSize(820, 600))
        self.setStyleSheet(_STYLE)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("MonitorQS")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1D1D1F;")
        self._praxis_lbl = QLabel(self._config.get("praxis_name", ""))
        self._praxis_lbl.setStyleSheet("color: #86868B; font-size: 13px;")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(self._praxis_lbl)
        header.addStretch()
        settings_btn = QPushButton("Einstellungen")
        settings_btn.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#1D1D1F", hov="#E5E5EA", pad="8px 16px", fs=13
        ))
        settings_btn.clicked.connect(self._einstellungen)
        header.addWidget(settings_btn)
        root.addLayout(header)

        # Prüfung starten
        pruef_box = QGroupBox("Konstanzprüfung starten")
        pruef_layout = QVBoxLayout(pruef_box)
        pruef_layout.setSpacing(10)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(16)
        mon_lbl = QLabel("Monitor:")
        mon_lbl.setStyleSheet("font-weight: 600;")
        self._monitor_combo = QComboBox()
        self._monitor_combo.setMinimumWidth(220)
        self._lade_monitore()
        sel_row.addWidget(mon_lbl)
        sel_row.addWidget(self._monitor_combo)
        sel_row.addSpacing(20)

        bild_lbl = QLabel("Testbild:")
        bild_lbl.setStyleSheet("font-weight: 600;")
        self._bild_combo = QComboBox()
        self._bild_combo.setMinimumWidth(260)
        self._testbilder = list_testbilder()
        for b in self._testbilder:
            self._bild_combo.addItem(b["name"])
        sel_row.addWidget(bild_lbl)
        sel_row.addWidget(self._bild_combo)
        sel_row.addStretch()
        pruef_layout.addLayout(sel_row)

        # Ziel-Bildschirm (auf welchem physischen Panel wird geprüft)
        screen_row = QHBoxLayout()
        screen_row.setSpacing(16)
        screen_lbl = QLabel("Bildschirm:")
        screen_lbl.setStyleSheet("font-weight: 600;")
        self._screen_combo = QComboBox()
        self._screen_combo.setMinimumWidth(360)
        self._lade_bildschirme()
        screen_row.addWidget(screen_lbl)
        screen_row.addWidget(self._screen_combo)
        screen_row.addStretch()
        pruef_layout.addLayout(screen_row)

        # Welche TG18-OIQ-Variante 1:1 auf das gewählte Panel passt
        self._oiq_info = QLabel("")
        self._oiq_info.setStyleSheet("color: #86868B; font-size: 12px;")
        pruef_layout.addWidget(self._oiq_info)
        self._screen_combo.currentIndexChanged.connect(self._aktualisiere_oiq_info)
        self._bild_combo.currentIndexChanged.connect(self._aktualisiere_oiq_info)

        # Bei Monitorwechsel automatisch den Screen mit passender Auflösung vorwählen
        self._monitor_combo.currentIndexChanged.connect(self._auto_select_screen)
        self._auto_select_screen()
        self._aktualisiere_oiq_info()

        self._start_btn = QPushButton("Prüfung starten")
        self._start_btn.setStyleSheet(_BTN.format(
            bg="#007AFF", fg="white", hov="#0071E3", pad="12px 24px", fs=15
        ))
        self._start_btn.setMinimumHeight(44)
        self._start_btn.setEnabled(bool(self._testbilder))
        self._start_btn.clicked.connect(self._pruefung_starten)
        pruef_layout.addWidget(self._start_btn)

        # TG18-Muster sind nicht mitgeliefert (Copyright AAPM) → einmalig von Duke RAI Labs laden
        self._laden_box = QFrame()
        self._laden_box.setStyleSheet("QFrame { background: #fff3cd; border-radius: 8px; }")
        laden_layout = QHBoxLayout(self._laden_box)
        laden_info = QLabel(
            "TG18-Testmuster fehlen. Sie werden einmalig und unverändert von Duke RAI Labs geladen "
            "(ca. 1 MB, Copyright AAPM) und per Prüfsumme kontrolliert. Bis dahin steht nur TG18-UN80 bereit."
        )
        laden_info.setWordWrap(True)
        laden_info.setStyleSheet("color: #8b6914; background: transparent;")
        laden_layout.addWidget(laden_info, 1)
        laden_btn = QPushButton("Testmuster laden")
        laden_btn.setStyleSheet(_BTN.format(
            bg="#007AFF", fg="white", hov="#0071E3", pad="8px 16px", fs=13
        ))
        laden_btn.clicked.connect(self._testbilder_laden)
        laden_layout.addWidget(laden_btn)
        self._laden_box.setVisible(not testbilder.vorhanden())
        pruef_layout.addWidget(self._laden_box)

        root.addWidget(pruef_box)

        # Status-Zeile (non-modal, blendet nach 4s aus)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 13px; min-height: 20px;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status_lbl)

        # Prüfprotokoll
        log_box = QGroupBox("Prüfprotokoll")
        log_layout = QVBoxLayout(log_box)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Datum/Zeit", "Monitor", "Testbild", "Prüfer", "Ergebnis", "Kommentar"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        log_layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#1D1D1F", hov="#E5E5EA", pad="8px 16px", fs=13
        ))
        refresh_btn.clicked.connect(self._lade_log_tabelle)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        audit_btn = QPushButton("Audit-Report PDF")
        audit_btn.setStyleSheet(_BTN.format(
            bg="#F2F2F7", fg="#007AFF", hov="#E3F0FF", pad="8px 16px", fs=13
        ))
        audit_btn.clicked.connect(self._audit_report)
        btn_row.addWidget(audit_btn)
        log_layout.addLayout(btn_row)

        root.addWidget(log_box, stretch=1)

        # Footer
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E5EA;")
        root.addWidget(sep)
        footer = QLabel("MonitorQS · Konstanzprüfung nach RöV/BAG · Built in Switzerland with ♥ by Kappa1-VRS")
        footer.setStyleSheet("color: #86868B; font-size: 11px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(footer)

    def _testbilder_laden(self):
        self._laden_dlg = QProgressDialog("Testmuster werden geladen …", None, 0, 100, self)
        self._laden_dlg.setWindowTitle("MonitorQS")
        self._laden_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self._laden_dlg.setMinimumDuration(0)
        self._laden_dlg.setValue(0)
        self._laden_thread = _TestbilderLaden(self)
        self._laden_thread.fortschritt.connect(lambda text, wert: (self._laden_dlg.setLabelText(text),
                                                                    self._laden_dlg.setValue(wert)))
        self._laden_thread.fertig.connect(self._testbilder_geladen)
        self._laden_thread.start()

    def _testbilder_geladen(self, fehler: str):
        self._laden_dlg.close()
        if fehler:
            QMessageBox.warning(self, "Testmuster nicht geladen", fehler)
            return
        self._testbilder = list_testbilder()
        self._bild_combo.clear()
        for b in self._testbilder:
            self._bild_combo.addItem(b["name"])
        self._laden_box.setVisible(not testbilder.vorhanden())
        self._aktualisiere_oiq_info()

    def _setup_menu(self):
        menubar = self.menuBar()
        app_menu = menubar.addMenu("MonitorQS")
        act = QAction("Einstellungen…", self)
        act.triggered.connect(self._einstellungen)
        app_menu.addAction(act)

    def _lade_monitore(self):
        self._monitors = load_monitors()
        self._monitor_combo.clear()
        for m in self._monitors:
            self._monitor_combo.addItem(m["name"])

    def _lade_bildschirme(self):
        self._screens = QGuiApplication.screens()
        self._screen_combo.clear()
        primary = QGuiApplication.primaryScreen()
        for s in self._screens:
            pw, ph = _screen_pixel_size(s)
            dpr = s.devicePixelRatio()
            label = f"{s.name()} — {pw}×{ph} px"
            if abs(dpr - 1.0) > 0.01:
                label += f" (@{dpr:.2g}×)"
            if s is primary:
                label += "  · primär"
            self._screen_combo.addItem(label)

    def _auto_select_screen(self):
        """Screen vorwählen, dessen Panelauflösung zur gewählten Monitor-Auflösung passt."""
        if not getattr(self, "_screens", None) or not getattr(self, "_monitors", None):
            return
        idx = self._monitor_combo.currentIndex()
        if not (0 <= idx < len(self._monitors)):
            return
        ziel = _parse_aufloesung(self._monitors[idx].get("aufloesung", ""))
        if ziel is None:
            return
        for i, s in enumerate(self._screens):
            if _screen_pixel_size(s) == ziel:
                self._screen_combo.setCurrentIndex(i)
                return

    def _ziel_screen(self):
        screen_idx = self._screen_combo.currentIndex()
        screens = getattr(self, "_screens", [])
        return screens[screen_idx] if 0 <= screen_idx < len(screens) else QGuiApplication.primaryScreen()

    def _raumklasse(self) -> str:
        idx = self._monitor_combo.currentIndex()
        monitors = getattr(self, "_monitors", [])
        return monitors[idx].get("raumklasse", "") if 0 <= idx < len(monitors) else ""

    def _aktualisiere_oiq_info(self):
        idx = self._bild_combo.currentIndex()
        if not (0 <= idx < len(self._testbilder)) or self._testbilder[idx]["typ"] not in ("bag", "oiq"):
            self._oiq_info.setText("")
            return
        pw, ph = _screen_pixel_size(self._ziel_screen())
        oiq = waehle_oiq(pw, ph)
        if oiq is None:
            self._oiq_info.setText(f"⚠  Keine TG18-OIQ-Variante passt 1:1 auf {pw}×{ph} px.")
        else:
            self._oiq_info.setText(f"TG18-OIQ für dieses Panel ({pw}×{ph} px): {oiq.stem}")

    def _lade_log_tabelle(self):
        try:
            rows = get_pruefungen()
            self._table.setRowCount(len(rows))
            for i, row in enumerate(reversed(rows)):
                self._table.setItem(i, 0, QTableWidgetItem(row["zeitstempel"]))
                self._table.setItem(i, 1, QTableWidgetItem(row["monitor"]))
                self._table.setItem(i, 2, QTableWidgetItem(row["testbild"]))
                self._table.setItem(i, 3, QTableWidgetItem(row["pruefer"]))
                ergebnis_item = QTableWidgetItem(row["ergebnis"])
                if row["ergebnis"] == "BESTANDEN":
                    ergebnis_item.setForeground(QColor("#1a6b2e"))
                else:
                    ergebnis_item.setForeground(QColor("#8b1a1a"))
                font = ergebnis_item.font()
                font.setBold(True)
                ergebnis_item.setFont(font)
                if row.get("kriterien"):
                    ergebnis_item.setToolTip("\n".join(
                        f"{'✓' if k['erfuellt'] else '✗'}  {k['id']} {k['kurz']}" for k in row["kriterien"]
                    ))
                self._table.setItem(i, 4, ergebnis_item)
                self._table.setItem(i, 5, QTableWidgetItem(row.get("kommentar", "") or ""))
        except Exception as exc:
            QMessageBox.critical(self, "Fehler beim Laden", str(exc))

    def _pruefung_starten(self):
        if not self._testbilder:
            return
        monitor_name = self._monitor_combo.currentText()
        bild_idx = self._bild_combo.currentIndex()
        bild_info = self._testbilder[bild_idx]
        target_screen = self._ziel_screen()
        pw, ph = _screen_pixel_size(target_screen)
        typ = bild_info["typ"]
        try:
            schritte = []
            testbild_name = bild_info["name"]
            if typ in ("bag", "oiq"):
                oiq = waehle_oiq(pw, ph)
                if oiq is None:
                    QMessageBox.critical(self, "Fehler",
                                         f"Keine TG18-OIQ-Variante passt 1:1 auf {pw}×{ph} px.")
                    return
                pixmap, w, h = load_as_qpixmap(str(oiq))
                schritte.append({"pixmap": pixmap, "w": w, "h": h, "titel": oiq.stem,
                                 "kriterien": oiq_kriterien(self._raumklasse())})
                testbild_name = oiq.stem
            if typ in ("bag", "un80"):
                pixmap, w, h = un80_qpixmap(pw, ph)
                schritte.append({"pixmap": pixmap, "w": w, "h": h, "titel": "TG18-UN80",
                                 "kriterien": un80_kriterien()})
                testbild_name = "TG18-UN80" if typ == "un80" else f"{testbild_name} + TG18-UN80"
            if typ in ("dicom", "png"):
                pixmap, w, h = load_as_qpixmap(bild_info["pfad"])
                schritte.append({"pixmap": pixmap, "w": w, "h": h, "titel": bild_info["name"],
                                 "kriterien": None})
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Testbild konnte nicht geladen werden:\n{e}")
            return
        self._aktueller_monitor = monitor_name
        self._aktuelles_bild = testbild_name
        self._display_win = DisplayWindow(schritte, screen=target_screen)
        self._display_win.pruefung_abgeschlossen.connect(self._pruefung_abgeschlossen)
        self._display_win.show()

    def _pruefung_abgeschlossen(self, bestanden: bool, kriterien):
        # Defer out of the signal-handler chain; prevents PyQt6 abort on exception
        QTimer.singleShot(0, lambda b=bestanden, k=kriterien: self._zeige_ergebnis_dialog(b, k))

    def _zeige_ergebnis_dialog(self, bestanden: bool, kriterien=None):
        try:
            pruefer_raw = self._config.get("pruefer", [])
            if isinstance(pruefer_raw, str):
                pruefer_liste = [p.strip() for p in pruefer_raw.split(",") if p.strip()]
            else:
                pruefer_liste = list(pruefer_raw)
            dlg = ResultDialog(bestanden, pruefer_liste, self, kriterien=kriterien)
            if dlg.exec() == ResultDialog.DialogCode.Accepted:
                from .log_manager import log_pruefung
                log_pruefung(
                    monitor=self._aktueller_monitor,
                    testbild=self._aktuelles_bild,
                    pruefer=dlg.get_pruefer(),
                    ergebnis="BESTANDEN" if bestanden else "NICHT BESTANDEN",
                    kommentar=dlg.get_kommentar(),
                    kriterien=kriterien,
                )
                self._lade_log_tabelle()
                color = "#34C759" if bestanden else "#FF3B30"
                self._status_lbl.setText(
                    f'<span style="color:{color};font-weight:700">'
                    f'{"BESTANDEN" if bestanden else "NICHT BESTANDEN"}</span>'
                    f' — {self._aktueller_monitor} gespeichert'
                )
                QTimer.singleShot(4000, lambda: self._status_lbl.clear())
                send_notification(
                    "MonitorQS",
                    f"Prüfung {'bestanden' if bestanden else 'nicht bestanden'} — {self._aktueller_monitor}"
                )
        except Exception:
            import traceback
            from pathlib import Path
            err = traceback.format_exc()
            log_dir = Path.home() / "Library" / "Logs" / "MonitorQS"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "error.log").write_text(err)
            QMessageBox.critical(self, "Fehler", f"Unerwarteter Fehler:\n\n{err}")

    def _audit_report(self):
        dlg = AuditDialog(self._config, self)
        dlg.exec()

    def _einstellungen(self):
        try:
            dlg = SettingsDialog(self._config, self)
            if dlg.exec() == SettingsDialog.DialogCode.Accepted:
                self._config = load_config()
                self._lade_monitore()
                self._praxis_lbl.setText(self._config.get("praxis_name", ""))
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

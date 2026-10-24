from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QAction, QGuiApplication
from PyQt6.QtWidgets import QProgressDialog

from .config_manager import load_config, load_monitors, save_monitors
from .bildschirme import pixelgroesse, beschreibe, zuordnung, abweichungen, kennung
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
        self._aktueller_bildschirm = ""
        self._kennung_lernen = None
        self._zu = {}
        self._beobachtet = []
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

        # Erkennung: welcher erfasste Monitor an welchem Bildschirm hängt
        self._erkennung_lbl = QLabel("")
        self._erkennung_lbl.setWordWrap(True)
        pruef_layout.addWidget(self._erkennung_lbl)

        # Welche TG18-OIQ-Variante 1:1 auf das gewählte Panel passt
        self._oiq_info = QLabel("")
        self._oiq_info.setStyleSheet("color: #86868B; font-size: 12px;")
        pruef_layout.addWidget(self._oiq_info)
        self._bild_combo.currentIndexChanged.connect(self._aktualisiere_oiq_info)

        # Monitor ↔ Bildschirm wählen sich gegenseitig vor; an-/abstecken wird live nachgeführt
        self._monitor_combo.currentIndexChanged.connect(self._monitor_gewaehlt)
        self._screen_combo.currentIndexChanged.connect(self._bildschirm_gewaehlt)
        self._neu_timer = QTimer(self)
        self._neu_timer.setSingleShot(True)
        self._neu_timer.setInterval(500)
        self._neu_timer.timeout.connect(self._bildschirme_neu)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self._neu_timer.start())
        app.screenRemoved.connect(lambda _s: self._neu_timer.start())
        app.primaryScreenChanged.connect(lambda _s: self._neu_timer.start())
        self._erkennen()

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
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.clear()
        for m in self._monitors:
            self._monitor_combo.addItem(m["name"])
        self._monitor_combo.blockSignals(False)

    def _lade_bildschirme(self):
        self._screens = QGuiApplication.screens()
        self._bildschirme = beschreibe(self._screens)
        self._screen_labels = []
        primary = QGuiApplication.primaryScreen()
        for s, b in zip(self._screens, self._bildschirme):
            pw, ph = b["px"]
            dpr = s.devicePixelRatio()
            label = f"{b['name']} — {pw}×{ph} px"
            if abs(dpr - 1.0) > 0.01:
                label += f" (@{dpr:.2g}×)"
            if s is primary:
                label += "  · primär"
            self._screen_labels.append(label)
            # Auflösung umgestellt (z. B. Retina-Skalierung) → neu erkennen
            if s not in self._beobachtet:
                s.geometryChanged.connect(lambda _g: self._neu_timer.start())
                self._beobachtet.append(s)
        self._screen_combo.blockSignals(True)
        self._screen_combo.clear()
        self._screen_combo.addItems(self._screen_labels)
        self._screen_combo.blockSignals(False)

    def _bildschirme_neu(self):
        self._lade_bildschirme()
        self._erkennen()

    def _erkennen(self):
        """Erfasste Monitore den angeschlossenen Bildschirmen zuordnen und das passende Paar vorwählen."""
        self._zu = zuordnung(self._monitors, self._bildschirme)
        an = {bi: mi for mi, bi in self._zu.items()}
        for mi, m in enumerate(self._monitors):
            self._monitor_combo.setItemText(mi, m["name"] if mi in self._zu else f"{m['name']}  · nicht angeschlossen")
        for bi, label in enumerate(self._screen_labels):
            zusatz = f"  → {self._monitors[an[bi]]['name']}" if bi in an else "  · nicht erfasst"
            self._screen_combo.setItemText(bi, label + zusatz)
        mi = self._monitor_combo.currentIndex()
        if mi not in self._zu and self._zu:
            mi = min(self._zu)
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.setCurrentIndex(mi)
        self._monitor_combo.blockSignals(False)
        self._monitor_gewaehlt()

    def _monitor_gewaehlt(self):
        bi = self._zu.get(self._monitor_combo.currentIndex())
        if bi is not None:
            self._screen_combo.blockSignals(True)
            self._screen_combo.setCurrentIndex(bi)
            self._screen_combo.blockSignals(False)
        self._aktualisiere_erkennung()
        self._aktualisiere_oiq_info()

    def _bildschirm_gewaehlt(self):
        bi = self._screen_combo.currentIndex()
        mi = next((m for m, b in self._zu.items() if b == bi), None)
        if mi is not None and mi != self._monitor_combo.currentIndex():
            self._monitor_combo.blockSignals(True)
            self._monitor_combo.setCurrentIndex(mi)
            self._monitor_combo.blockSignals(False)
        self._aktualisiere_erkennung()
        self._aktualisiere_oiq_info()

    def _abweichungen(self) -> list[str]:
        """Warum der gewählte Bildschirm nicht zum gewählten Monitor passt; [] = passt."""
        mi, bi = self._monitor_combo.currentIndex(), self._screen_combo.currentIndex()
        if not (0 <= mi < len(self._monitors) and 0 <= bi < len(self._bildschirme)):
            return []
        gruende = abweichungen(self._monitors[mi], self._bildschirme[bi])
        andere = next((m for m, b in self._zu.items() if b == bi and m != mi), None)
        if andere is not None:
            gruende.insert(0, f"Dieser Bildschirm ist als «{self._monitors[andere]['name']}» erfasst.")
        return gruende

    def _aktualisiere_erkennung(self):
        mi = self._monitor_combo.currentIndex()
        if not (0 <= mi < len(self._monitors)):
            text, farbe = "Noch kein Monitor erfasst — bitte unter Einstellungen › Monitore eintragen.", "#8b6914"
        else:
            name = self._monitors[mi]["name"]
            gruende = self._abweichungen()
            if mi not in self._zu:
                text = f"⚠  «{name}» ist nicht angeschlossen. " + " ".join(gruende)
                farbe = "#8b6914"
            elif gruende:
                text, farbe = "⚠  " + " ".join(gruende), "#8b6914"
            else:
                b = self._bildschirme[self._screen_combo.currentIndex()]
                text, farbe = f"✓  «{name}» erkannt an «{b['name']}».", "#1a6b2e"
        self._erkennung_lbl.setText(text)
        self._erkennung_lbl.setStyleSheet(f"color: {farbe}; font-size: 12px;")

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
        pw, ph = pixelgroesse(self._ziel_screen())
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
                monitor_item = QTableWidgetItem(row["monitor"])
                if row.get("bildschirm"):
                    monitor_item.setToolTip(f"Geprüft an: {row['bildschirm']}")
                self._table.setItem(i, 1, monitor_item)
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
        mi = self._monitor_combo.currentIndex()
        if not (0 <= mi < len(self._monitors)):
            QMessageBox.information(self, "Kein Monitor", "Bitte zuerst unter Einstellungen › Monitore einen Monitor erfassen.")
            return
        monitor = self._monitors[mi]
        monitor_name = monitor["name"]
        bi = self._screen_combo.currentIndex()
        bildschirm = self._bildschirme[bi] if 0 <= bi < len(self._bildschirme) else None
        gruende = self._abweichungen()
        if gruende:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Monitor und Bildschirm passen nicht zusammen")
            box.setText(f"Geprüft wird «{monitor_name}», angezeigt würde das Testbild aber auf "
                        f"«{bildschirm['name'] if bildschirm else '?'}».")
            richtig = self._zu.get(mi)
            if richtig is None:
                hinweis = (f"«{monitor_name}» wird an keinem angeschlossenen Bildschirm erkannt. Wurde er ersetzt, "
                           "ihn unter Einstellungen › Monitore neu erfassen (nach einem Ersatz ist eine "
                           "Abnahmeprüfung fällig).")
            else:
                hinweis = f"«{monitor_name}» ist an «{self._bildschirme[richtig]['name']}» angeschlossen."
            box.setInformativeText("\n".join(gruende) + "\n\n" + hinweis)
            wechseln = None
            if richtig is not None and richtig != bi:
                wechseln = box.addButton(f"Auf «{self._bildschirme[richtig]['name']}» prüfen",
                                         QMessageBox.ButtonRole.AcceptRole)
            trotzdem = box.addButton("Trotzdem hier prüfen", QMessageBox.ButtonRole.DestructiveRole)
            abbrechen = box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(wechseln or abbrechen)
            box.setEscapeButton(abbrechen)
            box.exec()
            if wechseln is not None and box.clickedButton() is wechseln:
                self._screen_combo.setCurrentIndex(richtig)
                return self._pruefung_starten()
            if box.clickedButton() is not trotzdem:
                return
        bild_idx = self._bild_combo.currentIndex()
        bild_info = self._testbilder[bild_idx]
        target_screen = self._ziel_screen()
        pw, ph = pixelgroesse(target_screen)
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
        self._aktueller_bildschirm = ""
        self._kennung_lernen = None
        if bildschirm:
            w, h = bildschirm["px"]
            self._aktueller_bildschirm = f"{bildschirm['name']}, {w}×{h} px" + (" (Abweichung bestätigt)" if gruende else "")
            # Passendes Paar ohne gespeicherte Kennung → nach der Prüfung merken, ab dann eindeutig
            if not gruende and not monitor.get("kennung"):
                self._kennung_lernen = (monitor_name, kennung(bildschirm))
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
                    bildschirm=self._aktueller_bildschirm,
                )
                self._kennung_merken()
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

    def _kennung_merken(self):
        if not self._kennung_lernen:
            return
        name, k = self._kennung_lernen
        self._kennung_lernen = None
        monitore = load_monitors()
        treffer = [m for m in monitore if m["name"] == name and not m.get("kennung")]
        if len(treffer) == 1:
            treffer[0]["kennung"] = k
            save_monitors(monitore)
            self._lade_monitore()
            self._erkennen()

    def _audit_report(self):
        dlg = AuditDialog(self._config, self)
        dlg.exec()

    def _einstellungen(self):
        try:
            dlg = SettingsDialog(self._config, self)
            if dlg.exec() == SettingsDialog.DialogCode.Accepted:
                self._config = load_config()
                self._lade_monitore()
                self._erkennen()
                self._praxis_lbl.setText(self._config.get("praxis_name", ""))
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

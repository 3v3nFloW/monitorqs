from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QKeySequence, QShortcut


class ImageCanvas(QWidget):
    """Renders pixmap at exact 1:1 pixel mapping, centered, no interpolation."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self.setStyleSheet("background-color: black;")

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        # Zentrieren in logischen Punkten: bei devicePixelRatio>1 (Retina) ist die
        # logische Größe = Pixel / DPR. drawPixmap zeichnet dann 1 Bildpixel = 1 Gerätepixel.
        dip = self._pixmap.deviceIndependentSize()
        x = int((self.width() - dip.width()) / 2)
        y = int((self.height() - dip.height()) / 2)
        painter.drawPixmap(x, y, self._pixmap)


_BTN_ROT = """
    QPushButton {
        background: rgba(255,59,48,210); color: white; border: none;
        border-radius: 12px; padding: 14px 32px;
        font-size: 17px; font-weight: 700;
    }
    QPushButton:hover { background: rgba(255,59,48,255); }
"""
_BTN_GRUEN = """
    QPushButton {
        background: rgba(52,199,89,210); color: white; border: none;
        border-radius: 12px; padding: 14px 32px;
        font-size: 17px; font-weight: 700;
    }
    QPushButton:hover { background: rgba(52,199,89,255); }
"""
_BTN_BLAU = """
    QPushButton {
        background: rgba(0,122,255,210); color: white; border: none;
        border-radius: 12px; padding: 12px 28px;
        font-size: 16px; font-weight: 700;
    }
    QPushButton:hover { background: rgba(0,122,255,255); }
"""


class DisplayWindow(QWidget):
    """Vollbild-Prüfung über ein oder mehrere Testbilder (Schritte).

    Schritt = {"pixmap", "w", "h", "titel", "kriterien": list[dict] | None}.
    Ohne Kriterien (Einzelbild): Leertaste → BESTANDEN / NICHT BESTANDEN.
    Mit Kriterien: Leertaste → Kriterien des Bildes abhaken → Weiter / Abschliessen.
    """
    # bestanden, kriterien (Liste mit "erfuellt" je Kriterium, oder None bei Einzelbild ohne Kriterien)
    pruefung_abgeschlossen = pyqtSignal(bool, object)

    def __init__(self, schritte: list[dict], screen=None, parent=None):
        super().__init__(parent)
        self._screen = screen
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        # Pixmap an das Ziel-Display koppeln: DPR=Panel-Skalierung → echtes 1:1
        # (Retina/DPR 2: 1 Bildpixel = 1 physisches Panelpixel; DPR 1: unverändert).
        for s in schritte:
            s["pixmap"].setDevicePixelRatio(dpr)
        self._schritte = schritte
        self._idx = 0
        self._phase = "ansehen"  # ansehen → bewerten
        self._ergebnisse: list[dict] = []
        self._checkboxen: list[tuple[dict, QCheckBox]] = []
        self._leisten_aus = False
        self._setup_ui()
        self._setup_shortcuts()
        self._zeige_schritt()

    def _setup_ui(self):
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._canvas = ImageCanvas(self._schritte[0]["pixmap"], self)
        layout.addWidget(self._canvas, 1)

        # Hint-Leiste (sichtbar bis Leertaste)
        self._hint_bar = QWidget(self)
        self._hint_bar.setStyleSheet("background-color: rgba(0,0,0,190);")
        hint_layout = QHBoxLayout(self._hint_bar)
        hint_layout.setContentsMargins(28, 12, 28, 12)
        self._hint_lbl = QLabel()
        self._hint_lbl.setStyleSheet("color: rgba(255,255,255,200); font-size: 13px; background: transparent;")
        hint_layout.addWidget(self._hint_lbl)
        hint_layout.addStretch()
        layout.addWidget(self._hint_bar)

        # Kriterien-Leiste (Schritte mit Kriterien, nach Leertaste)
        self._krit_widget = QWidget(self)
        self._krit_widget.setStyleSheet("background-color: rgba(0,0,0,200);")
        self._krit_layout = QVBoxLayout(self._krit_widget)
        self._krit_layout.setContentsMargins(40, 14, 40, 14)
        self._krit_layout.setSpacing(6)
        self._krit_widget.setVisible(False)
        layout.addWidget(self._krit_widget)

        # Bewertungs-Buttons (Einzelbild ohne Kriterien, nach Leertaste)
        self._btn_widget = QWidget(self)
        self._btn_widget.setStyleSheet("background-color: rgba(0,0,0,170);")
        btn_layout = QHBoxLayout(self._btn_widget)
        btn_layout.setContentsMargins(40, 20, 40, 20)
        btn_layout.setSpacing(24)
        btn_layout.addStretch()
        btn_nicht = QPushButton("✗  NICHT BESTANDEN")
        btn_nicht.setStyleSheet(_BTN_ROT)
        btn_nicht.clicked.connect(lambda: self._abschliessen(False, None))
        btn_ok = QPushButton("✓  BESTANDEN")
        btn_ok.setStyleSheet(_BTN_GRUEN)
        btn_ok.clicked.connect(lambda: self._abschliessen(True, None))
        btn_layout.addWidget(btn_nicht)
        btn_layout.addWidget(btn_ok)
        btn_layout.addStretch()
        self._btn_widget.setVisible(False)
        layout.addWidget(self._btn_widget)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._abbrechen)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._leertaste)
        QShortcut(QKeySequence(Qt.Key.Key_H), self, self._leisten_umschalten)

    def _zeige_schritt(self):
        s = self._schritte[self._idx]
        self._canvas.set_pixmap(s["pixmap"])
        self._phase = "ansehen"
        self._leisten_aus = False
        self._krit_widget.setVisible(False)
        self._btn_widget.setVisible(False)

        dpr = self._screen.devicePixelRatio() if self._screen is not None else 1.0
        mapping = "1 Bildpixel = 1 Panelpixel" if abs(dpr - round(dpr)) < 0.01 else \
                  f"⚠ skalierter Modus (DPR {dpr:.2f}) — Display auf native Auflösung stellen!"
        schritt = f"Schritt {self._idx + 1}/{len(self._schritte)}: " if len(self._schritte) > 1 else ""
        weiter = "Kriterien bewerten" if s.get("kriterien") else "Prüfung abgeschlossen?"
        self._hint_lbl.setText(
            f"{schritt}<b>{s['titel']}</b>  |  {s['w']}×{s['h']} px  |  {mapping}  "
            f"|  True Tone / Night Shift aus  |  Leisten aus/ein: <b>H</b>  "
            f"|  {weiter}  →  <b>Leertaste</b>  |  Abbrechen: <b>Esc</b>"
        )
        self._hint_bar.setVisible(True)

    def _leertaste(self):
        if self._phase != "ansehen":
            return
        self._phase = "bewerten"
        self._leisten_aus = False
        self._hint_bar.setVisible(False)
        kriterien = self._schritte[self._idx].get("kriterien")
        if kriterien:
            self._baue_kriterien(kriterien)
            self._krit_widget.setVisible(True)
        else:
            self._btn_widget.setVisible(True)

    def _leisten_umschalten(self):
        """H blendet alle Leisten aus — z. B. um die Ränder der UN80-Fläche ungestört zu beurteilen."""
        self._leisten_aus = not self._leisten_aus
        if self._phase == "ansehen":
            self._hint_bar.setVisible(not self._leisten_aus)
        elif self._schritte[self._idx].get("kriterien"):
            self._krit_widget.setVisible(not self._leisten_aus)
        else:
            self._btn_widget.setVisible(not self._leisten_aus)

    def _baue_kriterien(self, kriterien: list[dict]):
        # Inhalt je Schritt neu aufbauen: alten Container verwerfen
        if getattr(self, "_krit_inhalt", None) is not None:
            self._krit_layout.removeWidget(self._krit_inhalt)
            self._krit_inhalt.hide()
            self._krit_inhalt.deleteLater()
        self._krit_inhalt = QWidget(self._krit_widget)
        self._krit_inhalt.setStyleSheet("background: transparent;")
        inhalt = QVBoxLayout(self._krit_inhalt)
        inhalt.setContentsMargins(0, 0, 0, 0)
        inhalt.setSpacing(6)
        self._krit_layout.addWidget(self._krit_inhalt)
        self._checkboxen = []

        kopf = QLabel(f"<b>{self._schritte[self._idx]['titel']}</b> — erfüllte Kriterien abhaken "
                      f"(nicht abgehakt = nicht erfüllt):")
        kopf.setStyleSheet("color: rgba(255,255,255,220); font-size: 14px; background: transparent;")
        inhalt.addWidget(kopf)
        for k in kriterien:
            cb = QCheckBox(f"{k['id']}  {k['kurz']}: {k['text']}")
            cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Leertaste bleibt beim Fenster
            cb.setStyleSheet(
                "QCheckBox { color: rgba(255,255,255,230); font-size: 14px; background: transparent; spacing: 10px; }"
                "QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,200);"
                " border-radius: 4px; background: transparent; }"
                "QCheckBox::indicator:checked { background: rgb(52,199,89); border-color: rgb(52,199,89); }"
            )
            inhalt.addWidget(cb)
            self._checkboxen.append((k, cb))

        zeile = QHBoxLayout()
        zeile.addStretch()
        letzter = self._idx == len(self._schritte) - 1
        btn = QPushButton("Abschliessen" if letzter else "Weiter  →")
        btn.setStyleSheet(_BTN_BLAU)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(self._kriterien_uebernehmen)
        zeile.addWidget(btn)
        inhalt.addLayout(zeile)

    def _kriterien_uebernehmen(self):
        titel = self._schritte[self._idx]["titel"]
        for k, cb in self._checkboxen:
            self._ergebnisse.append({**k, "testbild": titel, "erfuellt": cb.isChecked()})
        if self._idx < len(self._schritte) - 1:
            self._idx += 1
            self._zeige_schritt()
            return
        bestanden = all(e["erfuellt"] for e in self._ergebnisse)
        self._abschliessen(bestanden, self._ergebnisse)

    def showEvent(self, event):
        screen = self._screen or QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)  # Fullscreen gezielt auf das geprüfte Panel
        self.showFullScreen()

    def _abschliessen(self, bestanden: bool, kriterien):
        self.close()
        self.pruefung_abgeschlossen.emit(bestanden, kriterien)

    def _abbrechen(self):
        self.close()

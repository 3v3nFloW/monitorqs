from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QLineEdit, QPushButton, QCheckBox, QScrollArea, QMessageBox, QFrame
)
from .config_manager import save_config, save_monitors, load_monitors
from .setup_wizard import MonitorListWidget
from .notifications import install_wochenreminder, uninstall_wochenreminder, is_reminder_installed

_STYLE = """
QDialog { background: #F5F5F7; }
QWidget { background: #F5F5F7; }
QLabel { color: #1D1D1F; font-size: 13px; }
QLineEdit {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; padding: 8px 12px;
    color: #1D1D1F; font-size: 14px; min-height: 34px;
}
QTabWidget::pane {
    background: #FFFFFF; border: 1px solid #E5E5EA;
    border-radius: 10px; margin-top: -1px;
}
QTabBar::tab {
    background: #F5F5F7; color: #86868B; border: none;
    padding: 8px 20px; font-size: 13px; font-weight: 500;
}
QTabBar::tab:selected { color: #007AFF; border-bottom: 2px solid #007AFF; }
QTabBar::tab:hover { color: #1D1D1F; }
QScrollArea { border: 1px solid #E5E5EA; border-radius: 10px; background: #FFFFFF; }
QCheckBox { color: #1D1D1F; font-size: 13px; }
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


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self._praxis_tab(), "Praxis & Prüfer")
        tabs.addTab(self._monitore_tab(), "Monitore")
        tabs.addTab(self._benachrichtigungen_tab(), "Benachrichtigungen")
        layout.addWidget(tabs)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E5EA;")
        layout.addWidget(sep)

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

    def _field(self, layout, label, placeholder, value="") -> QLineEdit:
        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        layout.addWidget(lbl)
        layout.addWidget(edit)
        return edit

    def _praxis_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        self._praxis_edit  = self._field(layout, "Praxisname",
                                          "z. B. Tierarztpraxis Mustermann",
                                          self._config.get("praxis_name", ""))
        self._adresse_edit = self._field(layout, "Adresse", "Musterstrasse 1",
                                          self._config.get("adresse", ""))
        self._ortplz_edit  = self._field(layout, "Ort / PLZ", "8000 Zürich",
                                          self._config.get("ort_plz", ""))
        self._bewill_edit  = self._field(layout, "Röntgen-Bewilligung Nr.", "KT-2024-XXXX",
                                          self._config.get("roentgen_bewilligung", ""))
        self._pruefer_edit = self._field(layout, "Prüfer (kommagetrennt)", "z. B. A. Muster, B. Beispiel",
                                          ", ".join(self._config.get("pruefer", [])))
        layout.addStretch()
        return w

    def _monitore_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._monitor_list = MonitorListWidget(load_monitors())
        scroll.setWidget(self._monitor_list)
        layout.addWidget(scroll)
        return w

    def _benachrichtigungen_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("Wöchentliche Erinnerung")
        lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1D1D1F;")
        layout.addWidget(lbl)

        info = QLabel(
            "Jeden Donnerstag um 09:00 Uhr öffnet sich MonitorQS automatisch und\n"
            "meldet sich per Benachrichtigung — aber nur, wenn in der laufenden\n"
            "Woche noch keine Prüfung erfasst wurde. Sonst passiert nichts."
        )
        info.setStyleSheet("color: #86868B; font-size: 13px;")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E5EA;")
        layout.addWidget(sep)

        self._reminder_check = QCheckBox("Wöchentliche Erinnerung aktivieren")
        self._reminder_check.setChecked(is_reminder_installed())
        layout.addWidget(self._reminder_check)
        layout.addStretch()
        return w

    def _speichern(self):
        config = self._config.copy()
        config["praxis_name"] = self._praxis_edit.text().strip()
        config["adresse"] = self._adresse_edit.text().strip()
        config["ort_plz"] = self._ortplz_edit.text().strip()
        config["roentgen_bewilligung"] = self._bewill_edit.text().strip()
        config["pruefer"] = [p.strip() for p in self._pruefer_edit.text().split(",") if p.strip()]

        monitors = self._monitor_list.get_monitors()
        if not monitors:
            QMessageBox.warning(self, "Kein Monitor", "Bitte mindestens einen Monitor eintragen.")
            return

        try:
            save_config(config)
            save_monitors(monitors)

            if self._reminder_check.isChecked() and not is_reminder_installed():
                install_wochenreminder()
            elif not self._reminder_check.isChecked() and is_reminder_installed():
                uninstall_wochenreminder()
        except Exception as exc:
            QMessageBox.critical(self, "Fehler beim Speichern", str(exc))
            return

        self._config = config
        self.accept()

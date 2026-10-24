import sys
from PyQt6.QtWidgets import QApplication
from app.config_manager import load_config
from app.setup_wizard import SetupWizard
from app.main_window import MainWindow
from app.log_manager import init_db, hat_pruefung_diese_woche
from app.notifications import send_notification, ALT_PLIST_PATH, install_wochenreminder


def main():
    reminder_mode = "--reminder" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("MonitorQS")
    app.setOrganizationName("Kappa1")

    init_db()
    # Reminder aus v3.1 (Label com.monitorqs…) auf das neue Label umziehen
    if ALT_PLIST_PATH.exists():
        install_wochenreminder()
    # Reminder-Start (Do 09:00): wenn diese Woche schon geprüft → still beenden
    if reminder_mode and hat_pruefung_diese_woche():
        return

    config = load_config()
    if not config.get("setup_done"):
        wizard = SetupWizard(config)
        if wizard.exec() != SetupWizard.DialogCode.Accepted:
            sys.exit(0)
        config = load_config()

    window = MainWindow()
    window.show()

    if reminder_mode:
        window.raise_()
        window.activateWindow()
        send_notification("MonitorQS", "Wöchentliche Konstanzprüfung fällig — bitte Monitor prüfen.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

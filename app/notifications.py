import sys
import subprocess
import plistlib
from pathlib import Path


LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LABEL = "vet.kappa1.monitorqs.wochenreminder"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"
# Bis v3.1: eigene Domain vorgegeben → beim Ein-/Ausschalten aufräumen
ALT_PLIST_PATH = LAUNCH_AGENTS_DIR / "com.monitorqs.wochenreminder.plist"
BUNDLE_ID = "vet.kappa1.monitorqs"

# Wöchentlicher Reminder: Donnerstag 09:00
REMINDER_WEEKDAY = 4  # launchd: 1=Mo … 4=Do
REMINDER_HOUR = 9
REMINDER_MINUTE = 0


def send_notification(titel: str, text: str):
    # Texte als Argumente, nie in den Skripttext — Monitornamen dürfen Anführungszeichen enthalten
    script = "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"
    subprocess.run(["osascript", "-e", script, titel, text], check=False)


def _app_launch_args() -> list[str]:
    """Öffnet die MonitorQS.app im Reminder-Modus.

    Im gefrorenen Bundle wird der reale .app-Pfad eingetragen (robust auch wenn
    die App nicht in /Applications liegt). Im Dev-Betrieb Fallback über Bundle-ID.
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        for p in exe.parents:
            if p.suffix == ".app":
                return ["/usr/bin/open", str(p), "--args", "--reminder"]
    return ["/usr/bin/open", "-b", BUNDLE_ID, "--args", "--reminder"]


def _alten_reminder_entfernen():
    if ALT_PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(ALT_PLIST_PATH)], check=False)
        ALT_PLIST_PATH.unlink()


def install_wochenreminder():
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    _alten_reminder_entfernen()
    plist = {
        "Label": LABEL,
        "ProgramArguments": _app_launch_args(),
        # Donnerstag 09:00 — verpasste Läufe (Mac aus/schlafend) holt launchd nach dem Aufwachen nach
        "StartCalendarInterval": {
            "Weekday": REMINDER_WEEKDAY,
            "Hour": REMINDER_HOUR,
            "Minute": REMINDER_MINUTE,
        },
        "RunAtLoad": False,
    }
    # Vorhandene (evtl. veraltete) Variante zuerst entladen, dann neu laden
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)


def uninstall_wochenreminder():
    _alten_reminder_entfernen()
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        PLIST_PATH.unlink()


def is_reminder_installed() -> bool:
    return PLIST_PATH.exists() or ALT_PLIST_PATH.exists()

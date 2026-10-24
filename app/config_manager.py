import json
import os
from pathlib import Path

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "MonitorQS"
CONFIG_FILE = APP_SUPPORT_DIR / "config.json"
MONITORS_FILE = APP_SUPPORT_DIR / "monitors.json"

DEFAULT_CONFIG = {
    "praxis_name": "",
    "adresse": "",
    "ort_plz": "",
    "roentgen_bewilligung": "",
    "pruefer": [],
    "setup_done": False
}



def ensure_app_support_dir():
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_app_support_dir()
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    for key, val in DEFAULT_CONFIG.items():
        data.setdefault(key, val)
    return data


def save_config(config: dict):
    ensure_app_support_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_monitors():
    ensure_app_support_dir()
    if not MONITORS_FILE.exists():
        return []
    with open(MONITORS_FILE) as f:
        return json.load(f)


def save_monitors(monitors: list):
    ensure_app_support_dir()
    with open(MONITORS_FILE, "w") as f:
        json.dump(monitors, f, indent=2, ensure_ascii=False)

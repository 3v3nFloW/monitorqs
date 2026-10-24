"""AAPM-TG18-Testmuster: beim ersten Start von Duke RAI Labs laden statt mitliefern.

Die Muster sind von der AAPM urheberrechtlich geschützt; Duke erlaubt die Nutzung unverändert und
mit Label, äussert sich aber nicht zur Weitergabe. Darum lädt jede Installation sie selbst, geprüft
per SHA-256, und legt sie unverändert in Application Support ab.
"""
import hashlib
import os
import shutil
import ssl
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Optional
from zipfile import BadZipFile, ZipFile

TESTBILDER_DIR = Path.home() / "Library" / "Application Support" / "MonitorQS" / "Testbilder"
OIQ_DIR = TESTBILDER_DIR / "OIQ"
QC_DIR = TESTBILDER_DIR / "QC"
QUELLE_URL = "https://rai.labs.duke.edu/resources/tg-18-assessment-of-display-performance-for-medical-imaging-systems/"
ZITAT = ("Samei E, Badano A, Chakraborty D, et al. Assessment of Display Performance for Medical Imaging Systems, "
         "Report of the American Association of Physicists in Medicine (AAPM) Task Group 18, Medical Physics "
         "Publishing, Madison, WI, AAPM On-Line Report No. 03, April 2005.")

MAX_PAKET = 50 * 1024 * 1024
MAX_DATEI = 20 * 1024 * 1024

PAKETE = [
    {"name": "TG18-OIQ (alle Grössen)",
     "url": "https://duke.box.com/shared/static/9pxei012y38foes4o8k47rqh0cjb7lva.zip",
     "sha256": "ab0f822404c26e3de0ba3d3cbc5c824aaef6c2832cb7b257a6066d0d864750b0",
     "ziel": OIQ_DIR, "muster": "TG18-OIQ-*.dcm", "anzahl": 10},
    {"name": "TG18-QC 2k",
     "url": "https://duke.box.com/shared/static/kye5ocoxw4zu6u5ii0ht97j7eagxppn9.zip",
     "sha256": "c341558c09e3c1c073c471f13152c017a0b4b5d3f6ee55fb40b539e622c6b422",
     "ziel": QC_DIR, "muster": "TG18-QC-*.dcm", "anzahl": 1},
]


class TestbildFehler(Exception):
    """Download, Prüfsumme oder Inhalt der Testmuster stimmen nicht."""


def vorhanden() -> bool:
    """True, wenn alle Pakete vollständig in Application Support liegen."""
    return all(p["ziel"].is_dir() and len(list(p["ziel"].glob(p["muster"]))) >= p["anzahl"] for p in PAKETE)


def _ssl_kontext() -> ssl.SSLContext:
    # Gefrorenes Bundle bringt keine System-CAs für Python mit → certifi, wenn vorhanden
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _laden(paket: dict, datei: Path, ctx: ssl.SSLContext, melde: Callable[[float], None]) -> None:
    req = urllib.request.Request(paket["url"], headers={"User-Agent": "MonitorQS"})
    sha = hashlib.sha256()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as antwort, open(datei, "wb") as f:
        laenge = int(antwort.getheader("Content-Length") or 0)
        geladen = 0
        while block := antwort.read(64 * 1024):
            geladen += len(block)
            if geladen > MAX_PAKET:
                raise TestbildFehler(f"{paket['name']}: Download grösser als erwartet, abgebrochen.")
            sha.update(block)
            f.write(block)
            if laenge:
                melde(min(geladen / laenge, 1.0))
    if sha.hexdigest() != paket["sha256"]:
        raise TestbildFehler(f"{paket['name']}: Prüfsumme stimmt nicht — Datei wurde nicht übernommen. "
                             f"Bitte später erneut versuchen oder die Muster von Hand von {QUELLE_URL} laden.")


def _entpacken(paket: dict, zip_datei: Path, ziel_tmp: Path) -> None:
    """Nur passende .dcm, nur Basisnamen (kein Zip-Slip), je Datei mit Grössengrenze."""
    ziel_tmp.mkdir()
    try:
        with ZipFile(zip_datei) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name
                if info.is_dir() or not fnmatch(name, paket["muster"]):
                    continue
                if info.file_size > MAX_DATEI:
                    raise TestbildFehler(f"{paket['name']}: {name} ist unerwartet gross.")
                with zf.open(info) as quelle, open(ziel_tmp / name, "wb") as ziel:
                    shutil.copyfileobj(quelle, ziel)
    except BadZipFile as e:
        raise TestbildFehler(f"{paket['name']}: Archiv beschädigt ({e}).") from e
    n = len(list(ziel_tmp.glob(paket["muster"])))
    if n != paket["anzahl"]:
        raise TestbildFehler(f"{paket['name']}: {paket['anzahl']} Dateien erwartet, {n} gefunden.")


def herunterladen(fortschritt: Optional[Callable[[str, float], None]] = None) -> None:
    """Lädt alle Pakete, prüft sie und ersetzt die Zielordner erst, wenn alles stimmt."""
    TESTBILDER_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=TESTBILDER_DIR, prefix=".laden-"))
    ctx = _ssl_kontext()
    n = len(PAKETE)
    try:
        bereit = []
        for i, paket in enumerate(PAKETE):
            def melde(anteil: float, i=i, name=paket["name"]):
                if fortschritt:
                    fortschritt(f"{name} wird geladen …", (i + anteil) / n)
            melde(0.0)
            zip_datei = tmp / f"paket-{i}.zip"
            try:
                _laden(paket, zip_datei, ctx, melde)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise TestbildFehler(f"Download fehlgeschlagen: {e}") from e
            ziel_tmp = tmp / f"inhalt-{i}"
            _entpacken(paket, zip_datei, ziel_tmp)
            bereit.append((ziel_tmp, paket["ziel"]))

        for ziel_tmp, ziel in bereit:
            if ziel.exists():
                shutil.rmtree(ziel)
            os.replace(ziel_tmp, ziel)

        zeilen = [f"Quelle: {QUELLE_URL}", f"Zitat: {ZITAT}",
                  f"Geladen: {datetime.now().isoformat(timespec='seconds')}", ""]
        zeilen += [f"{p['name']}: {p['url']}\n  SHA-256 {p['sha256']}" for p in PAKETE]
        zeilen += ["", "Unverändert von Duke RAI Labs übernommen; Copyright AAPM."]
        (TESTBILDER_DIR / "QUELLE.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        if fortschritt:
            fortschritt("Fertig", 1.0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

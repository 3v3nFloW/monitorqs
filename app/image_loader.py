from pathlib import Path
import numpy as np
from PIL import Image
import pydicom
from pydicom.pixel_data_handlers.util import apply_modality_lut, apply_voi_lut
from PyQt6.QtGui import QImage, QPixmap

from .testbilder import OIQ_DIR, QC_DIR

# TG18-UN80: 80 % der maximalen Ansteuerung = DDL 204 (BAG-Wegleitung Tabelle B)
UN80_DDL = 204


def list_testbilder() -> list[dict]:
    """Auswahl für die Prüfung. Erster Eintrag = Standard-Ablauf nach BAG-Wegleitung."""
    bilder = []
    if _oiq_varianten():
        bilder.append({"name": "Konstanzprüfung BAG (TG18-OIQ + TG18-UN80)", "pfad": "", "typ": "bag"})
        bilder.append({"name": "TG18-OIQ (Grösse passend zum Bildschirm)", "pfad": "", "typ": "oiq"})
    bilder.append({"name": "TG18-UN80 (bildschirmfüllend)", "pfad": "", "typ": "un80"})
    if QC_DIR.exists():
        for dcm in sorted(QC_DIR.glob("TG18-QC-*.dcm")):
            bilder.append({"name": dcm.stem, "pfad": str(dcm), "typ": "dicom"})
    return bilder


def _oiq_varianten() -> list[tuple[int, int, Path]]:
    """(breite, höhe, pfad) aller TG18-OIQ-DICOMs; Grösse aus dem Header, ohne Pixeldaten."""
    varianten = []
    if OIQ_DIR.exists():
        for dcm in sorted(OIQ_DIR.glob("TG18-OIQ-*.dcm")):
            ds = pydicom.dcmread(dcm, stop_before_pixels=True)
            varianten.append((int(ds.Columns), int(ds.Rows), dcm))
    return varianten


def waehle_oiq(panel_w: int, panel_h: int) -> Path | None:
    """Grösste OIQ-Variante, die 1:1 vollständig aufs Panel passt (L/P ergibt sich daraus)."""
    passend = [v for v in _oiq_varianten() if v[0] <= panel_w and v[1] <= panel_h]
    if not passend:
        return None
    return max(passend, key=lambda v: v[0] * v[1])[2]


def un80_qpixmap(w: int, h: int) -> tuple[QPixmap, int, int]:
    """Bildschirmfüllende TG18-UN80-Fläche (DDL 204) in Panelpixeln."""
    return _to_qpixmap(np.full((h, w), UN80_DDL, dtype=np.uint8))


def load_as_qpixmap(pfad: str) -> tuple[QPixmap, int, int]:
    """Returns (pixmap, width, height). Guarantees 1:1 pixel data, no interpolation."""
    return _to_qpixmap(load_as_array(pfad))


def load_as_array(pfad: str) -> np.ndarray:
    """Testbild als 2D-uint8 (0 = schwarz, 255 = weiss)."""
    if Path(pfad).suffix.lower() == ".dcm":
        return _load_dicom(pfad)
    return _load_png(pfad)


def _to_qpixmap(arr: np.uint8) -> tuple[QPixmap, int, int]:
    """arr: contiguous 2D uint8. QImage borrows the buffer, QPixmap.fromImage copies it."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape
    qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(qimg.copy()), w, h


def _load_png(pfad: str) -> np.ndarray:
    img = Image.open(pfad)
    if img.mode not in ("L", "I;16", "I"):
        img = img.convert("L")
    arr = np.asarray(img)
    if arr.dtype != np.uint8:
        # 16-bit PNG: map full stored range deterministically (not min/max of data)
        maxval = float(np.iinfo(arr.dtype).max) if np.issubdtype(arr.dtype, np.integer) else float(arr.max() or 1)
        arr = np.clip(arr.astype(np.float32) / maxval, 0, 1) * 255
        arr = arr.astype(np.uint8)
    return arr


def _bit_bereich(bits: int, signed: bool) -> tuple[float, float]:
    if signed:
        return float(-(2 ** (bits - 1))), float(2 ** (bits - 1) - 1)
    return 0.0, float(2 ** bits - 1)


def _load_dicom(pfad: str) -> np.ndarray:
    ds = pydicom.dcmread(pfad)
    arr = ds.pixel_array
    if arr.ndim == 3:  # multiframe → erster Frame genügt für ein Testmuster
        arr = arr[0]

    # 1) Modality-LUT: RescaleSlope/Intercept anwenden (Stored Values → echte Werte)
    arr = apply_modality_lut(arr, ds)

    # 2) Definierte Grauwert-Abbildung — Bereich immer aus den Tags, nie aus den Daten
    #    (sonst würde z. B. eine gleichmässige 80-%-Fläche zu Weiss gestreckt).
    bits = int(getattr(ds, "BitsStored", 0)) or 16
    signed = int(getattr(ds, "PixelRepresentation", 0)) == 1
    if "WindowCenter" in ds:
        # pydicom-Fensterung gibt den vollen Bereich der gespeicherten Bittiefe aus
        arr = apply_voi_lut(arr, ds).astype(np.float32)
        lo, hi = _bit_bereich(bits, signed)
    elif "VOILUTSequence" in ds:
        lut_bits = int(ds.VOILUTSequence[0].LUTDescriptor[2])
        arr = apply_voi_lut(arr, ds).astype(np.float32)
        lo, hi = 0.0, float(2 ** lut_bits - 1)
    else:
        arr = arr.astype(np.float32)
        lo, hi = _bit_bereich(bits, signed)
        # TG18-OIQ: BitsStored 16, Werte 0–4095 → Largest/SmallestImagePixelValue gibt den Bereich vor
        if "LargestImagePixelValue" in ds:
            hi = float(ds.LargestImagePixelValue)
            lo = float(getattr(ds, "SmallestImagePixelValue", lo if signed else 0))

    rng = hi - lo
    if rng <= 0:
        rng = 1.0
    out = (np.clip((arr - lo) / rng, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)

    # 3) MONOCHROME1 (0 = weiss) korrekt invertieren
    if str(getattr(ds, "PhotometricInterpretation", "")).strip() == "MONOCHROME1":
        out = 255 - out

    return out

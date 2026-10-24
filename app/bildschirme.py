"""Welcher erfasste Monitor hängt an welchem Bildschirm?

Qt liefert unter macOS nur den Produktnamen (z. B. «LS49A950U»). Hersteller-, Modell- und Seriennummer
kommen aus CoreGraphics; damit lassen sich auch zwei baugleiche Monitore auseinanderhalten. Die Kennung
wird nur lokal in monitors.json abgelegt, nie im Logbuch oder im Report.
"""
import ctypes

_CG_PFAD = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


def _cg_displays() -> list[dict]:
    """Aktive Displays laut CoreGraphics: Lage in Punkten + Hersteller/Modell/Seriennummer. [] ausserhalb macOS."""
    try:
        cg = ctypes.CDLL(_CG_PFAD)
    except OSError:
        return []
    cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint32)]
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    cg.CGDisplayBounds.restype = _CGRect
    for fn in ("CGDisplayVendorNumber", "CGDisplayModelNumber", "CGDisplaySerialNumber", "CGDisplayIsBuiltin"):
        getattr(cg, fn).argtypes = [ctypes.c_uint32]
        getattr(cg, fn).restype = ctypes.c_uint32
    ids = (ctypes.c_uint32 * 16)()
    n = ctypes.c_uint32(0)
    if cg.CGGetActiveDisplayList(16, ids, ctypes.byref(n)) != 0:
        return []
    displays = []
    for did in ids[:n.value]:
        r = cg.CGDisplayBounds(did)
        displays.append({
            "lage": (round(r.origin.x), round(r.origin.y), round(r.size.width), round(r.size.height)),
            "hersteller": cg.CGDisplayVendorNumber(did),
            "modell": cg.CGDisplayModelNumber(did),
            "seriennr": cg.CGDisplaySerialNumber(did),
            "eingebaut": bool(cg.CGDisplayIsBuiltin(did)),
        })
    return displays


def pixelgroesse(screen) -> tuple[int, int]:
    """Physische (Geräte-)Pixelmasse eines Screens: logische Grösse × devicePixelRatio."""
    geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    return round(geo.width() * dpr), round(geo.height() * dpr)


def parse_aufloesung(text: str) -> tuple[int, int] | None:
    """'5120x1440' / '5120 × 2880' → (5120, 1440); None wenn nicht parsebar."""
    if not text:
        return None
    parts = text.lower().replace("×", "x").replace(" ", "").split("x")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return None


def beschreibe(screens) -> list[dict]:
    """Je QScreen ein Dict mit Name, Pixelgrösse und — soweit CoreGraphics sie kennt — der Kennung.

    QScreen.geometry() und CGDisplayBounds teilen sich unter macOS dasselbe Koordinatensystem (Punkte,
    Ursprung oben links am Hauptbildschirm); darüber werden die beiden Listen verknüpft.
    """
    cg = {d["lage"]: d for d in _cg_displays()}
    result = []
    for s in screens:
        geo = s.geometry()
        d = cg.get((geo.x(), geo.y(), geo.width(), geo.height()), {})
        result.append({
            "name": s.name(),
            "px": pixelgroesse(s),
            "hersteller": d.get("hersteller", 0),
            "modell": d.get("modell", 0),
            "seriennr": d.get("seriennr", 0),
            "eingebaut": d.get("eingebaut", False),
        })
    return result


def kennung(bildschirm: dict) -> dict:
    """Was in monitors.json gespeichert wird, um den Bildschirm wiederzuerkennen."""
    return {k: bildschirm[k] for k in ("name", "hersteller", "modell", "seriennr")}


def _gleiches_geraet(k: dict, b: dict) -> bool:
    if k.get("seriennr") and b.get("seriennr"):
        return (k.get("hersteller"), k.get("modell"), k["seriennr"]) == (b["hersteller"], b["modell"], b["seriennr"])
    if k.get("hersteller") and b.get("hersteller"):
        return (k["hersteller"], k.get("modell")) == (b["hersteller"], b["modell"])
    return bool(k.get("name")) and k.get("name") == b.get("name")


def zuordnung(monitore: list[dict], bildschirme: list[dict]) -> dict[int, int]:
    """Monitor-Index → Bildschirm-Index für alle angeschlossenen Monitore.

    Zuerst über die gespeicherte Kennung; Monitore ohne Kennung nur dann über die Auflösung, wenn genau
    ein noch freier Bildschirm sie hat — bei zwei gleich grossen Panels wird nicht geraten.
    """
    zu, belegt = {}, set()
    for mi, m in enumerate(monitore):
        k = m.get("kennung")
        if not k:
            continue
        for bi, b in enumerate(bildschirme):
            if bi not in belegt and _gleiches_geraet(k, b):
                zu[mi] = bi
                belegt.add(bi)
                break
    for mi, m in enumerate(monitore):
        if m.get("kennung") or mi in zu:
            continue
        ziel = parse_aufloesung(m.get("aufloesung", ""))
        kandidaten = [bi for bi, b in enumerate(bildschirme) if bi not in belegt and b["px"] == ziel]
        if ziel and len(kandidaten) == 1:
            zu[mi] = kandidaten[0]
            belegt.add(kandidaten[0])
    return zu


def abweichungen(monitor: dict, bildschirm: dict) -> list[str]:
    """Gründe, warum der Bildschirm nicht zum erfassten Monitor passt; [] = passt."""
    gruende = []
    k = monitor.get("kennung")
    if k and not _gleiches_geraet(k, bildschirm) and k.get("name") == bildschirm["name"]:
        gruende.append(f"Am gewählten Bildschirm hängt ein anderes Gerät desselben Modells «{bildschirm['name']}» "
                       f"(Seriennummer weicht ab) — nicht der für «{monitor['name']}» erfasste Monitor.")
    elif k and not _gleiches_geraet(k, bildschirm):
        gruende.append(f"Am gewählten Bildschirm hängt «{bildschirm['name']}», für «{monitor['name']}» "
                       f"ist aber «{k.get('name') or 'ein anderes Gerät'}» erfasst.")
    ziel = parse_aufloesung(monitor.get("aufloesung", ""))
    w, h = bildschirm["px"]
    if ziel and ziel != (w, h):
        gruende.append(f"Der Bildschirm läuft mit {w}×{h} px, erfasst sind {ziel[0]}×{ziel[1]} px.")
    return gruende

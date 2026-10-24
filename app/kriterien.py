"""Visuelle Prüfkriterien der Konstanzprüfung — BAG-Wegleitung Befundmonitore V3 (20.03.2025), Tabelle C.

Tabelle C: Gesamtbildqualität 8.2.2 a), b), c), e), g) am TG18-OIQ;
Homogenität der Leuchtdichte 8.2.4 und Farbeindruck/Gleichmässigkeit 8.2.5 am TG18-UN80.
"""

RAUMKLASSEN = ["", "RK1", "RK2", "RK3"]

# Element 3, schwarzes Feld: mindestens zu erkennen je Raumklasse
_SCHWARZ_JE_RK = {
    "RK1": "«QUALITY CONTRO»",
    "RK2": "«QUALITY CONT»",
    "RK3": "«QUALITY CON»",
}


def oiq_kriterien(raumklasse: str = "") -> list[dict]:
    if raumklasse in _SCHWARZ_JE_RK:
        schwarz = f"im schwarzen Feld mindestens {_SCHWARZ_JE_RK[raumklasse]} ({raumklasse})"
    else:
        schwarz = ("im schwarzen Feld mindestens RK1 «QUALITY CONTRO» / RK2 «QUALITY CONT» / "
                   "RK3 «QUALITY CON»")
    return [
        {"id": "8.2.2 a", "kurz": "Linienpaar-Raster",
         "text": "Linienpaar-Raster in der Mitte und in den vier Ecken unverfälscht sichtbar, "
                 "auch die mit niedrigem Kontrast — ohne Schlieren, Verwischungen, Auslöschungen"},
        {"id": "8.2.2 b", "kurz": "5 %- und 95 %-Felder",
         "text": "5 %- und 95 %-Feld sichtbar"},
        {"id": "8.2.2 c", "kurz": "«QUALITY CONTROL»",
         "text": f"Im weissen und grauen Feld «QUALITY CONTROL» vollständig; {schwarz}"},
        {"id": "8.2.2 e", "kurz": "Linien des Rasters",
         "text": "Grenzen und Linien des Rasters sichtbar, Raster zentriert im aktiven Bereich"},
        {"id": "8.2.2 g", "kurz": "Verlaufsbalken",
         "text": "Verlaufsbalken kontinuierlich, ohne Stufen oder Bänder"},
    ]


def un80_kriterien() -> list[dict]:
    return [
        {"id": "8.2.4", "kurz": "Homogenität der Leuchtdichte",
         "text": "Fläche überall gleich hell — keine Flecken, Wolken, Schatten oder dunklen Ränder/Ecken"},
        {"id": "8.2.5", "kurz": "Farbeindruck und Gleichmässigkeit",
         "text": "Neutrales Grau ohne Farbstich, Farbton über die ganze Fläche gleich"},
    ]

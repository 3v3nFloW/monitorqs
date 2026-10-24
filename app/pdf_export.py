from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


OUTPUT_DIR = Path.home() / "Documents" / "MonitorQS" / "Berichte"


def generiere_audit_report(config: dict, pruefungen: list, jahr: int) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dateiname = OUTPUT_DIR / f"QS_Monitor_Bericht_{jahr}.pdf"

    doc = SimpleDocTemplate(
        str(dateiname),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f"Qualitätssicherung Monitore {jahr}",
        author=config.get("praxis_name", "")
    )

    styles = getSampleStyleSheet()
    titel_style = ParagraphStyle("Titel", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=14, spaceAfter=4)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10, textColor=colors.gray)
    normal = styles["Normal"]

    story = []

    story.append(Paragraph("Konstanzprüfung medizinischer Bildwiedergabesysteme", titel_style))
    story.append(Paragraph("gemäss Schweizer Röntgenverordnung (RöV / BAG)", sub_style))
    story.append(Spacer(1, 0.4*cm))

    praxis_data = [
        ["Praxis:", config.get("praxis_name", "–")],
        ["Adresse:", config.get("adresse", "–")],
        ["Ort / PLZ:", config.get("ort_plz", "–")],
        ["Röntgen-Bewilligung:", config.get("roentgen_bewilligung", "–")],
        ["Berichtszeitraum:", f"01.01.{jahr} – 31.12.{jahr}"],
        ["Erstellt am:", datetime.now().strftime("%d.%m.%Y %H:%M")],
    ]
    praxis_table = Table(praxis_data, colWidths=[5*cm, 11*cm])
    praxis_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,-1), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(praxis_table)
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph(f"Prüfprotokoll {jahr}", styles["Heading2"]))
    story.append(Spacer(1, 0.3*cm))

    headers = ["Datum/Zeit", "Monitor", "Testbild", "Prüfer", "Ergebnis", "Kommentar"]
    table_data = [headers]

    # Zell-Style, der lange Texte (Monitornamen, Kommentare) umbricht statt abzuschneiden
    cell_style = ParagraphStyle("Cell", parent=normal, fontSize=8, leading=10)

    def _esc(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _cell(text: str) -> Paragraph:
        return Paragraph(_esc(text), cell_style)

    def _monitor_cell(monitor: str, bildschirm: str | None) -> Paragraph:
        zusatz = f'<br/><font size="6.5" color="#86868B">an {_esc(bildschirm)}</font>' if bildschirm else ""
        return Paragraph(_esc(monitor) + zusatz, cell_style)

    def _ergebnis_cell(ergebnis: str) -> Paragraph:
        # Farbe/Fett direkt im Paragraph — TableStyle-TEXTCOLOR greift bei Paragraphen nicht
        farbe = "#1a6b2e" if ergebnis == "BESTANDEN" else "#8b1a1a"
        return Paragraph(f'<font color="{farbe}"><b>{_esc(ergebnis)}</b></font>', cell_style)

    krit_style = ParagraphStyle("Krit", parent=normal, fontSize=7.5, leading=9.5, leftIndent=6)

    def _kriterien_cell(kriterien: list) -> Paragraph:
        # Einzelkriterien der Konstanzprüfung (BAG-Wegleitung Tabelle C), eine Zeile je Kriterium
        zeilen = []
        for k in kriterien:
            if k.get("erfuellt"):
                marke = '<font color="#1a6b2e"><b>erfüllt</b></font>'
            else:
                marke = '<font color="#8b1a1a"><b>NICHT erfüllt</b></font>'
            text = f" — {_esc(k['text'])}" if k.get("text") else ""
            zeilen.append(f"{_esc(k.get('testbild', ''))} · <b>{_esc(k['id'])} {_esc(k['kurz'])}</b>{text}: {marke}")
        return Paragraph("<br/>".join(zeilen), krit_style)

    bestanden_count = 0
    nicht_bestanden_count = 0
    kriterien_zeilen = []  # Tabellenzeilen-Indizes der Kriterien-Zeilen (über alle Spalten)

    for p in pruefungen:
        ergebnis = p["ergebnis"]
        if ergebnis == "BESTANDEN":
            bestanden_count += 1
        else:
            nicht_bestanden_count += 1
        table_data.append([
            _cell(p["zeitstempel"][:16].replace("T", " ")),
            _monitor_cell(p["monitor"], p.get("bildschirm")),
            _cell(p["testbild"]),
            _cell(p["pruefer"]),
            _ergebnis_cell(ergebnis),
            _cell(p.get("kommentar", "") or "")
        ])
        if p.get("kriterien"):
            kriterien_zeilen.append(len(table_data))
            table_data.append([_kriterien_cell(p["kriterien"]), "", "", "", "", ""])

    col_widths = [3.2*cm, 3.5*cm, 3*cm, 2.5*cm, 2.8*cm, 2*cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)

    row_styles = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("GRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")]),
    ]
    for r in kriterien_zeilen:
        row_styles += [
            ("SPAN", (0, r), (-1, r)),
            ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f3f6f9")),
        ]

    t.setStyle(TableStyle(row_styles))
    story.append(t)
    story.append(Spacer(1, 0.6*cm))

    gesamt = len(pruefungen)
    zusammenfassung = [
        ["Gesamtprüfungen:", str(gesamt)],
        ["Bestanden:", f"{bestanden_count}  ({bestanden_count/gesamt*100:.0f}%)" if gesamt else "0"],
        ["Nicht bestanden:", f"{nicht_bestanden_count}  ({nicht_bestanden_count/gesamt*100:.0f}%)" if gesamt else "0"],
    ]
    zus_table = Table(zusammenfassung, colWidths=[4*cm, 4*cm])
    zus_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(Paragraph("Zusammenfassung", styles["Heading3"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(zus_table)

    doc.build(story)
    return str(dateiname)

"""PDF de relés con estilo de cards (estilo modal de detalle)."""
from datetime import datetime
from io import BytesIO

from django.contrib.staticfiles.finders import find
from django.http import FileResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

from .models import PuertoComunicacion


# ── Paleta ─────────────────────────────────────────────────────────────────
NAVY      = colors.HexColor('#0D2B4D')
INK       = colors.HexColor('#1a1a2e')
WHITE     = colors.white
CARD_BR   = colors.HexColor('#e5e9f0')
ICON_BG   = colors.HexColor('#e8f4fd')
ICON_FG   = colors.HexColor('#4DA6FF')
BADGE_BR  = colors.HexColor('#d0d7de')
MUTED     = colors.HexColor('#8c8c8c')
TEXT      = colors.HexColor('#495057')
LIGHT_BG  = colors.HexColor('#f7f9fc')
RED       = colors.HexColor('#ED1C24')

ESTADO_COLORS = {
    'Activo':        (colors.HexColor('#10b981'), colors.HexColor('#d1fae5')),
    'Inactivo':      (colors.HexColor('#6c757d'), colors.HexColor('#e5e7eb')),
    'Mantenimiento': (colors.HexColor('#0ea5e9'), colors.HexColor('#dbeafe')),
}
ESTADO_DEFAULT = (colors.HexColor('#f59e0b'), colors.HexColor('#fef3c7'))


def _styles():
    s = getSampleStyleSheet()
    return {
        'brand':      ParagraphStyle('br',  parent=s['Normal'], fontSize=11, leading=13,
                                     textColor=NAVY, fontName='Helvetica-Bold'),
        'rele_h':     ParagraphStyle('rh',  parent=s['Normal'], fontSize=10, leading=12,
                                     textColor=NAVY, fontName='Helvetica-Bold'),
        'section':    ParagraphStyle('sec', parent=s['Normal'], fontSize=8.5, leading=10,
                                     textColor=NAVY, fontName='Helvetica-Bold'),
        'label':      ParagraphStyle('lbl', parent=s['Normal'], fontSize=6, leading=7,
                                     textColor=MUTED, fontName='Helvetica-Bold'),
        'value':      ParagraphStyle('val', parent=s['Normal'], fontSize=8, leading=9,
                                     textColor=INK, fontName='Helvetica'),
        'small':      ParagraphStyle('sm',  parent=s['Normal'], fontSize=6, leading=7,
                                     textColor=MUTED),
        'obs':        ParagraphStyle('obs', parent=s['Normal'], fontSize=7.5, leading=9,
                                     textColor=TEXT),
        'no_data':    ParagraphStyle('nd',  parent=s['Normal'], fontSize=7, leading=8,
                                     textColor=MUTED, fontName='Helvetica-Oblique'),
        'badge_txt':  ParagraphStyle('bdg', parent=s['Normal'], fontSize=7, leading=9,
                                     textColor=INK, fontName='Helvetica-Bold'),
        'foot':       ParagraphStyle('ft',  parent=s['Normal'], fontSize=7, leading=9,
                                     textColor=MUTED, alignment=TA_CENTER),
    }


def _document_header(page_w, st):
    base = getSampleStyleSheet()['Normal']

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=base, fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=base, fontSize=13))

    title_p = Paragraph('<b>Relés Registrados</b>',
                        ParagraphStyle('title', parent=base,
                                       fontSize=14, leading=17, alignment=TA_CENTER))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=base,
                                       fontSize=8, leading=10, alignment=TA_RIGHT,
                                       textColor=colors.HexColor('#555555')))

    # Anchos proporcionales (1.8 : 3.2 : 2.1, como en el PDF de remotas) que
    # ocupan exactamente el ancho de página disponible.
    ratios = [1.8, 3.2, 2.1]
    col_w = [page_w * r / sum(ratios) for r in ratios]
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=col_w)
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return hdr


def _icon_circle(letter, size=14):
    """Círculo azul-claro con letra como icono."""
    p = Paragraph(
        f'<font color="#4DA6FF" size="8"><b>{letter}</b></font>',
        ParagraphStyle('ic', parent=getSampleStyleSheet()['Normal'],
                       alignment=TA_CENTER, fontSize=8))
    tbl = Table([[p]], colWidths=[size], rowHeights=[size])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ICON_BG),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('BOX', (0,0), (-1,-1), 0.5, ICON_BG),
    ]))
    return tbl


def _section_header(title, icon_letter, st):
    """Header de card: icono circular + título."""
    tbl = Table([[_icon_circle(icon_letter, size=16),
                  Paragraph(title, st['section'])]],
                colWidths=[20, None])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (1,0), (1,0), 8),
    ]))
    return tbl


def _card(body_flowables, width, pad=12):
    """Envuelve flowables en una "card" blanca con borde y radio sutil.
    `pad` controla el padding vertical superior/inferior interno.
    """
    rows = [[fl] for fl in body_flowables]
    tbl = Table(rows, colWidths=[width])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), WHITE),
        ('BOX',           (0,0), (-1,-1), 0.7, CARD_BR),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 12),
        ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (0,0), pad),
        ('BOTTOMPADDING', (0,-1), (-1,-1), pad),
    ]))
    return tbl


def _info_rows(items, st):
    """Tabla con label en columna izquierda y valor en derecha (estilo modal)."""
    rows = []
    for label, value in items:
        if value is None or value == '':
            value = '—'
        rows.append([
            Paragraph(label.upper(), st['label']),
            value if hasattr(value, 'wrap') else Paragraph(str(value), st['value']),
        ])
    if not rows:
        return Paragraph('—', st['no_data'])

    tbl = Table(rows, colWidths=[1.05*inch, None])
    style = [
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]
    # Línea fina entre filas
    for i in range(len(rows) - 1):
        style.append(('LINEBELOW', (0, i), (-1, i), 0.4, CARD_BR))
    tbl.setStyle(TableStyle(style))
    return tbl


def _estado_pill(estado, st):
    fg, bg = ESTADO_COLORS.get(estado, ESTADO_DEFAULT)
    p = Paragraph(
        f'<b>{estado}</b>',
        ParagraphStyle('ep', parent=st['badge_txt'], fontSize=7.5,
                       textColor=fg, alignment=TA_CENTER,
                       fontName='Helvetica-Bold'))
    tbl = Table([[p]], colWidths=[0.7*inch], rowHeights=[15])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    return tbl


PUERTO_ICONS = {
    'ETH':   'E',
    'RS232': 'R',
    'RS485': '⇄',
    'USB':   'U',
    'FIBRA': 'F',
}


def _badges_row(items, width, st, per_row=3):
    """Badges blancos con texto sencillo.
    items: lista de (label) o (label, sub) o (icon, label) [icon se ignora].
    """
    if not items:
        return Paragraph('— Ninguno —', st['no_data'])

    cell_w = (width - 24) / per_row  # restando padding card

    badge_txt_st = ParagraphStyle(
        'bdg', parent=st['badge_txt'], fontSize=8, leading=10,
        textColor=INK, fontName='Helvetica-Bold')

    cells = []
    for it in items:
        if isinstance(it, (tuple, list)):
            if len(it) == 2 and it[1] and len(str(it[0])) <= 2:
                # formato (icon, label) - ignorar icon
                label = str(it[1])
                sub = None
            elif len(it) == 2:
                label, sub = it[0], it[1]
            else:
                label, sub = it[0], None
        else:
            label, sub = it, None
        if sub:
            text = (f'<font color="#1a1a2e">{label}</font>'
                    f'  <font color="#4DA6FF" size="7"><b>{sub}</b></font>')
        else:
            text = f'<font color="#1a1a2e">{label}</font>'
        cells.append(Paragraph(text, badge_txt_st))

    rows = []
    for i in range(0, len(cells), per_row):
        chunk = cells[i:i+per_row]
        while len(chunk) < per_row:
            chunk.append('')
        rows.append(chunk)

    tbl = Table(rows, colWidths=[cell_w]*per_row, rowHeights=[17]*len(rows))
    style = [
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (-1,-1), 'LEFT'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING',(0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]
    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row):
            if cell != '':
                style.append(('BACKGROUND', (c_idx, r_idx), (c_idx, r_idx), WHITE))
                style.append(('BOX', (c_idx, r_idx), (c_idx, r_idx), 0.6, BADGE_BR))

    # Espaciado entre badges
    final_rows = []
    for r in rows:
        row = []
        for j, cell in enumerate(r):
            row.append(cell)
            if j < per_row - 1:
                row.append('')
        final_rows.append(row)
    col_w = [cell_w if i % 2 == 0 else 4 for i in range(per_row*2 - 1)]
    tbl2 = Table(final_rows, colWidths=col_w, rowHeights=[17]*len(final_rows))
    style2 = [
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (-1,-1), 'LEFT'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING',(0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]
    for r_idx, r in enumerate(final_rows):
        for c_idx, cell in enumerate(r):
            if cell != '' and c_idx % 2 == 0:
                style2.append(('BACKGROUND', (c_idx, r_idx), (c_idx, r_idx), WHITE))
                style2.append(('BOX', (c_idx, r_idx), (c_idx, r_idx), 0.6, BADGE_BR))
    tbl2.setStyle(TableStyle(style2))
    return tbl2


def _plain_list(items, st):
    """Lista vertical en texto plano (sin badges), una por línea.
    items: lista de tuplas (texto_principal, sub_texto_opcional) o solo strings.
    """
    if not items:
        return Paragraph('— Ninguno —', st['no_data'])

    rows = []
    for it in items:
        if isinstance(it, (tuple, list)):
            main = it[0]
            sub = it[1] if len(it) > 1 else None
        else:
            main = it
            sub = None
        if sub:
            txt = (f'<font color="#1a1a2e">{main}</font>'
                   f'  <font color="#4DA6FF" size="7"><b>IP: {sub}</b></font>')
        else:
            txt = f'<font color="#1a1a2e">{main}</font>'
        rows.append([Paragraph(txt, st['value'])])

    tbl = Table(rows, colWidths=[None])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    return tbl


def _senales_row(items, width, st):
    """Fila de 4 métricas (señales) en una sola línea.
    items: lista de (label, value). El valor se muestra grande y el label debajo.
    """
    gap = 8
    n = len(items)
    cell_w = (width - gap * (n - 1)) / n if n else width

    value_st = ParagraphStyle('senal_val', parent=st['value'], fontSize=10,
                              leading=12, alignment=TA_CENTER, textColor=NAVY)
    label_st = ParagraphStyle('senal_lbl', parent=st['label'], fontSize=6.5,
                              leading=8, alignment=TA_CENTER)

    cells = []
    for label, value in items:
        inner = Table([
            [Paragraph(str(value), value_st)],
            [Paragraph(label.upper(), label_st)],
        ], colWidths=[cell_w])
        inner.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
            ('BOX', (0,0), (-1,-1), 0.5, CARD_BR),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (0,0), 5),
            ('BOTTOMPADDING', (0,0), (0,0), 1),
            ('TOPPADDING', (0,1), (0,1), 0),
            ('BOTTOMPADDING', (0,1), (0,1), 5),
        ]))
        cells.append(inner)

    # Intercalar separadores entre celdas
    row = []
    col_widths = []
    for i, c in enumerate(cells):
        if i > 0:
            row.append('')
            col_widths.append(gap)
        row.append(c)
        col_widths.append(cell_w)

    outer = Table([row], colWidths=col_widths)
    outer.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    return outer


def build_reles_pdf(reles):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=28, bottomMargin=28,
        title='Relés Registrados',
    )
    st = _styles()
    page_w = letter[0] - 60
    col_w = (page_w - 10) / 2  # 2 columnas con 10 de gap
    elements = []

    elements.append(_document_header(page_w, st))
    elements.append(Spacer(1, 6))
    # Línea roja como Table de 1pt de alto que ocupa exactamente page_w.
    red_line = Table([['']], colWidths=[page_w], rowHeights=[1.0])
    red_line.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), RED),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(red_line)
    elements.append(Spacer(1, 10))

    if not reles:
        elements.append(Paragraph('No hay relés registrados.', st['no_data']))

    for idx, rele in enumerate(reles, start=1):
        nivel = ''
        if rele.Id_Ten:
            tipo = rele.Id_Ten.get_Tipo_ten_display() if hasattr(rele.Id_Ten, 'get_Tipo_ten_display') else ''
            niv  = rele.Id_Ten.get_Nivel_display() if hasattr(rele.Id_Ten, 'get_Nivel_display') else str(rele.Id_Ten.Nivel)
            nivel = f"{tipo} - {niv}" if tipo else niv

        protos_badges = [p.get_Tipo_display() for p in rele.Protocolos.all()]
        puertos_ips_data = rele.Puertos_IPs or {}
        puertos_badges = []
        for p in rele.Puertos.all():
            label = p.get_Tipo_display()
            if p.Tipo == 'ETH':
                ip = puertos_ips_data.get(str(p.Id_Puerto)) or '0.0.0.0'
                puertos_badges.append((label, f'IP: {ip}'))
            else:
                puertos_badges.append(label)
        fecha  = rele.Fecha_Reg.strftime('%d/%m/%Y') if rele.Fecha_Reg else '—'
        creado = rele.creado_por.username if rele.creado_por else 'Sistema'
        estado = rele.Estado or '—'
        subest = rele.Id_Sub_est.Nombre if rele.Id_Sub_est else '—'

        # ── Cabecera de relé ──
        title_html = (f'<font size="11" color="#0D2B4D"><b>{subest}</b></font>'
                      f'  <font size="7.5" color="#8c8c8c">· Relé #{idx:02d}</font>')
        rele_hdr = Table([[Paragraph(title_html,
                                     ParagraphStyle('rh', parent=st['rele_h'],
                                                    fontSize=11, leading=13))]],
                         colWidths=[page_w])
        rele_hdr.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING',(0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LINEBELOW', (0,0), (-1,-1), 1.0, NAVY),
        ]))

        # ── Card: Información General ──
        info_items = [
            ('Subestación', subest),
            ('Nivel de Tensión', nivel),
            ('Marca', rele.Marca or '—'),
            ('Modelo', rele.Modelo or '—'),
            ('Estado', estado),
            ('Creado por', creado),
            ('Fecha de Registro', fecha),
        ]
        info_card = _card([
            _section_header('Información General', 'i', st),
            Spacer(1, 4),
            _info_rows(info_items, st),
        ], col_w)

        # ── Card: Observaciones (al lado derecho de Info General) ──
        obs_card = _card([
            _section_header('Observaciones', '✎', st),
            Spacer(1, 4),
            Paragraph(rele.Observaciones or 'Sin observaciones', st['obs']),
        ], col_w, pad=7)

        # ── Card: Protocolos ──
        proto_card = _card([
            _section_header('Protocolos', '⚙', st),
            Spacer(1, 4),
            _badges_row(protos_badges, col_w, st, per_row=2),
        ], col_w, pad=7)

        # ── Card: Interfaces de Comunicación ──
        iface_card = _card([
            _section_header('Interfaces de Comunicación', '⇄', st),
            Spacer(1, 4),
            _badges_row(puertos_badges, col_w, st, per_row=2),
        ], col_w, pad=7)

        # ── Columna derecha: Observaciones + Protocolos + Interfaces stacked ──
        right_col = Table([
            [obs_card],
            [Spacer(1, 5)],
            [proto_card],
            [Spacer(1, 5)],
            [iface_card],
        ], colWidths=[col_w])
        right_col.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING',(0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))

        # ── Fila: Info (izq) | Observaciones+Protocolos+Interfaces (der) ──
        main_row = Table([[info_card, '', right_col]],
                         colWidths=[col_w, 10, col_w])
        main_row.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING',(0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))

        # ── Card: Señales (ancho completo, 4 métricas en una línea) ──
        senales_items = [
            ('Entrada Digital',   rele.Entradas_Digitales or 0),
            ('Salida Digital',    rele.Salidas_Digitales or 0),
            ('Entrada Analógica', rele.Entradas_Analogicas or 0),
            ('Contadores',        rele.Contadores or 0),
        ]
        senales_card = _card([
            _section_header('Señales', '∿', st),
            Spacer(1, 4),
            _senales_row(senales_items, page_w - 24, st),
        ], page_w, pad=7)

        # ── Card: Remota (ancho completo) ──
        rem = rele.Remota
        if rele.EsRemoto and rem:
            # Nivel(es) de tensión: campo M2M Niveles_Ten (lo que edita el formulario)
            niveles_rem = []
            for nivel in rem.Niveles_Ten.all():
                tipo_r = nivel.get_Tipo_ten_display() if hasattr(nivel, 'get_Tipo_ten_display') else ''
                nv_r   = nivel.get_Nivel_display() if hasattr(nivel, 'get_Nivel_display') else str(nivel.Nivel)
                niveles_rem.append(f"{tipo_r} - {nv_r}" if tipo_r else nv_r)
            niv_rem = ', '.join(niveles_rem) if niveles_rem else '—'
            rem_protos_plain = [p.get_Tipo_display() for p in rem.Protocolos.all()]
            remota_ips_data = rele.Remota_IPs or {}

            # Interfaces: usar la selección a nivel de puerto guardada en
            # Remota_Puertos; para relés antiguos, derivar de las interfaces.
            pares = []
            if rele.Remota_Puertos:
                for clave in rele.Remota_Puertos:
                    if '_' in clave:
                        iface_id, puerto_id = clave.split('_', 1)
                        pares.append((iface_id, puerto_id))
            else:
                for iface in rem.Interfaces.all():
                    for pt in iface.puertos.all():
                        pares.append((str(iface.Id_Interfaz), str(pt.Id_Puerto)))

            puerto_ids = [pid for _, pid in pares]
            puertos_map = {
                str(p.Id_Puerto): p
                for p in PuertoComunicacion.objects.filter(Id_Puerto__in=puerto_ids)
            }

            rem_ifaces_plain = []
            seen_non_eth = set()
            seen_eth_keys = set()
            for iface_id, puerto_id in pares:
                pt = puertos_map.get(str(puerto_id))
                if not pt:
                    continue
                label = pt.get_Tipo_display()
                if pt.Tipo == 'ETH':
                    key = (iface_id, puerto_id)
                    if key in seen_eth_keys:
                        continue
                    seen_eth_keys.add(key)
                    ip_key = f'{iface_id}_{puerto_id}'
                    ip = remota_ips_data.get(ip_key) or '0.0.0.0'
                    rem_ifaces_plain.append((label, ip))
                else:
                    if pt.Tipo in seen_non_eth:
                        continue
                    seen_non_eth.add(pt.Tipo)
                    rem_ifaces_plain.append((label, None))

            # 2 columnas:
            # Izquierda: Marca, Nivel de Tensión, Interfaces
            # Derecha:   Modelo, Protocolos
            inner_w = page_w - 24
            col_inner = (inner_w - 12) / 2

            left_info = _info_rows([
                ('Marca', rem.Marca or '—'),
                ('Nivel de Tensión', niv_rem),
                ('Interfaces', _plain_list(rem_ifaces_plain, st)),
            ], st)
            right_info = _info_rows([
                ('Modelo', rem.Modelo or '—'),
                ('Protocolos', _plain_list(rem_protos_plain, st)),
            ], st)
            info_2col = Table([[left_info, '', right_info]],
                              colWidths=[col_inner, 12, col_inner])
            info_2col.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING',(0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))

            remota_card = _card([
                _section_header('Remota Asociada', 'R', st),
                Spacer(1, 4),
                info_2col,
            ], page_w, pad=7)
        else:
            remota_card = _card([
                _section_header('Remota', 'R', st),
                Spacer(1, 4),
                Paragraph('No tiene remota asociada', st['no_data']),
            ], page_w, pad=7)

        footer_p = Paragraph(
            f'<font color="#8c8c8c" size="6.5">Registrado el {fecha} · por {creado}</font>',
            ParagraphStyle('rf', parent=st['small'], alignment=TA_CENTER))

        card_block = [
            rele_hdr,
            Spacer(1, 5),
            main_row,
            Spacer(1, 5),
            senales_card,
            Spacer(1, 5),
            remota_card,
            Spacer(1, 3),
            footer_p,
        ]
        elements.append(KeepTogether(card_block))

        # Separador entre relés (no después del último)
        if idx < len(reles):
            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width=page_w, thickness=1.2,
                                       color=CARD_BR, spaceBefore=0, spaceAfter=0,
                                       lineCap='round'))
            elements.append(Spacer(1, 12))

    foot_line = Table([['']], colWidths=[page_w], rowHeights=[0.5])
    foot_line.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CARD_BR),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(Spacer(1, 4))
    elements.append(foot_line)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. · Documento de carácter oficial · Confidencial',
        st['foot']))

    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reles.pdf"'
    return response

"""UI helpers: genera el calendario mensual HTML coloreado por ocupación.

El calendario se representa como un grid HTML. Cada día es un enlace
`href="?y=A&m=B&dia=YYYY-MM-DD"`. Al pulsarlo, Streamlit lee la query string
con st.query_params y muestra la agenda de ese día.
"""

from __future__ import annotations

import datetime as dt

import core

WEEK_HEADERS = core.WEEKDAY_SHORT


def build_calendar_html(anyo: int, mes: int, link_base: str,
                        dia_seleccionado: str | None,
                        ocupacion: dict[int, dict],
                        compact: bool = False) -> str:
    """Genera el HTML del calendario mensual.

    link_base: query string base para el mes, p. ej. "?y=2026&m=1".
    Dia: cada celda enlaza a link_base + "&dia=YYYY-MM-DD".
    compact: estilos reducidos para caber junto a la agenda en una columna.
    """
    if compact:
        th_style = ("padding:2px 2px; text-align:center; font-size:0.72rem; "
                    "color:#6b7280; border-bottom:2px solid #e5e7eb;")
        a_style = ("display:block; padding:4px 2px; border-radius:4px; "
                   "text-decoration:none; font-weight:600; font-size:0.8rem; "
                   "color:#fff;")
    else:
        th_style = ("padding:6px 4px; text-align:center; font-size:0.85rem; "
                    "color:#6b7280; border-bottom:2px solid #e5e7eb;")
        a_style = ("display:block; padding:10px 4px; border-radius:6px; "
                   "text-decoration:none; font-weight:600; font-size:0.95rem; "
                   "color:#fff;")

    header = "".join(f"<th>{w}</th>" for w in WEEK_HEADERS)
    pasado_style = a_style + " cursor:not-allowed;"
    hoy = dt.date.today()
    rows = []
    for week in core.iter_weeks(anyo, mes):
        cells = []
        for dia in week:
            if dia is None:
                cells.append("<td class='cal-vacio'></td>")
                continue
            fecha = dt.date(anyo, mes, dia)
            if fecha < hoy:
                cells.append(
                    f"<td><span class='cal-pasado' title='{core.PAST_LABEL}' "
                    f"style='background:{core.PAST_COLOR}'>{dia}</span></td>"
                )
                continue
            info = ocupacion.get(dia, {})
            color = info.get("color", core.COLORS[core.OCC_NONE])
            tooltip = info.get("label", "")
            sel = " cal-seleccionado" if fecha.isoformat() == dia_seleccionado else ""
            cells.append(
                f"<td><a class='cal-dia'{sel} title='{tooltip}' "
                f"href='{link_base}&dia={fecha.isoformat()}' "
                f"style='background:{color}'>{dia}</a></td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    html = f"""
    <style>
      .cal-{anyo} {{ width:100%; border-collapse:collapse; }}
      .cal-{anyo} th {{ {th_style} }}
      .cal-{anyo} td {{ text-align:center; padding:{'1px' if compact else '2px'}; }}
      .cal-{anyo} a {{ {a_style} }}
      .cal-{anyo} span.cal-pasado {{ {pasado_style} }}
      .cal-{anyo} a:hover {{ outline:2px solid #111827; outline-offset:-2px; }}
      .cal-{anyo} a.cal-seleccionado {{ outline:3px solid #111827; outline-offset:-3px; }}
      .cal-{anyo} td.cal-vacio {{ background:transparent; }}
    </style>
    <table class='cal-{anyo}'>
      <thead><tr>{header}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """
    return html
# -*- coding: utf-8 -*-
"""Genera docs/discovery/informe-discovery.pdf desde informe-discovery.md.

Uso:  python docs/discovery/generar-pdf.py
Requiere: pip install fpdf2
Estrategia de legibilidad (pedida por la consigna "grilla/tablas legibles"):
- Tabla A (18 sistemas x 11 columnas): una ficha por sistema (bloque
  atributo/valor) porque 11 columnas no entran ni en apaisado.
- Matriz B (9 columnas cortas): grilla real en pagina apaisada A4.
- Tabla de Verificacion (6 fuentes): un bloque por fuente.
- Resto: titulares, parrafos, listas y citas.
Sin secretos, sin datos reales: el contenido sale integro del .md.
"""
import re
import sys
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

BASE = Path(__file__).resolve().parent
MD = BASE / "informe-discovery.md"
PDF = BASE / "informe-discovery.pdf"

REPLACEMENTS = {
    "\u2014": "--",
    "\u2013": "-",
    "\u2192": "->",
    "\u00d7": "x",
    "\u2713": "OK",
    "\u201c": '"', "\u201d": '"',
    "\u2018": "'", "\u2019": "'",
    "\u2026": "...",
    "\u00a0": " ",
}


def san(t: str) -> str:
    for k, v in REPLACEMENTS.items():
        t = t.replace(k, v)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    t = t.replace("**", "")
    out = []
    for ch in t:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            out.append("?")
    return "".join(out)


class InformePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, san("Informe de Discovery - turnos-odontologia_cattaneo"),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 8, f"pag. {self.page_no()}/{{nb}}", align="R")


def parse_table(lines):
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells and all(set(c) <= set("-: ") and c for c in cells):
            continue
        rows.append(cells)
    return rows


pdf = InformePDF()
pdf.alias_nb_pages("{nb}")
pdf.set_auto_page_break(True, margin=18)
pdf.set_margins(15, 15, 15)


def block(t, size=10.5, style="", color=(20, 20, 20), h=6, gap=1):
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, h, san(t), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if gap:
        pdf.ln(gap)


def heading(level, t):
    t = san(t.strip())
    if level == 1 and t.startswith("Informe de Discovery"):
        return
    sizes = {1: 16, 2: 13.5, 3: 11.5, 4: 10.5}
    pdf.ln(3)
    col = (20, 40, 90) if level <= 2 else (30, 30, 30)
    block(t, size=sizes.get(level, 11), style="B", color=col, h=7)


def grid(headers, rows, fontsize=9):
    with pdf.table(
        col_widths=None,
        text_align="LEFT",
        line_height=fontsize * 0.55,
        first_row_as_headings=True,
    ) as table:
        hdr = table.row()
        for h in headers:
            hdr.cell(san(h))
        for r in rows:
            row = table.row()
            for j in range(len(headers)):
                c = r[j] if j < len(r) else ""
                row.cell(san(c))


def fichas(headers, rows):
    for r in rows:
        block(f"{r[0] if r else ''} - {r[1] if len(r) > 1 else ''}",
              size=11, style="B", color=(20, 40, 90), h=7)
        for j in range(2, len(headers)):
            c = r[j] if j < len(r) else ""
            if not c:
                continue
            block(headers[j] + ":", size=10, style="B", gap=0)
            block(c, size=10, gap=1)
        pdf.ln(1)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)


def main():
    pdf.add_page()
    # ---- Portada ----
    block("Informe de Discovery", size=20, style="B", h=10, gap=0)
    block("Sistema de gestion de turnos y agenda para consultorios "
          "odontologicos (mercado argentino)", size=13, gap=2)
    pdf.ln(2)
    for item in [
        "Materia: Metodologia I - Trabajo de Integracion (SDD + Active Stack)",
        "Integrantes: A completar por el equipo (no consta en el repositorio)",
        "Fuentes originales: 2026-10-10 / 2026-10-11 - Verificacion: 2026-10-12",
        "Stack: FastAPI + React + Postgres - Fuente historica: discovery/",
    ]:
        block(item, size=11, gap=0)
    pdf.ln(2)
    pdf.set_draw_color(60, 60, 60)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    lines = MD.read_text(encoding="utf-8").split("\n")
    i, n = 0, len(lines)
    in_table = []
    pending_item = None
    pending_indent = 0
    para_buf = []

    def flush_pending():
        nonlocal pending_item
        if pending_item:
            block("- " + pending_item, size=10.5, gap=0.5)
            pending_item = None

    def flush_para():
        nonlocal para_buf
        if para_buf:
            block(" ".join(para_buf), size=10.5)
            para_buf = []

    while i < n:
        ln = lines[i]
        s = ln.strip()

        if s.startswith("|"):
            flush_para()
            flush_pending()
            in_table.append(ln)
            i += 1
            continue
        if in_table:
            rows = parse_table(in_table)
            in_table = []
            if rows:
                headers, data = rows[0], rows[1:]
                h0 = headers[0].lower()
                flat = " ".join(headers).lower()
                if len(headers) >= 10:
                    heading(3, "Detalle por sistema (Tabla A: 18 sistemas)")
                    fichas(headers, data)
                elif "tur/aut" in flat or "seg/exp" in flat:
                    pdf.add_page(orientation="L")
                    heading(2, "Matriz de puntuacion (apaisada para legibilidad)")
                    grid(headers, data, fontsize=9)
                    pdf.add_page(orientation="P")
                elif "fuente" in flat:
                    heading(3, "Fuentes comprobadas (una por tipo)")
                    fichas(headers, data)
                elif len(headers) == 2:
                    for r in data:  # tabla de definiciones (portada)
                        if len(r) >= 2 and r[1]:
                            block(r[0] + ":", size=10, style="B", gap=0)
                            block(r[1], size=10, gap=1)
                else:
                    grid(headers, data, fontsize=9)
            continue

        if not s:
            flush_para()
            flush_pending()
            i += 1
            continue
        if set(s) == {"-"} and len(s) >= 3:
            flush_para()
            flush_pending()
            pdf.ln(2)
            pdf.set_draw_color(60, 60, 60)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flush_para()
            flush_pending()
            heading(len(m.group(1)), m.group(2))
            i += 1
            continue
        if s.startswith(">"):
            flush_para()
            flush_pending()
            inner = s.lstrip(">").strip()
            if inner.startswith("|") or inner == "**Portada**":
                i += 1  # tabla de portada: ya cubierta por la portada del PDF
                continue
            block(inner, size=10, style="I", color=(60, 60, 60))
            i += 1
            continue
        m2 = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)$", ln.rstrip())
        if m2:
            flush_para()
            flush_pending()
            pending_item = m2.group(3)
            pending_indent = len(m2.group(1)) // 2
            i += 1
            continue
        if pending_item is not None and (ln.startswith(" ") or ln.startswith("\t")):
            pending_item += " " + s
        elif pending_item is not None:
            flush_pending()
            para_buf.append(s)
        else:
            para_buf.append(s)
        i += 1

    flush_para()
    flush_pending()
    pdf.output(str(PDF))
    print(f"OK: {PDF} ({PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())

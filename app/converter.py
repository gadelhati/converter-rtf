"""
Conversor RTF -> HTML no padrão de Portarias/NORMAM da DHN.

Baseado no antigo FileChooser.java (marcadores ##ATO, ##EME, ##TEX, ##ASS,
##DOU, ##ANE, ##TCH, ##LNK), agora gerando o HTML do novo modelo
(Padrão_Normam.html / Padrão_Normam_Revogado.html).

Marcadores aceitos no início da linha do RTF:
  ##ATO  -> identificação do documento (título)       <h1 class="identificacao-documento">
  ##EME  -> ementa                                    <div class="ementa"><p>
  ##TEX  -> início do texto (linha comum do texto)    <div class="texto-documento">
  ##ASS  -> assinatura (até 3 linhas: nome, posto, função)
  ##DOU  -> rodapé "Este texto não substitui..."      <p class="rodape">
  ##ANE  -> anexo (título)                            <h3>
  ##TCH  -> tachado / riscado na linha                class="riscado"
  ##REV  -> documento inteiro revogado (em qualquer linha)
  ##LNK  -> link: exibe o conteúdo entre [] e aponta para o conteúdo entre ()
  (INSERIR AQUI A IMAGEM arquivo.png) -> <img>

Sem marcadores, a classificação é automática:
  "Art. ..."                         -> <p class="artigo">
  "I - ", "a) ", "§ 1º"              -> <p class="item">
  "Este texto não substitui ..."     -> rodapé
  "ANEXO ..."                        -> anexo
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

MARKERS = ("ATO", "EME", "TEX", "ASS", "DOU", "ANE", "TCH", "LNK", "REV")
_MARKER_RE = re.compile(r"##(" + "|".join(MARKERS) + ")")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_IMG_RE = re.compile(r"^\(INSERIR AQUI A IMAGEM\s+(.+?)\)\s*$", re.IGNORECASE)
_ART_RE = re.compile(r"^Art\.\s*\d+", re.IGNORECASE)
_ITEM_RE = re.compile(r"^([IVXLCDM]+\s*[-–—]|[a-z]\)|§\s*\d+|Parágrafo único)", re.IGNORECASE)
_RODAPE_RE = re.compile(r"^Este texto não substitui", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Leitor de RTF próprio: preserva negrito, itálico, sobrescrito, subscrito e
# tachado (o striprtf descartava essa formatação, ex.: m³ virava m3).
# ---------------------------------------------------------------------------

_SKIP_DEST = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header",
    "headerl", "headerr", "headerf", "footer", "footerl", "footerr", "footerf",
    "listtable", "listoverridetable", "rsidtbl", "generator", "xmlnstbl",
    "themedata", "colorschememapping", "datastore", "latentstyles", "mmathpr",
    "fldinst", "filetbl", "revtbl", "pgdsctbl", "bkmkstart", "bkmkend",
    "footnote", "annotation", "atnid", "atnauthor", "nonshppict", "shpinst",
}
_SYMBOLS = {
    "emdash": "\u2014", "endash": "\u2013", "bullet": "\u2022", "lquote": "\u2018",
    "rquote": "\u2019", "ldblquote": "\u201c", "rdblquote": "\u201d", "tab": " ",
    "emspace": " ", "enspace": " ", "qmspace": " ",
}
_TOKEN_RE = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|(\r\n|\r|\n)|([^\\{}\r\n]+)",
    re.S,
)
# formato = (negrito, itálico, sobrescrito, subscrito, tachado)
Fmt = tuple


def _parse_rtf(raw: str, enc: str) -> list[list[tuple[str, Fmt]]]:
    """Devolve lista de parágrafos; cada parágrafo é lista de (caractere, formato)."""
    lines: list[list[tuple[str, Fmt]]] = [[]]
    st = {"b": False, "i": False, "sup": False, "sub": False, "s": False, "skip": False, "uc": 1}
    stack: list[dict] = []
    skip_chars = 0
    pending_bytes = bytearray()
    first_in_group = False
    star = False

    def fmt() -> Fmt:
        return (st["b"], st["i"], st["sup"], st["sub"], st["s"])

    def emit(text: str) -> None:
        nonlocal skip_chars
        if st["skip"]:
            return
        for ch in text:
            if skip_chars > 0:
                skip_chars -= 1
                continue
            lines[-1].append((ch, fmt()))

    def flush_bytes() -> None:
        if pending_bytes:
            emit(bytes(pending_bytes).decode(enc, errors="replace"))
            pending_bytes.clear()

    for m in _TOKEN_RE.finditer(raw):
        word, num, hexv, sym, brace, nl, text = m.groups()
        if hexv is not None:
            if skip_chars > 0:
                skip_chars -= 1
            else:
                pending_bytes.append(int(hexv, 16))
            first_in_group = False
            continue
        flush_bytes()
        if brace == "{":
            stack.append(dict(st))
            first_in_group, star = True, False
            continue
        if brace == "}":
            if stack:
                st.clear()
                st.update(stack.pop())
            first_in_group = star = False
            continue
        if nl is not None:
            continue
        if text is not None:
            emit(text)
            first_in_group = False
            continue
        if sym is not None:
            if sym == "*":
                star = True
                continue
            if sym in "\\{}":
                emit(sym)
            elif sym == "~":
                emit("\u00a0")
            elif sym in "\n\r":
                lines.append([])
            first_in_group = False
            continue
        # palavra de controle
        w = word.lower()
        n = int(num) if num is not None else None
        if (first_in_group or star) and (w in _SKIP_DEST or star):
            if w != "fldrslt":
                st["skip"] = True
            first_in_group = star = False
            continue
        first_in_group = False
        on = n != 0
        if w == "b":
            st["b"] = on
        elif w == "i":
            st["i"] = on
        elif w == "super":
            st["sup"], st["sub"] = on, False
        elif w == "sub":
            st["sub"], st["sup"] = on, False
        elif w == "nosupersub":
            st["sup"] = st["sub"] = False
        elif w == "up" :
            st["sup"] = (n or 0) > 0
        elif w == "dn":
            st["sub"] = (n or 0) > 0
        elif w in ("strike", "striked"):
            st["s"] = on
        elif w == "plain":
            st.update(b=False, i=False, sup=False, sub=False, s=False)
        elif w == "uc":
            st["uc"] = n or 0
        elif w == "u" and n is not None:
            emit(chr(n + 65536 if n < 0 else n))
            skip_chars = st["uc"]
        elif w in ("par", "line", "sect", "page", "row"):
            if not st["skip"]:
                lines.append([])
        elif w == "cell":
            emit(" ")
        elif w in _SYMBOLS:
            emit(_SYMBOLS[w])
    flush_bytes()
    return lines


def rtf_bytes_to_lines(data: bytes) -> list[list[tuple[str, Fmt]]]:
    raw = data.decode("latin-1", errors="ignore")
    cp = re.search(r"\\ansicpg(\d+)", raw)
    enc = f"cp{cp.group(1)}" if cp else "cp1252"
    try:
        "".encode(enc)
    except LookupError:
        enc = "cp1252"
    return _parse_rtf(raw, enc)


def rtf_bytes_to_text(data: bytes) -> str:
    return "\n".join("".join(c for c, _ in l) for l in rtf_bytes_to_lines(data))


_TAGS = (("strong", 0), ("em", 1), ("sup", 2), ("sub", 3), ("s", 4))


def _chars_html(chars: list[tuple[str, Fmt]]) -> str:
    """Converte (caractere, formato) em HTML com <strong>, <em>, <sup>, <sub>, <s>."""
    out, i = [], 0
    while i < len(chars):
        f = chars[i][1]
        j = i
        while j < len(chars) and chars[j][1] == f:
            j += 1
        txt = html.escape("".join(c for c, _ in chars[i:j]), quote=False)
        if txt.strip():
            for tag, k in _TAGS:
                if f[k]:
                    txt = f"<{tag}>{txt}</{tag}>"
        out.append(txt)
        i = j
    return "".join(out)


_LNK_TEXT_RE = re.compile(r"\[([^\]]*)\]")
_LNK_URL_RE = re.compile(r"\(([^)]*)\)")


def _line_html(chars: list[tuple[str, Fmt]], plain: str, links: bool) -> str:
    if links:
        t, u = _LNK_TEXT_RE.search(plain), _LNK_URL_RE.search(plain)
        if t and u:
            href = u.group(1).strip()
            label = t.group(1).strip() or href
            a = f'<a href="{html.escape(href)}" target="_blank">{_chars_html(chars[t.start(1):t.end(1)]) or html.escape(label)}</a>'
            spans = sorted([(t.start(), t.end(), a), (u.start(), u.end(), "")])
            out, pos = [], 0
            for s, e, rep in spans:
                out.append(_chars_html(chars[pos:s]))
                out.append(rep)
                pos = e
            out.append(_chars_html(chars[pos:]))
            return "".join(out).strip()
    return _chars_html(chars)


def _prepare(line: list[tuple[str, Fmt]]):
    """Remove marcadores e espaços das pontas; devolve (tags, chars, plain)."""
    plain = "".join(c for c, _ in line)
    tags = set(_MARKER_RE.findall(plain))
    keep = [True] * len(line)
    for m in _MARKER_RE.finditer(plain):
        for k in range(m.start(), m.end()):
            keep[k] = False
    chars = [c for c, k in zip(line, keep) if k]
    chars = [(" " if c == "\u00a0" else c, f) for c, f in chars]
    while chars and chars[0][0].isspace():
        chars.pop(0)
    while chars and chars[-1][0].isspace():
        chars.pop()
    return tags, chars, "".join(c for c, _ in chars)


@dataclass
class Documento:
    titulo: str = ""
    titulo_html: str = ""
    ementa_txt: list[str] = field(default_factory=list)
    ementa: list[str] = field(default_factory=list)
    texto: list[str] = field(default_factory=list)  # já em HTML
    assinatura: list[str] = field(default_factory=list)
    rodape: str = ""
    anexos: list[str] = field(default_factory=list)  # já em HTML
    revogado: bool = False
    titulo_riscado: bool = False
    ementa_riscada: bool = False


def parse(lines, revogado: bool = False) -> Documento:
    """lines: texto puro (str) ou parágrafos vindos de rtf_bytes_to_lines."""
    if isinstance(lines, str):
        lines = [[(c, (False,) * 5) for c in l] for l in lines.split("\n")]
    doc = Documento(revogado=revogado)
    secao = "inicio"
    pendentes: set[str] = set()
    for raw in lines:
        tags, chars, line = _prepare(raw)
        tags |= pendentes
        pendentes = set()
        if "REV" in tags:
            doc.revogado = True
            tags.discard("REV")
        if not line:
            # marcador sozinho na linha vale para a linha seguinte
            pendentes = tags
            continue

        riscado = "TCH" in tags or all(f[4] for _, f in chars)
        conteudo = _line_html(chars, line, "LNK" in tags or bool(_LINK_RE.search(line)))
        cls_r = " riscado" if riscado else ""

        if "ATO" in tags or (secao == "inicio" and not doc.titulo and line.upper().startswith("PORTARIA")):
            doc.titulo, doc.titulo_html = line, conteudo
            doc.titulo_riscado = riscado
            secao = "ementa"
            continue
        if "EME" in tags or (secao == "ementa" and not doc.ementa and not tags and not _ART_RE.match(line) and line != line.upper()):
            doc.ementa.append(conteudo)
            doc.ementa_txt.append(line)
            doc.ementa_riscada = doc.ementa_riscada or riscado
            secao = "texto"
            continue
        if "ASS" in tags:
            doc.assinatura.append(conteudo)
            secao = "assinatura"
            continue
        if "DOU" in tags or _RODAPE_RE.match(line):
            doc.rodape = conteudo
            secao = "pos"
            continue
        if "ANE" in tags or (secao in ("pos", "anexo") and line.upper().startswith("ANEXO")):
            doc.anexos.append(f"<h3>{conteudo}</h3>")
            secao = "anexo"
            continue
        if "TEX" in tags:
            secao = "texto"

        if secao == "assinatura":
            if len(doc.assinatura) < 3 and "LNK" not in tags:
                doc.assinatura.append(conteudo)
                continue
            secao = "pos"

        img = _IMG_RE.match(line)
        if img:
            el = f'<img src="{html.escape(img.group(1).strip())}" alt="">'
        elif "LNK" in tags:
            el = f'<p class="{cls_r.strip()}">{conteudo}</p>' if riscado else f"<p>{conteudo}</p>"
        elif _ART_RE.match(line):
            el = f'<p class="artigo{cls_r}">{conteudo}</p>'
        elif _ITEM_RE.match(line):
            el = f'<p class="item{cls_r}">{conteudo}</p>'
        else:
            el = f'<p class="{cls_r.strip()}">{conteudo}</p>' if riscado else f"<p>{conteudo}</p>"

        if secao in ("anexo", "pos"):
            doc.anexos.append(f"<h3>{conteudo}</h3>" if "LNK" in tags and secao == "anexo" else el)
        else:
            doc.texto.append(el)
            if secao in ("inicio", "ementa"):
                secao = "texto"
    return doc


def _p(text: str) -> str:
    return html.escape(text, quote=False)


def render(doc: Documento, om: str = "DIRETORIA DE HIDROGRAFIA E NAVEGAÇÃO") -> str:
    rev = " riscado" if doc.revogado else ""
    titulo = doc.titulo or "DOCUMENTO"
    ementa_txt = " ".join(doc.ementa_txt)
    ementa_html = " ".join(doc.ementa)
    ass_cls = ["nome", "posto", "função"]
    assinatura = "\n".join(
        f'                <h3 class="{ass_cls[min(i, 2)]}">{v}</h3>' for i, v in enumerate(doc.assinatura)
    )
    corpo = "\n".join(f"            {e}" for e in doc.texto)
    anexos = "\n".join(f"            {e}" for e in doc.anexos)
    titulo_cls = "identificacao-documento" + (" riscado" if doc.revogado or doc.titulo_riscado else "")
    ementa_cls = ' class="riscado"' if doc.revogado or doc.ementa_riscada else ""

    partes = [
        "<!DOCTYPE html>",
        '<html lang="pt-br">',
        "<head>",
        '    <meta http-equiv="content-type" content="text/html; charset=UTF-8">',
        '    <meta charset="UTF-8">',
        '    <meta http-equiv="Content-Language" content="pt-br">',
        '    <meta http-equiv="X-UA-Compatible" content="IE=edge">',
        '    <meta http-equiv="Cache-Control" content="no-cache, no-store">',
        '    <meta http-equiv="expires" content="Sat, 01 jan 2000 00:00:00 GMT">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '    <link rel="stylesheet" href="portaria-css.css">',
        '    <link rel="stylesheet" href="portarias_html.css">',
        f'    <meta name="author" content="{html.escape(om.title())}">',
        f'    <meta name="description" content="{html.escape(ementa_txt)}">',
        f"    <title>{_p(titulo)}</title>",
        "</head>",
        "",
        "<body>",
        '    <div class="conteudo-documento">',
        '        <img class="brasao-gov" src="brasao.png" alt="Brasão da República">',
        '        <div class="cabecalho">',
        "            <h1>MARINHA DO BRASIL</h1>",
        f'            <h1 class="nome-da-om">{_p(om)}</h1>',
        "        </div>",
        f'        <h1 class="{titulo_cls}">{doc.titulo_html or _p(titulo)}</h1>',
        '        <div class="ementa">',
        f"            <p{ementa_cls}>{ementa_html}</p>",
        "        </div>",
        f'        <div class="texto-documento{rev}">',
        corpo,
    ]
    if doc.assinatura:
        partes += ['            <div class="assinatura">', assinatura, "            </div>"]
    if doc.rodape:
        partes.append(f'            <p class="rodape">{doc.rodape}</p>')
    if anexos:
        partes.append(anexos)
    partes += ["        </div>", "    </div>", "</body>", "</html>", ""]
    return "\n".join(p for p in partes if p != "")


def convert_rtf(data: bytes, revogado: bool = False, om: str | None = None) -> str:
    doc = parse(rtf_bytes_to_lines(data), revogado=revogado)
    return render(doc, om=om) if om else render(doc)

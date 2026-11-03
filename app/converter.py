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
  ##LNK  -> converte [texto](url) em links
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

from striprtf.striprtf import rtf_to_text

MARKERS = ("ATO", "EME", "TEX", "ASS", "DOU", "ANE", "TCH", "LNK", "REV")
_MARKER_RE = re.compile(r"##(" + "|".join(MARKERS) + ")")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_IMG_RE = re.compile(r"^\(INSERIR AQUI A IMAGEM\s+(.+?)\)\s*$", re.IGNORECASE)
_ART_RE = re.compile(r"^Art\.\s*\d+", re.IGNORECASE)
_ITEM_RE = re.compile(r"^([IVXLCDM]+\s*[-–—]|[a-z]\)|§\s*\d+|Parágrafo único)", re.IGNORECASE)
_RODAPE_RE = re.compile(r"^Este texto não substitui", re.IGNORECASE)


def rtf_bytes_to_text(data: bytes) -> str:
    """Extrai o texto puro do RTF (substitui o Apache Tika do projeto Java)."""
    raw = data.decode("latin-1", errors="ignore")
    text = rtf_to_text(raw, errors="ignore")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _inline(text: str, links: bool) -> str:
    """Escapa HTML e, se pedido, converte [texto](url) em <a>."""
    if not links:
        return html.escape(text, quote=False)
    out, pos = [], 0
    for m in _LINK_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        out.append(
            f'<a href="{html.escape(m.group(2))}" target="_blank">'
            f"{html.escape(m.group(1), quote=False)}</a>"
        )
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


@dataclass
class Documento:
    titulo: str = ""
    ementa: list[str] = field(default_factory=list)
    texto: list[str] = field(default_factory=list)  # já em HTML
    assinatura: list[str] = field(default_factory=list)
    rodape: str = ""
    anexos: list[str] = field(default_factory=list)  # já em HTML
    revogado: bool = False
    titulo_riscado: bool = False
    ementa_riscada: bool = False


def parse(text: str, revogado: bool = False) -> Documento:
    doc = Documento(revogado=revogado)
    secao = "inicio"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue

        tags = set(_MARKER_RE.findall(line))
        line = _MARKER_RE.sub("", line).strip()
        if "REV" in tags:
            doc.revogado = True
        if not line:
            continue

        riscado = "TCH" in tags
        conteudo = _inline(line, "LNK" in tags or bool(_LINK_RE.search(line)))
        cls_r = " riscado" if riscado else ""

        if "ATO" in tags or (secao == "inicio" and not doc.titulo and line.upper().startswith("PORTARIA")):
            doc.titulo = line
            doc.titulo_riscado = riscado
            secao = "ementa"
            continue
        if "EME" in tags or (secao == "ementa" and not doc.ementa and not _ART_RE.match(line) and line != line.upper()):
            doc.ementa.append(line)
            doc.ementa_riscada = doc.ementa_riscada or riscado
            secao = "texto"
            continue
        if "ASS" in tags:
            secao = "assinatura"
        elif "DOU" in tags or _RODAPE_RE.match(line):
            doc.rodape = line
            secao = "pos"
            continue
        elif "ANE" in tags or (secao in ("pos", "anexo") and line.upper().startswith("ANEXO")):
            doc.anexos.append(f"<h3>{conteudo}</h3>")
            secao = "anexo"
            continue
        elif "TEX" in tags:
            secao = "texto"

        if secao == "assinatura":
            if len(doc.assinatura) < 3:
                doc.assinatura.append(line)
                continue
            secao = "texto"

        img = _IMG_RE.match(line)
        if img:
            el = f'<img src="{html.escape(img.group(1).strip())}" alt="">'
        elif _ART_RE.match(line):
            el = f'<p class="artigo{cls_r}">{conteudo}</p>'
        elif _ITEM_RE.match(line):
            el = f'<p class="item{cls_r}">{conteudo}</p>'
        else:
            el = f'<p class="{cls_r.strip()}">{conteudo}</p>' if riscado else f"<p>{conteudo}</p>"

        if secao == "anexo":
            doc.anexos.append(el if not conteudo.startswith("<a") else f"<h3>{conteudo}</h3>")
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
    ementa_txt = " ".join(doc.ementa)
    ass_cls = ["nome", "posto", "função"]
    assinatura = "\n".join(
        f'                <h3 class="{ass_cls[i]}">{_p(v)}</h3>' for i, v in enumerate(doc.assinatura)
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
        f'        <h1 class="{titulo_cls}">{_p(titulo)}</h1>',
        '        <div class="ementa">',
        f"            <p{ementa_cls}>{_p(ementa_txt)}</p>",
        "        </div>",
        f'        <div class="texto-documento{rev}">',
        corpo,
    ]
    if doc.assinatura:
        partes += ['            <div class="assinatura">', assinatura, "            </div>"]
    if doc.rodape:
        partes.append(f'            <p class="rodape">{_p(doc.rodape)}</p>')
    if anexos:
        partes.append(anexos)
    partes += ["        </div>", "    </div>", "</body>", "</html>", ""]
    return "\n".join(p for p in partes if p != "")


def convert_rtf(data: bytes, revogado: bool = False, om: str | None = None) -> str:
    doc = parse(rtf_bytes_to_text(data), revogado=revogado)
    return render(doc, om=om) if om else render(doc)

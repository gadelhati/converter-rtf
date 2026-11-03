from fastapi.testclient import TestClient

from app.converter import convert_rtf
from app.main import app

RTF = rb"""{\rtf1\ansi\ansicpg1252
PORTARIA DHN/DGN/MB N\'ba 31, DE 22 DE JUNHO DE 2026.\par
Altera a Portaria DHN/DGN/MB n\'ba 21/2023.\par
O DIRETOR DE HIDROGRAFIA E NAVEGA\'c7\'c3O resolve:\par
Art. 1\'ba A al\'ednea a passa a vigorar:\par
a) Sat\'e9lite - transmiss\'f5es;\par
I - al\'edneas f e g;\par
Art. 2\'ba Esta Portaria entra em vigor.\par
##ASS RICARDO JAQUES FERREIRA\par
Vice-Almirante\par
Diretor\par
Este texto n\'e3o substitui o publicado no DOU de n\'ba 116.\par
ANEXO\par
##LNK [NORMAM-701/DHN](https://www.marinha.mil.br/normam-701.pdf)\par
}"""


def test_estrutura_padrao():
    h = convert_rtf(RTF)
    assert '<h1 class="identificacao-documento">PORTARIA DHN/DGN/MB Nº 31' in h
    assert "<title>PORTARIA DHN/DGN/MB Nº 31, DE 22 DE JUNHO DE 2026.</title>" in h
    assert '<div class="ementa">\n            <p>Altera a Portaria' in h
    assert '<p class="artigo">Art. 1º' in h
    assert '<p class="item">a) Satélite' in h
    assert '<p class="item">I - alíneas' in h
    assert '<h3 class="nome">RICARDO JAQUES FERREIRA</h3>' in h
    assert '<h3 class="função">Diretor</h3>' in h
    assert '<p class="rodape">Este texto não substitui' in h
    assert '<h3><a href="https://www.marinha.mil.br/normam-701.pdf" target="_blank">NORMAM-701/DHN</a></h3>' in h
    assert 'class="texto-documento riscado"' not in h


def test_revogado_risca():
    h = convert_rtf(RTF, revogado=True)
    assert 'class="identificacao-documento riscado"' in h
    assert '<p class="riscado">Altera' in h
    assert '<div class="texto-documento riscado">' in h


def test_api_zip():
    c = TestClient(app)
    r = c.post("/api/convert", files=[("files", ("p31.rtf", RTF, "application/rtf"))])
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert c.post("/api/convert", files=[("files", ("x.txt", b"x"))]).status_code == 400


RTF2 = rb"""{\rtf1\ansi\ansicpg1252{\fonttbl{\f0 Arial;}}
##ATO PORTARIA N\'ba 5\par
##EME Disp\'f5e sobre {\i navios}.\par
##TEX Art. 1\'ba Volume de 10 m{\super 3} e H{\sub 2}O, {\b importante} e {\i it\'e1lico}.\par
##TCH Art. 2\'ba Revogado.\par
##ASS\par
JO\'c3O DA SILVA\par
##ASS Contra-Almirante\par
##ASS Diretor\par
##DOU Este texto n\'e3o substitui o publicado no DOU.\par
##LNK (https://exemplo.mil.br/a.pdf) [Ver anexo]\par
}"""


def test_sobrescrito_e_formatacao():
    h = convert_rtf(RTF2)
    assert "10 m<sup>3</sup>" in h
    assert "H<sub>2</sub>O" in h
    assert "<strong>importante</strong>" in h
    assert "<em>itálico</em>" in h
    assert "sobre <em>navios</em>." in h
    assert '<p class="artigo riscado">Art. 2º Revogado.</p>' in h


def test_assinatura_completa_na_div():
    h = convert_rtf(RTF2)
    div = h.split('<div class="assinatura">')[1].split("</div>")[0]
    assert '<h3 class="nome">JOÃO DA SILVA</h3>' in div
    assert '<h3 class="posto">Contra-Almirante</h3>' in div
    assert '<h3 class="função">Diretor</h3>' in div
    assert h.count("JOÃO DA SILVA") == 1


def test_link():
    h = convert_rtf(RTF2)
    assert '<a href="https://exemplo.mil.br/a.pdf" target="_blank">Ver anexo</a>' in h
    assert "(https://" not in h


RTF3 = rb"""{\rtf1\ansi\ansicpg1252{\fonttbl{\f0 Arial;}}
##ATO PORTARIA N\'ba 6\par
##EME Aprova normas.\par
##TEX 1. INTRODU\'c7\'c3O\par
Texto qualquer.\par
1.1 Objetivo\par
2. {\b DEFINI\'c7\'d5ES}\par
##ASS FULANO\par
##ANE ANEXO A\par
1. Item do anexo\par
}"""


def test_sumario_sem_anexos():
    h = convert_rtf(RTF3)
    nav = h.split('<nav class="sumario">')[1].split("</nav>")[0]
    assert '<a href="#secao-1">1. INTRODUÇÃO</a>' in nav
    assert '<li class="nivel-2"><a href="#secao-1-1">1.1 Objetivo</a>' in nav
    assert "<strong>DEFINIÇÕES</strong>" in nav
    assert "ANEXO A" not in nav
    assert "Item do anexo" in nav
    assert '<p id="secao-1">1. INTRODUÇÃO</p>' in h
    assert nav.count("<li") == 4


def test_secao_no_anexo_e_capitulo():
    rtf = rb"""{\rtf1\ansi ##ATO PORTARIA 7\par ##EME Aprova.\par Art. 1\'ba Aprovar.\par ##ASS FULANO\par ##ANE ANEXO\par CAP\'cdTULO I\par 1.1\tab Generalidades\par}"""
    nav = convert_rtf(rtf).split('<nav class="sumario">')[1].split("</nav>")[0]
    assert "CAPÍTULO I" in nav and "Generalidades" in nav and "ANEXO" not in nav


def test_sem_secoes_sem_sumario():
    assert "sumario" not in convert_rtf(RTF2)


def test_sumario_depois_do_rodape():
    h = convert_rtf(RTF3.replace(b"##ANE", b"##DOU Este texto n\\'e3o substitui.\\par\n##ANE"))
    assert h.index('class="assinatura"') < h.index('class="rodape"') < h.index('class="sumario"') < h.index("ANEXO A")

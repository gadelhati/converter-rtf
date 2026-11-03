# Conversor de RTF para HTML (FastAPI)

Converte portarias em RTF para o novo padrão HTML da DHN (`Padrão_Normam.html` / `Padrão_Normam_Revogado.html`).

## Executar
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Abra http://localhost:8000, selecione os RTF e baixe o ZIP (HTML + CSS + brasão).
Documentação da API: http://localhost:8000/docs

## Endpoints
- `POST /api/convert` — vários `files`, campos `revogado` e `om`; devolve ZIP.
- `POST /api/convert/html` — um `file`; devolve o HTML.

## Regras de conversão
Automáticas: 1ª linha "PORTARIA..." = título; linha seguinte = ementa; "Art. N" = `p.artigo`;
"I -", "a)", "§" = `p.item`; "Este texto não substitui..." = rodapé; "ANEXO" = anexo.

Marcadores (herdados do conversor Java): `##ATO` título, `##EME` ementa, `##TEX` texto,
`##ASS` assinatura (nome, posto, função nas 3 linhas), `##DOU` rodapé, `##ANE` anexo,
`##TCH` linha riscada, `##LNK` links `[texto](url)`, `##REV` documento revogado.
`(INSERIR AQUI A IMAGEM arquivo.png)` insere imagem.

## Testes
```bash
pytest
```

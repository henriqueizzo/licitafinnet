"""Relatório em PDF de uma licitação com a identidade Finnet.

Reúne num único documento tudo o que o card mostra no detalhe (dados do certame,
classificação e scores da IA, justificativa, prazos, exigências, riscos, checklist
de documentação com o que já foi anexado, situação no pipeline e links) para o
time compartilhar sem copiar e colar. Gerado com reportlab (sem IA, resposta
imediata).
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from ..models import Analise, Licitacao, Oportunidade, Usuario

_LOGO = Path(__file__).resolve().parent.parent / "assets" / "finnet-logo.png"

# Paleta do design system Finnet (styles.css)
AZUL = colors.HexColor("#1C2E55")
AZUL_TEXTO = colors.HexColor("#16254A")
AZUL_SUAVE = colors.HexColor("#EDF1F8")
TEXTO = colors.HexColor("#0F172A")
TEXTO_SUAVE = colors.HexColor("#475569")
TEXTO_MUDO = colors.HexColor("#94A3B8")
LINHA = colors.HexColor("#E2E8F0")
PANEL_2 = colors.HexColor("#F8FAFC")

# Classificação da IA → (fundo pastel, texto escuro do matiz), como as pílulas da tela
CORES_CLASSIFICACAO = {
    "EXCELENTE OPORTUNIDADE": (colors.HexColor("#ECFDF5"), colors.HexColor("#047857")),
    "BOA OPORTUNIDADE": (AZUL_SUAVE, AZUL_TEXTO),
    "OPORTUNIDADE MODERADA": (colors.HexColor("#FFFBEB"), colors.HexColor("#B45309")),
    "ALTO RISCO": (colors.HexColor("#FFFBEB"), colors.HexColor("#B45309")),
    "NÃO RECOMENDADO": (colors.HexColor("#FEF2F2"), colors.HexColor("#B91C1C")),
}

FONTES = {"pncp": "PNCP", "fiesc": "FIESC", "fiergs": "FIERGS", "fiems": "FIEMS",
          "manual": "Cadastro manual", "conlicitacao": "ConLicitação", "bll": "BLL",
          "paradigma_mural": "Paradigma Mural"}

ESTAGIOS = {
    "identificada": "Identificada", "em_analise": "Em análise", "impugnacao": "Impugnação",
    "proposta_enviada": "Proposta enviada", "disputa": "Disputa", "ganhou": "Ganhou",
    "perdeu_nogo": "Perdeu / No Go",
}

LARGURA_UTIL = A4[0] - 2 * 18 * mm


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=15, leading=19, textColor=TEXTO),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName="Helvetica",
                              fontSize=9, leading=12, textColor=TEXTO_SUAVE),
        "secao": ParagraphStyle("secao", parent=base["Normal"], fontName="Helvetica-Bold",
                                fontSize=8, leading=10, textColor=AZUL, spaceBefore=10,
                                spaceAfter=4),
        "corpo": ParagraphStyle("corpo", parent=base["Normal"], fontName="Helvetica",
                                fontSize=9.5, leading=13.5, textColor=TEXTO, alignment=TA_LEFT),
        "item": ParagraphStyle("item", parent=base["Normal"], fontName="Helvetica",
                               fontSize=9.5, leading=13.5, textColor=TEXTO, leftIndent=10,
                               bulletIndent=0, spaceAfter=1.5),
        "rotulo": ParagraphStyle("rotulo", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=7, leading=9, textColor=TEXTO_MUDO),
        "valor": ParagraphStyle("valor", parent=base["Normal"], fontName="Helvetica-Bold",
                                fontSize=10, leading=13, textColor=TEXTO),
        "pilula": ParagraphStyle("pilula", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=8, leading=10),
        "mono": ParagraphStyle("mono", parent=base["Normal"], fontName="Courier",
                               fontSize=7.2, leading=9, textColor=TEXTO),
        "celula": ParagraphStyle("celula", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=8.5, leading=11, textColor=TEXTO),
        "celula_cab": ParagraphStyle("celula_cab", parent=base["Normal"],
                                     fontName="Helvetica-Bold", fontSize=7, leading=9,
                                     textColor=TEXTO_SUAVE),
    }


def _t(texto) -> str:
    """Escapa texto livre para o mini-markup do Paragraph (preserva quebras de linha)."""
    return escape(str(texto or "")).replace("\n", "<br/>")


def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _data_br(iso) -> str:
    if not iso:
        return "—"
    partes = str(iso)[:10].split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 and partes[2] else "—"


def _secao(titulo: str, st) -> list:
    """Rótulo de seção em caixa alta + linha fina azul, como os cabeçalhos de tabela da tela."""
    tabela = Table([[Paragraph(titulo.upper(), st["secao"])]], colWidths=[LARGURA_UTIL])
    tabela.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, LINHA),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [tabela, Spacer(1, 4)]


def _lista(itens, st) -> list:
    return [Paragraph(_t(item), st["item"], bulletText="•") for item in itens if item]


def _pilula(texto: str, fundo, cor, st) -> Table:
    p = Paragraph(f'<font color="{cor.hexval()}">{_t(texto)}</font>', st["pilula"])
    tabela = Table([[p]])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabela


def _cabecalho(lic: Licitacao, analise: Analise | None, st) -> list:
    partes = []
    linha_meta = " · ".join(filter(None, [
        f"{lic.municipio}/{lic.uf}" if lic.municipio else (lic.uf or ""),
        lic.modalidade,
        f"Sistema: {lic.sistema}" if lic.sistema else "",
        f"nº {lic.id_externo}" if lic.id_externo else "",
        FONTES.get(lic.fonte, lic.fonte),
    ]))
    titulo = [Paragraph(_t(lic.orgao or "Órgão não informado"), st["titulo"]),
              Paragraph(_t(linha_meta), st["sub"])]

    selos = []
    if lic.suspensa:
        selos.append(_pilula("SUSPENSA", colors.HexColor("#FFFBEB"), colors.HexColor("#B45309"), st))
    if analise and analise.classificacao_final:
        fundo, cor = CORES_CLASSIFICACAO.get(analise.classificacao_final, (AZUL_SUAVE, AZUL_TEXTO))
        selos.append(_pilula(analise.classificacao_final, fundo, cor, st))
    if selos:
        selos_tabela = Table([selos], hAlign="RIGHT")
        selos_tabela.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
    else:
        selos_tabela = ""

    cab = Table([[titulo, selos_tabela]], colWidths=[LARGURA_UTIL * 0.66, LARGURA_UTIL * 0.34])
    cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    partes.append(cab)
    partes.append(Spacer(1, 8))
    return partes


def _metricas(lic: Licitacao, analise: Analise | None, oportunidade: Oportunidade | None, st) -> Table:
    """Faixa de indicadores (como o .detalhes-meta da tela)."""
    celulas = [
        ("Valor estimado", _brl(lic.valor_estimado)),
        ("Identificada em", _data_br(lic.criado_em.isoformat() if lic.criado_em else "")),
        ("Abertura", _data_br(lic.data_abertura)),
        ("Vence em", _data_br(lic.data_encerramento)),
    ]
    if analise and analise.classificacao_final:
        celulas.append(("Scores da IA", f"EDI {analise.score_beneficios}/10 · Pag {analise.score_pagamentos}/10"))
    if oportunidade:
        celulas.append(("Estágio no pipeline", ESTAGIOS.get(oportunidade.estagio, oportunidade.estagio)))

    # Cada célula é uma lista de flowables (rótulo em cima, valor embaixo)
    dados = [[[Paragraph(_t(r), st["rotulo"]), Paragraph(_t(v), st["valor"])] for r, v in celulas]]
    faixa = Table(dados, colWidths=[LARGURA_UTIL / len(celulas)] * len(celulas))
    faixa.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL_2),
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return faixa


def _justificativa(analise: Analise, st) -> Table:
    fundo, cor = CORES_CLASSIFICACAO.get(analise.classificacao_final, (AZUL_SUAVE, AZUL_TEXTO))
    titulo = (f'Por que "{analise.classificacao_final}"?' if analise.classificacao_final
              else "Justificativa da análise")
    caixa = Table([[
        Paragraph(f'<b><font color="{cor.hexval()}">{_t(titulo)}</font></b>', st["corpo"]),
    ], [
        Paragraph(_t(analise.justificativa), st["corpo"]),
    ]], colWidths=[LARGURA_UTIL])
    caixa.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo),
        ("LINEBEFORE", (0, 0), (0, -1), 3, cor),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 7), ("BOTTOMPADDING", (0, 0), (0, 0), 1),
        ("TOPPADDING", (0, 1), (0, 1), 1), ("BOTTOMPADDING", (0, 1), (0, 1), 7),
    ]))
    return caixa


def _tabela_checklist(checklist: list, anexos_por_item: dict, st) -> Table:
    cab = [Paragraph(t, st["celula_cab"]) for t in ("CATEGORIA", "DOCUMENTO", "REF. EDITAL", "SITUAÇÃO")]
    linhas = [cab]
    for item in checklist:
        documento = (item.get("documento") or "").strip()
        anexos = anexos_por_item.get(documento, [])
        if anexos:
            situacao = f'<font color="#047857"><b>Anexado</b></font><br/>{_t("; ".join(anexos))}'
        else:
            situacao = '<font color="#B45309"><b>Pendente</b></font>'
        linhas.append([
            Paragraph(_t(item.get("categoria") or "Outros"), st["celula"]),
            Paragraph(_t(documento), st["celula"]),
            Paragraph(_t(item.get("referencia_edital") or "—"), st["celula"]),
            Paragraph(situacao, st["celula"]),
        ])
    larguras = [LARGURA_UTIL * f for f in (0.20, 0.42, 0.14, 0.24)]
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PANEL_2),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINHA),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela


def _rodape_e_logo(gerado_por: str):
    """Logo no topo e rodapé com origem, data e paginação em toda página."""
    quando = datetime.now().strftime("%d/%m/%Y %H:%M")

    def desenhar(canvas, doc):
        canvas.saveState()
        largura, altura = A4
        margem = 18 * mm
        # Logo (proporção preservada, altura fixa)
        if _LOGO.exists():
            try:
                img = Image(str(_LOGO))
                razao = img.imageWidth / float(img.imageHeight)
                h = 9 * mm
                canvas.drawImage(str(_LOGO), margem, altura - margem - h + 4 * mm, width=h * razao, height=h,
                                 preserveAspectRatio=True, mask="auto")
            except Exception:  # logo corrompida não pode derrubar o relatório
                pass
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(TEXTO_MUDO)
        canvas.drawRightString(largura - margem, altura - margem + 5 * mm, "CRM de Licitações · Relatório da oportunidade")
        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.6)
        canvas.line(margem, altura - margem + 1.5 * mm, largura - margem, altura - margem + 1.5 * mm)
        # Rodapé
        canvas.line(margem, margem - 3 * mm, largura - margem, margem - 3 * mm)
        canvas.drawString(margem, margem - 7 * mm,
                          f"Gerado pelo LicitaFinnet em {quando}" + (f" por {gerado_por}" if gerado_por else "")
                          + " · uso interno")
        canvas.drawRightString(largura - margem, margem - 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    return desenhar


def gerar_pdf(
    lic: Licitacao,
    analise: Analise | None,
    oportunidade: Oportunidade | None,
    anexos_por_item: dict[str, list[str]],
    anexos_avulsos: list[str],
    usuario: Usuario | None = None,
) -> bytes:
    """Monta o relatório completo da licitação e devolve os bytes do PDF."""
    st = _estilos()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=24 * mm, bottomMargin=20 * mm,
        title=f"Licitação — {lic.orgao}", author="LicitaFinnet", subject=lic.objeto or "",
    )
    fluxo: list = []
    fluxo += _cabecalho(lic, analise, st)
    fluxo.append(_metricas(lic, analise, oportunidade, st))
    fluxo.append(Spacer(1, 8))

    if analise and analise.justificativa:
        fluxo.append(_justificativa(analise, st))
        fluxo.append(Spacer(1, 6))

    fluxo += _secao("Objeto", st)
    fluxo.append(Paragraph(_t(lic.objeto or "—"), st["corpo"]))
    if analise and analise.objeto_resumido:
        fluxo.append(Spacer(1, 3))
        fluxo.append(Paragraph(f"<b>Resumo da IA:</b> {_t(analise.objeto_resumido)}", st["corpo"]))

    if analise:
        blocos_texto = [
            ("Credenciamento", analise.credenciamento_analise),
            ("Custo estimado de emissão", analise.custo_emissao_cartoes),
        ]
        for titulo, texto in blocos_texto:
            if texto:
                fluxo += _secao(titulo, st)
                fluxo.append(Paragraph(_t(texto), st["corpo"]))

        if analise.prazos:
            fluxo += _secao("Prazos", st)
            fluxo += _lista(
                [f"{p.get('descricao', '')}: {p.get('data_ou_prazo', '')}" if isinstance(p, dict) else p
                 for p in analise.prazos], st)

        blocos_lista = [
            ("Alertas de impugnação", analise.alertas_impugnacao),
            ("Atestados exigidos", analise.atestados_exigidos),
            ("Exigências de habilitação", analise.exigencias_habilitacao),
            ("Exigências técnicas", analise.exigencias_tecnicas),
            ("Riscos", analise.riscos),
        ]
        for titulo, itens in blocos_lista:
            if itens:
                fluxo += _secao(titulo, st)
                fluxo += _lista(itens, st)

        checklist = analise.documentos_habilitacao or []
        if checklist:
            fluxo += _secao("Checklist de documentação", st)
            fluxo.append(_tabela_checklist(checklist, anexos_por_item, st))
    else:
        fluxo += _secao("Análise da IA", st)
        fluxo.append(Paragraph("Licitação ainda sem análise.", st["corpo"]))

    if anexos_avulsos:
        fluxo += _secao("Outros anexos", st)
        fluxo += _lista(anexos_avulsos, st)

    if oportunidade and (oportunidade.responsavel or oportunidade.notas):
        fluxo += _secao("Acompanhamento do time", st)
        if oportunidade.responsavel:
            fluxo.append(Paragraph(f"<b>Responsável:</b> {_t(oportunidade.responsavel)}", st["corpo"]))
        if oportunidade.notas:
            fluxo.append(Paragraph(f"<b>Notas:</b> {_t(oportunidade.notas)}", st["corpo"]))

    links = [(f"Licitação no sistema{f' ({lic.sistema})' if lic.sistema else ''}", lic.endereco_licitacao),
             ("Portal de origem", lic.link), ("Edital", lic.edital_url)]
    links = [(r, u) for r, u in links if u]
    if links:
        fluxo += _secao("Links", st)
        for rotulo, url in links:
            fluxo.append(Paragraph(
                f'<b>{_t(rotulo)}:</b> <link href="{escape(url)}" color="#16254A">{_t(url)}</link>',
                st["corpo"]))

    if analise and analise.analise_completa:
        fluxo += _secao("Análise completa (íntegra)", st)
        # Texto integral com tabelas em ASCII: monoespaçado, um parágrafo por bloco
        for bloco in analise.analise_completa.split("\n\n"):
            if bloco.strip():
                fluxo.append(Paragraph(_t(bloco).replace(" ", "&nbsp;"), st["mono"]))
                fluxo.append(Spacer(1, 4))

    desenhar = _rodape_e_logo(getattr(usuario, "nome", "") or getattr(usuario, "email", "") or "")
    doc.build(fluxo, onFirstPage=desenhar, onLaterPages=desenhar)
    return buffer.getvalue()


def nome_arquivo(lic: Licitacao) -> str:
    import re
    base = " - ".join(filter(None, [lic.orgao, lic.id_externo]))[:90] or f"licitacao-{lic.id}"
    base = re.sub(r'[\\/:*?"<>|]+', " ", base).strip()
    return f"Licitacao Finnet - {base}.pdf"

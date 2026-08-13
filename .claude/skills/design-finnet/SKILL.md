---
name: design-finnet
description: Design system do LicitaFinnet (tema claro, identidade Finnet) — usar sempre que criar ou alterar qualquer tela, componente ou estilo do frontend.
---

# Design system Finnet — CRM (tema claro)

Identidade adaptada em 2026-08-12 a partir do design system do CRM de origem
(LicitaProsperaCRM), com a paleta trocada para o azul-marinho da logomarca Finnet.
Os tokens vivem em `frontend/src/styles.css` (`:root`) — sempre usar as variáveis
CSS, nunca cores hardcoded.

## Conceito

CRM claro, limpo e "SaaS moderno": fundo branco, cartões brancos de cantos bem
arredondados com bordas cinza-claras, azul-marinho #1C2E55 como cor de ação,
status em pílulas pastel com bolinha colorida. Nada de glow, gradientes ou grid
de fundo.

## Cores da marca Finnet (da logomarca)

- Azul-marinho do wordmark: #132148–#19274A · hexágono: #1D3E61 · vermelho do
  detalhe: #A01B20. O vermelho da marca é ACENTO da logomarca — não usar como cor
  de status (o vermelho semântico continua #EF4444).

## Tokens (styles.css)

- Fundos: `--void` #FFF (página) · `--panel` #FFF (cartões) · `--panel-2` #F8FAFC (seções suaves) · bordas `--linha` #E2E8F0 / `--linha-suave` #F1F5F9
- Marca: `--azul` #1C2E55 (ações) · `--azul-luz` #2F4A7A (hover/realce) · `--azul-suave` #EDF1F8 (fundos de destaque) · `--azul-texto` #16254A (texto sobre pastel)
- Texto: `--texto` #0F172A · `--texto-suave` #475569 · `--texto-mudo` #94A3B8
- Status: verde #10B981, âmbar #F59E0B, vermelho #EF4444 — cada um com `-fundo`
  (pastel: #ECFDF5/#FFFBEB/#FEF2F2), `-borda` (clara) e `-texto` (escuro do matiz:
  #047857/#B45309/#B91C1C). Em pílula pastel, o texto usa SEMPRE a variante `-texto`,
  nunca a cor plena.
- Forma: `--raio` 16px (cartões) · `--raio-sm` 12px (inputs/botões) · pílulas 999px
- Foco: `--foco` (anel azul-marinho claro #C9D5E8); sombras discretas `--sombra`/`--sombra-md`

## Tipografia

**Inter** para tudo (Google Fonts no `index.html`, pesos 400–800). Papéis por peso,
não por família: títulos/valores 600–700; rótulos de tabela/seção 600 em 0.68–0.72rem
uppercase discreto (letter-spacing ≤0.08em); texto corrido 400. Números que alinham
em coluna: `font-variant-numeric: tabular-nums`.

## Regras de componente

- **Cartões**: fundo branco + `border: 1px solid var(--linha)` + raio 16px. Sem gradiente.
- **Abas (nav)**: controle segmentado — trilho `#F1F5F9` raio 12px com padding 4px;
  aba ativa = fundo branco + sombra leve + texto escuro; inativa = texto slate-500.
- **Ação primária**: fundo `--azul` sólido, texto branco 600, raio 12px, hover
  `brightness(1.1)`. Sem uppercase, sem glow.
- **Badges/pílulas de status** (scores, vereditos, contadores): raio 999px, fundo
  pastel + texto `-texto` do matiz; contadores usam `--azul-suave`/`--azul-texto`.
- **Semântica**: verde = aprovado/alto, âmbar = revisar/moderado, vermelho =
  reprovado/baixo. Azul é ação/informação, nunca status de aprovação.
- **Inputs**: fundo branco, borda #CBD5E1, raio 12px; foco = borda azul + `--foco`.
  Labels em 0.83rem/500 slate-700 (sem uppercase).
- **Kanban**: colunas `#F8FAFC` raio 16px; cartões brancos raio 12px, hover borda
  azul-clara + sombra leve. Faixa de 4px à esquerda na cor PLENA do matiz da
  classificação da IA (`.faixa-verde/azul/amarelo/vermelho`, decisão 2026-07-17 —
  única exceção à regra "cor plena só em bolinha/LED"). Cartões arrastáveis
  (@dnd-kit): coluna de destino ganha fundo `--azul-suave`; chip do responsável
  (iniciais, pílula azul-suave) no topo do cartão.
- **Tabelas**: th com fundo `--panel-2`, texto slate-500 uppercase 0.68rem; linhas
  divididas por `--linha-suave`; hover `--panel-2`.
- **Logomarca**: NUNCA alterar/recolorir o `finnet-logo.png`. Sobre fundo claro
  vai direto (o `.logo-chip` existe mas é transparente).
- **LED** (`.led`): bolinha verde pulsante = processo automático ativo; âmbar
  (`.led-alerta`) = há avisos. Sem box-shadow/glow.

## Ao criar telas novas

Reusar as classes existentes (`.tile`, `.cartao`, `.tabela`, `.veredito`, `.perfil`,
`.acoes`, `.score`) antes de criar novas. Indicadores agregados usam `.cockpit`/`.tile`.
Nomes de classe em português, como o restante do projeto.

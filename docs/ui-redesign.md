# UI Redesign — Decisões de Design (interface Flet)

> Ferramenta de orientação: **ui-ux-pro-max-cli 2.15.0** (skill instalada em `.opencode/skills/` via `uipro init -a opencode`).
> As recomendações da skill são orientadas a web (shadcn/ui + Tailwind). Elas são usadas **como referência** e os componentes são implementados **nativamente em Flet 1.0** (`mychirp/fletui`), sem interface web paralela. Histórico: os mesmos tokens foram aplicados primeiro na wxui (removida) e migrados para a Flet UI.

## 1. Princípios adotados (da skill, adaptados ao Flet)

| Recomendação da skill (design-system) | Implementação no Flet |
|---|---|
| Arquitetura de tokens em 3 camadas (primitivo → semântico → componente) | `chirp/wxui/theme.py`: dicionários de primitivos (hex), papéis semânticos (`BG`, `FG`, `ACCENT`...) e helpers por componente |
| Escala de espaçamento base 4px (4/8/12/16/24) | Constantes `SPACING_XS/SM/MD/LG/XL` aplicadas em margens/paddings dos painéis modernizados |
| Raio discreto (4–8px), sem exageros | wx não tem bordas arredondadas nativas por widget em GTK; cantos ficam nativos — a "suavidade" vem do contraste e dos espaçamentos (decisão: não pintar cantos manualmente) |
| Dark mode = remapeamento de papéis semânticos (não de componentes) | `theme.py` mantém dois dicionários de papéis; um switch troca todos os componentes que usam os helpers |
| Estados de componente (default/hover/focus/active/disabled) com prioridade disabled > loading > active > focus > hover | Widgets wx/GTK mantêm estados nativos; o tema garante contraste mínimo WCAG AA nos dois modos |
| Tipografia legível e hierarquia clara | Fonte padrão do sistema é preservada (decisão: não forçar fontes); hierarquia via espaçamento e peso do rótulo, não via tamanhos exóticos |

## 2. Paleta semântica (derivada da escala neutra da skill)

Modo claro (base) e modo escuro (remapeamento), todos com contraste AA verificado
para texto sobre os fundos correspondentes:

| Papel | Claro | Escuro | Uso |
|---|---|---|---|
| `BG_WINDOW` | `#F6F7F9` | `#1E1F24` | janelas/diálogos |
| `BG_PANEL` | `#FFFFFF` | `#26272C` | painéis/cards |
| `BG_GRID_ALT` | `#F1F3F5` | `#222329` | linhas alternadas do grid |
| `BG_PENDING` | `#FFF4D6` | `#3A3320` | células alteradas não salvas |
| `FG_TEXT` | `#1A1C1E` | `#E8EAED` | texto principal |
| `FG_MUTED` | `#5A6069` | `#9AA1AC` | texto secundário |
| `ACCENT` | `#1A6B8F` | `#5FB2CE` | seleção/detalhe/links |
| `ACCENT_DOWNLOAD` | `#1E7B4F` | `#4CAF7D` | operação Ler do rádio |
| `ACCENT_UPLOAD` | `#B3541E` | `#E08A4F` | operação Gravar no rádio |
| `ERROR` | `#B3261E` | `#F2B8B5` | mensagens de erro |
| `BORDER` | `#D8DCE0` | `#383B42` | separadores |

## 3. Direção visual

- Aplicação **desktop técnica de engenharia**: limpa, profissional, sem
  gradientes decorativos, sem animações pesadas.
- Hierarquia: barra de título → área de trabalho → barra de status com
  informações do rádio/arquivo.
- **Ler × Gravar** nunca confundíveis: cor + ícone + texto no diálogo de
  clonagem (verde para download, laranja para upload).
- Erros em duas camadas: mensagem simplificada + detalhes técnicos
  expandíveis (mensagem original do driver, etapa, caminho do log).
- Funcionalidades existentes 100% preservadas: nenhum menu/atalho é
  removido; a mudança é incremental e reversível por arquivo.

## 4. Limitações honestas

- wxGTK não permite estilizar controles nativos de menu/combobox sem
  desativar o tema nativo — esses mantêm a aparência do sistema.
- O modo escuro cobre os componentes centrais (janela, grids, diálogos,
  painéis modernizados); widgets nativos não pintados herdam o visual do
  GTK (aceitável; documentado).
- Sobre o relatório de saúde do graphify: o build inicial registrou
  arestas pendentes geradas pela própria extração AST (referências de
  import a módulos sem nó correspondente) — artefato conhecido da
  extração estrutural, não um problema do código do CHIRP.

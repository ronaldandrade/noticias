# Guia de anotação de sentimento (títulos de notícias, PT-BR)

## Tarefa
Classificar o **título** da notícia em três classes, do ponto de vista de quem acompanha
a economia e o mercado financeiro brasileiro:

| Rótulo | Quando usar | Exemplos |
|---|---|---|
| **Positivo** | O fato é favorável para a economia, mercado ou empresa citada. | "Lucro do Nubank cresce 41% no 1º tri"; "Ibovespa bate recorde com cessar-fogo"; "Balança comercial tem superávit recorde" |
| **Negativo** | O fato é desfavorável: queda, perda, risco, crise, evento adverso. | "CVC desaba 15% após balanço"; "Casas Bahia pede recuperação judicial"; "Juros bancários batem recorde" |
| **Neutro** | Informativo, sem direção clara, ambíguo, pergunta, serviço/tutorial, ou **fora do escopo econômico** (esporte, entretenimento, política sem efeito econômico explícito). | "Receita divulga regras do IR 2025"; "Fed mantém juros"; "Mega-Sena: resultado" |

## Regras de decisão
1. **Polaridade pelo fato, não pelas palavras.** "Ibovespa interrompe quatro meses de
   *queda*" é positivo; "Dólar *cai*" tende a ser positivo para o Brasil; "Petróleo *sobe*
   após escalada de conflito" é negativo (risco).
2. **Perspectiva:** economia brasileira e investidor local. Inflação, juros e dólar em
   alta, desemprego em alta, déficit, tarifas, sanções e guerra são negativos; o inverso é positivo.
3. **Resultados corporativos:** lucro/receita acima do esperado ou em alta = positivo;
   prejuízo, queda de lucro, recuperação judicial, queda forte da ação = negativo.
   Resultado misto (ex.: "lucra mais que o esperado, mas receita decepciona") = neutro.
4. **Perguntas e títulos especulativos** ("Musk ameaça a Tesla?") = neutro.
5. **Anúncios de produto/lançamento sem efeito financeiro explícito** = neutro.
6. **Mercado misto** ("dólar cai, Ibovespa cai"; "bolsas mistas") = neutro.
7. **Fora do escopo** (esporte, celebridades, BBB, loterias, receitas, tutoriais) = neutro.
8. Em dúvida entre polaridade fraca e neutro, escolher **neutro**.

## Como foi produzido o conjunto (`data/labels/rotulos.csv`)
- Origem: tabela `Noticia` (≈19,9 mil notícias, mar/2025–nov/2026).
- Filtros: erro de encoding, textos em inglês, duplicatas por URL e por título normalizado
  (≈16,4 mil restantes).
- **Amostra aleatória** de 1.000 títulos, estratificada por fonte × mês (sem usar score nem
  palavras-chave, para não herdar viés do baseline lexical), **mais 199 títulos do conjunto
  "gold"**, que já tinham rótulo humano binário (Positivo/Negativo) feito pelo autor.
- **Anotador:** um LLM (Claude), aplicando este guia, **vendo apenas fonte e título**. Os
  rótulos humanos do conjunto gold **não** foram mostrados durante a anotação.
- Divisão **temporal**: 70% mais antigo = `train`; 10% seguinte = `val`; 20% mais recente = `test`.

## Concordância e limitações
- No conjunto gold, onde o LLM atribuiu Positivo/Negativo (n=103), a concordância com o
  rótulo humano foi de **89,3%** (kappa de Cohen = **0,76**).
- O rótulo humano original **não tem a classe Neutro** (escolha forçada entre Positivo e
  Negativo). Por isso o kappa em 3 classes (0,28) **não** é uma medida justa de concordância.
  Dos 108 "Positivos" humanos, 69 foram considerados Neutros pelo LLM (por ex. regras do
  IR, "É #FAKE..."), o que sugere que "Positivo" funcionou como padrão para o que não era negativo.
- Há **11 itens com polaridade oposta** entre humano e LLM (arquivo local
  `data/annotations/disputados.csv`). Vários parecem erro do rótulo original (por ex.
  "Como Trump fez bolsas despencarem..." marcado como Positivo) e devem ser decididos
  por revisão humana antes de qualquer uso como padrão-ouro.
- **Anotador único (LLM):** os rótulos podem herdar vieses do modelo e deste guia. Os
  resultados dos modelos devem ser lidos como "concordância com este critério de anotação".
- Classes desbalanceadas (≈62% Neutro, 23% Negativo, 15% Positivo); o conjunto de teste
  tem só 240 itens (42 negativos, 27 positivos), então os intervalos de confiança serão largos.
  Reportar F1 macro com bootstrap.
- Redistribuição: o repositório publica apenas `id`, `url`, `fonte`, `data` e rótulos. O
  texto das notícias não é redistribuído.

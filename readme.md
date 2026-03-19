# Monitoramento de Sentimento 
![alt text](/print.png)
Este projeto é uma plataforma integrada de **Agregação e Análise de Sentimentos** de notícias. Ele combina técnicas de raspagem de dados (_scraping_), persistência em banco de dados, processamento de linguagem natural (NLP) e um pipeline avançado de Machine Learning para classificar o teor das notícias em Positivo ou Negativo em tempo real detectando possíveis sinais de risco a partir de fontes.

##  Resultados Obtidos
O modelo apresenta uma **Acurácia Média de 0.61 (± 0.13)** em validação cruzada, o que demonstra uma capacidade sólida de generalização para dados textuais curtos (apenas títulos).

### Análise de Performance e Contexto Estatístico

Diferente de modelos genéricos, este classificador foi validado contra baselines rigorosos para garantir sua utilidade em um ambiente de baixa previsibilidade como o financeiro:

. Baseline Aleatório: 50% (o modelo supera o acaso em 11 pontos percentuais).

. Majority Class Baseline: 54% (baseado na distribuição real de 108 notícias positivas vs 92 negativas no dataset de treino).

- Desempenho Atual: 61% de acurácia média em validação cruzada.

Por que 61% é um resultado sólido neste estágio?

. Limitação Semântica: O modelo utiliza TF-IDF, que analisa a frequência de palavras, mas não o contexto profundo. Títulos curtos (5–10 palavras) possuem pouca densidade de informação para modelos estatísticos clássicos.

. Volume de Dados: O treinamento foi realizado com apenas 200 amostras rotuladas manualmente, o que explica a margem de melhoria conforme o dataset cresce.

. Complexidade do Domínio: Notícias financeiras frequentemente contêm termos ambíguos que exigem compreensão de mercado para correta rotulação.

- Próximo Passo: Implementação de FinBERT (Transformers treinados especificamente para o mercado financeiro) para capturar nuances semânticas e elevar a acurácia para além dos 80%.


## Visão Geral
O sistema coleta notícias de diversas fontes, armazena-as em um banco SQLite e utiliza um classificador baseado em **Support Vector Machines (SVM)** para analisar o sentimento dos títulos. 

## Funcionalidades Principais

-   **Web App (Flask)**: Interface amigável para navegação, filtros por data e assunto.
    
-   **Scraping Automatizado**: Coleta de dados reais utilizando `BeautifulSoup`.
    
-   **Análise Estatística (NLP)**: Dashboard com ranking de tópicos (_trigram analysis_) via `NLTK`.
    
-   **Pipeline de Machine Learning**:
    
    -   Vetorização `TF-IDF` para representação textual.
        
    -   Modelo `SVM` com pesos balanceados para lidar com dados escassos.
        
    -   **Validação Cruzada (K-Fold)**: Avaliação robusta que garante a estabilidade estatística do modelo.

## Detalhes do Modelo de ML

O classificador foi construído focando em evitar o **Vazamento de Dados (Data Leakage)** através do uso de `Pipelines` do Scikit-Learn.
## Estrutura do Repositório
news/
├── app/
│   ├── __init__.py       # Flask app setup
│   ├── routes.py         # Application routes with Blueprint
│   ├── repository.py     # Applying filters to search
│   ├── services.py       # NLTK functions
│   ├── models.py         # Database models
│   ├── scraper.py        # News scraping logic
│   ├── templates/        # HTML templates
│   └── static/           # CSS and static files
|   └── notebooks/      # Study, visualization
├── config.py             # Configuration settings
├── nltk_data/            # NLTK resources (punkt_tab, stopwords)
├── run.py                # Local development entry point
├── Procfile              # Render deployment configuration
├── requirements.txt      # Python dependencies
├── instance/             # Contains db archive database
│   ├── noticias.db       # SQLite database


## Como Executar
1. Instale as dependências:
   ### Pré-requisitos
-   Python 3.11+
-   Virtualenv (recomendado)
### Instalação
1.  **Clone o repositório**
   ``
    git clone https://github.com/ronaldandrade/noticias
    ``
    ``
cd noticias``
2. **Ative o ambiente virtual e instale as dependências**:
``# O arquivo requirements.txt já contém todas as bibliotecas necessárias
``
``pip install -r requirements.txt``
3. **Inicie o Classificador Interativo**:
``
python src/classifier.py
``
4. **Inicie a Aplicação Web**:
``python run.py``
5. **Inicie o classificador interativo**
``pyhon app/classifier.py``

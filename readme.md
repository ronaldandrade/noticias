Scraping de noticias dos principais portais de noticias da internet

```php
noticias/
├── app/
│   ├── __init__.py        # Inicializa a aplicação, configura o Flask e o SQLAlchemy
│   ├── models.py          # Define os modelos de dados
│   ├── routes.py          # Define as rotas e lógicas de exibição/atualização
│   ├── scraper.py         # Lógica de web scraping para buscar as notícias
│   ├── templates/         # Arquivos HTML
│   │   └── index.html     # Todas as notícias listadas
|   |   └── noticia.html   # Página dedicada leitura da notícia
│   └── static/            # Arquivos estáticos (CSS, JavaScript, imagens, etc.)
├── config.py              # Configurações da aplicação
├── requirements.txt       # Lista de dependências do projeto
└── run.py                 # Arquivo para executar a aplicação
```
# app/scraper.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .models import Noticia
from . import db

def buscar_noticias():
    # Exemplo: altere a URL e a lógica conforme a estrutura do site de notícias
    url = "https://www.exemplo.com/noticias"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    noticias_encontradas = []
    for artigo in soup.find_all('article'):
        titulo = artigo.find('h2').get_text(strip=True)
        link = artigo.find('a')['href']
        # Extraia ou defina o conteúdo e data conforme o HTML
        conteudo = "Conteúdo de exemplo"  
        data = datetime.now()
        
        noticia = Noticia(
            titulo=titulo,
            conteudo=conteudo,
            url=link,
            data_publicacao=data
        )
        noticias_encontradas.append(noticia)
    
    # Salva as novas notícias evitando duplicatas
    for noticia in noticias_encontradas:
        if not Noticia.query.filter_by(url=noticia.url).first():
            db.session.add(noticia)
    db.session.commit()
    
    return noticias_encontradas

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .models import Noticia
from . import db

def buscar_noticias():
    fontes = {
        "G1 Economia": "https://g1.globo.com/rss/g1/economia/",
        # "UOL Notícias": "https://feeds.folha.uol.com.br/mercado/rss091.xml",
        "exame": "https://exame.com/feed/",
        # "NY times": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    }
    
    noticias_encontradas = []
    
    for nome, url in fontes.items():
        response = requests.get(url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'xml', from_encoding='utf-8')
        
        for item in soup.find_all('item'):
            titulo = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True)
            conteudo = item.find('description').get_text(strip=True) if item.find('description') else "Sem descrição"
            data_str = item.find('pubDate').get_text(strip=True)
            try:
                data = datetime.strptime(data_str, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
            except ValueError:
                data = datetime.now()
            
            noticia = Noticia(
                titulo=titulo,
                conteudo=conteudo,
                url=link,
                data_publicacao=data
            )
            noticias_encontradas.append(noticia)
    
    for noticia in noticias_encontradas:
        if not Noticia.query.filter_by(url=noticia.url).first():
            db.session.add(noticia)
    db.session.commit()
    
    return noticias_encontradas
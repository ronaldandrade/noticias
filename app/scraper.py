# app/scraper.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .models import Noticia
from . import db

def buscar_noticias():
    url = "https://g1.globo.com/rss/g1/economia/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'xml')
    
    noticias_encontradas = []
    for item in soup.find_all('item'):
        titulo = item.find('title').get_text(strip=True)
        link = item.find('link').get_text(strip=True)
        conteudo = item.find('description').get_text(strip=True) if item.find('description') else "Sem descrição"
        data_str = item.find('pubDate').get_text(strip=True)
        data = datetime.strptime(data_str, "%a, %d %b %Y %H:%M:%S %z")
        
        noticia = Noticia(
            titulo=titulo,
            conteudo=conteudo,
            url=link,
            data_publicacao=data
        )
        noticias_encontradas.append(noticia)
    
    # Debug e salvamento
    print(f"Encontradas {len(noticias_encontradas)} notícias novas")
    for noticia in noticias_encontradas:
        existente = Noticia.query.filter_by(url=noticia.url).first()
        if not existente:
            print(f"Salvando: {noticia.titulo} - {noticia.url}")
            db.session.add(noticia)
        else:
            print(f"Já existe: {noticia.titulo}")
    try:
        db.session.commit()
        print("Commit bem-sucedido!")
    except Exception as e:
        db.session.rollback()
        print(f"Erro no commit: {e}")
    
    return noticias_encontradas
import nltk
from nltk import trigrams
from nltk.corpus import stopwords
from collections import Counter
import os

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

def calcular_top_assuntos(noticias):
    titulos = [n.titulo.lower() for n in noticias]
    stop_words = set(stopwords.words('portuguese'))
    palavras = []
    
    for titulo in titulos:
        tokens = nltk.word_tokenize(titulo)
        tokens = [t for t in tokens if t not in stop_words and len(t) > 3]
        trigramas = [' '.join(t) for t in trigrams(tokens)]
        palavras.extend(trigramas)
    
    contagem = Counter(palavras).most_common(10)
    return [{'assunto': a, 'frequencia': f} for a, f in contagem]
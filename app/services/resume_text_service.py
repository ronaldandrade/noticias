import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from collections import defaultdict
import os

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

def resumir_texto(texto, num_frases=2):
    # Tokeniza em frases
    frases = sent_tokenize(texto, language='portuguese')
    if len(frases) <= num_frases:
        return texto  # Se for muito curto, retorna tudo
    
    # Remove stopwords e calcula frequência de palavras
    stop_words = set(stopwords.words('portuguese'))
    frequencia = defaultdict(int)
    for frase in frases:
        palavras = word_tokenize(frase.lower())
        for palavra in palavras:
            if palavra not in stop_words and len(palavra) > 3:
                frequencia[palavra] += 1
    
    # Pontua as frases com base nas palavras frequentes
    pontuacao = {}
    for i, frase in enumerate(frases):
        for palavra in word_tokenize(frase.lower()):
            if palavra in frequencia:
                pontuacao[i] = pontuacao.get(i, 0) + frequencia[palavra]
    
    # Pega as top N frases
    melhores_frases = sorted(pontuacao, key=pontuacao.get, reverse=True)[:num_frases]
    resumo = ' '.join(frases[i] for i in sorted(melhores_frases))
    return resumo
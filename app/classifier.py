import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_score, recall_score

# 1. Carregamento dos Dados
try:
    df = pd.read_csv('../noticias.csv')
except FileNotFoundError:
    df = pd.read_csv('noticias.csv') # Fallback para diretório local

titulos = df['titulo'].tolist()
amostra_titulos = titulos[:200]
rotulos = [1 if s == 'Positivo' else 0 for s in df['sentimento'][:200]]

# 2. Configuração do Pipeline Profissional
# Remove o vazamento de dados (Data Leakage) e automatiza a vetorização [cite: 1226, 1253]
stopwords_pt = ['e', 'em', 'de', 'para', 'com', 'que', 'do', 'da', 'no', 'na', 'o', 'a', 'as', 'os']

pipeline_sentimento = Pipeline([
    ('vetorizador', TfidfVectorizer(max_features=1000, stop_words=stopwords_pt, lowercase=True)),
    ('modelo', SVC(kernel='linear', class_weight='balanced', random_state=42))
])

# 3. Divisão e Validação Estatística (K-Fold)
# Garante que as métricas de 0.61 não sejam fruto do acaso [cite: 967, 970]
titulos_train, titulos_test, y_train, y_test = train_test_split(
    amostra_titulos, rotulos, test_size=0.2, random_state=42
)

print("Iniciando Validação Cruzada (5-folds)...")
cv_results = cross_validate(pipeline_sentimento, titulos_train, y_train, cv=5, 
                            scoring=['accuracy', 'precision', 'recall'])

# 4. Treinamento Final e Avaliação [cite: 1255]
pipeline_sentimento.fit(titulos_train, y_train)
y_pred = pipeline_sentimento.predict(titulos_test)

print(f"\nAcurácia Média (CV): {cv_results['test_accuracy'].mean():.2f} (+/- {cv_results['test_accuracy'].std():.2f})")
print("\n--- Relatório Final no Conjunto de Teste ---")
print(f"Acurácia: {accuracy_score(y_test, y_pred):.2f}")
print(f"Precisão: {precision_score(y_test, y_pred):.2f}")
print(f"Recall: {recall_score(y_test, y_pred):.2f}")

# 5. Função de Modo Interativo
def modo_interativo(pipeline):
    print("\n" + "="*40)
    print("🧠 MODO INTERATIVO DE CLASSIFICAÇÃO")
    print("Digite uma notícia para testar o modelo (ou 'sair'):")
    while True:
        entrada = input("\nNotícia > ")
        if entrada.lower() == 'sair':
            break
        # O pipeline vetoriza a string automaticamente antes de prever [cite: 1234]
        predicao = pipeline.predict([entrada])[0]
        sentimento = "✅ POSITIVO" if predicao == 1 else "❌ NEGATIVO"
        print(f"Resultado: {sentimento}")

if __name__ == "__main__":
    modo_interativo(pipeline_sentimento)
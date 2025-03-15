-- Criação da tabela "Noticia"
CREATE TABLE IF NOT EXISTS Noticia (
  id INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(200) NOT NULL,
  conteudo TEXT NOT NULL,
  url VARCHAR(500) NOT NULL UNIQUE,
  data_publicacao DATETIME NOT NULL
);

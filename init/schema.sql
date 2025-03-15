-- Cria o banco de dados com a codificação adequada
CREATE DATABASE IF NOT EXISTS noticias
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Seleciona o banco de dados para uso
USE noticias;

-- Criação da tabela "Noticia"
CREATE TABLE IF NOT EXISTS Noticia (
  id INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(200) NOT NULL,
  conteudo TEXT NOT NULL,
  url VARCHAR(500) NOT NULL UNIQUE,
  data_publicacao DATETIME NOT NULL
);

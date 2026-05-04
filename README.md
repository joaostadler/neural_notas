# 🧠 NeuralNotes — Workspace de Conhecimento (Web)

Plataforma web moderna para gerenciamento de notas, tarefas, diagramas e muito mais. Construído com Flask e SQLAlchemy.

## 🚀 Funcionalidades

- 🔐 **Autenticação segura** — Registro e login com senhas criptografadas
- 📁 **Tópicos hierárquicos** — Árvore de pastas e sub-pastas para organizar conhecimento
- 📝 **Editor de Notas** — Texto livre com tags e etiquetas
- 📓 **Caderno Pautado** — Interface estilo caderno com linhas e margem
- 📐 **Diagrama** — Editor visual com formas e conexões
- 🔬 **Jupyter Notebook** — Células de código e markdown
- 📊 **Kanban** — Quadro de tarefas com colunas arrastáveis
- 📋 **Tarefas Simples** — Gerenciamento rápido de tarefas diárias
- 🔍 **Busca** — Pesquisar em títulos e conteúdo
- 📱 **Responsivo** — Interface adaptável para desktop e mobile

## 📋 Estrutura do Projeto

```
neural_notas/
├── run.py                          # Ponto de entrada
├── config.py                       # Configurações
├── models.py                       # Modelos SQLAlchemy
├── requirements.txt
├── .env.example
├── .gitignore
├── Procfile                        # Deploy Heroku
├── README.md
│
├── app/
│   ├── __init__.py                 # Factory Flask
│   │
│   ├── routes/
│   │   ├── auth.py                 # Login, registro, logout
│   │   └── main.py                 # Dashboard
│   │
│   ├── templates/
│   │   ├── base.html               # Template base
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── main/
│   │   │   └── dashboard.html
│   │   ├── notas/                  # (em desenvolvimento)
│   │   ├── topicos/                # (em desenvolvimento)
│   │   ├── kanban/                 # (em desenvolvimento)
│   │   └── ...
│   │
│   └── static/
│       ├── css/
│       │   └── style.css           # Estilos base
│       ├── js/
│       │   └── main.js             # JavaScript base
│       └── uploads/                # Arquivos de usuários
│
└── instance/                       # Banco de dados (não versionado)
    └── neural_notas.db
```

## 🛠️ Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/neural-notas.git
cd neural_notas
```

### 2. Crie e ative o ambiente virtual

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente
```bash
cp .env.example .env
# Edite .env conforme necessário
```

### 5. Inicie o servidor
```bash
python run.py
```

Acesse em: http://localhost:5000

## 🔐 Credenciais Demo

- **Usuário:** demo
- **Senha:** demo123

Essas credenciais são criadas automaticamente na primeira execução.

## 📊 Banco de Dados

O banco SQLite é criado automaticamente em `instance/neural_notas.db` na primeira execução.

### Tabelas
- `usuarios` — Usuários e autenticação
- `topicos` — Árvore hierárquica de notas
- `notas` — Conteúdo de notas
- `etiquetas` — Tags das notas
- `cadernos` — Cadernos pautados
- `colunas_kanban` — Colunas do kanban
- `cartoes_kanban` — Cartões com tarefas
- `historico_etapas` — Histórico de movimentação
- `diagramas` — Dados de diagramas
- `celulas_jupyter` — Células do notebook
- `pdfs` — Arquivos PDF
- `planilhas` — Dados de planilhas
- `imagens` — Arquivos de imagem
- `tarefas_faceis` — Tarefas simples

## 🌐 Deploy

### Heroku
```bash
heroku create seu-app-name
git push heroku main
heroku open
```

### Outras plataformas
Veja o arquivo `Procfile` para configurações de deploy.

## 📝 Próximos Passos

- [ ] Implementar CRUD de notas
- [ ] Implementar CRUD de tópicos
- [ ] Implementar editor de kanban
- [ ] Implementar editor de diagramas
- [ ] Implementar notebook Jupyter
- [ ] Adicionar busca full-text
- [ ] Adicionar uploads de arquivo
- [ ] Melhorar interface mobile

## 🤝 Contribuindo

Sinta-se livre para abrir issues e fazer pull requests!

## 📄 Licença

MIT License - veja LICENSE para detalhes.

## 👤 Autor

João Stadtler — [@joaostadler](https://github.com/joaostadler)


## Atalhos

| Tecla        | Ação                        |
|--------------|-----------------------------|
| Ctrl+S       | Salvar nota/caderno ativo   |
| Shift+Enter  | Executar célula (Jupyter)   |
| Delete       | Excluir forma selecionada   |
| Botão 3      | Menu de contexto na árvore  |

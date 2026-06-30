# Como Rodar o LinkedIn Scraper

## Pré-requisitos

- Python 3.8+
- Uma conta no LinkedIn

---

## 1. Criar e ativar ambiente virtual

> O Ubuntu/Debian bloqueia instalação global de pacotes pip. Use um virtualenv.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> O prefixo `(.venv)` vai aparecer no terminal confirmando que está ativo.  
> **Sempre ative o venv antes de rodar qualquer comando do projeto.**

## 2. Instalar dependências

```bash
pip install -e .
```

## 3. Instalar o navegador do Playwright

```bash
playwright install chromium
```

---

## 3. Criar a sessão (autenticação)

> O arquivo `linkedin_session.json` é necessário para todos os scripts. Crie-o antes de qualquer coisa.

```bash
python samples/create_session.py
```

O que vai acontecer:
1. Uma janela do navegador vai abrir na página de login do LinkedIn
2. Faça o login manualmente (email, senha, 2FA se necessário)
3. Aguarde o feed do LinkedIn carregar
4. O script detecta o login e salva a sessão em `linkedin_session.json` automaticamente

> **Atenção:** nunca suba o `linkedin_session.json` para o git — ele contém seus cookies de autenticação.

---

## 4. Rodar os exemplos

Todos os scripts abaixo usam o `linkedin_session.json` criado no passo anterior.

### Raspar perfil de pessoa

```bash
python samples/scrape_person.py
```

Raspa o perfil de [William Gates](https://www.linkedin.com/in/williamhgates/) por padrão. Retorna nome, localização, sobre, experiências e educação.

---

### Raspar empresa

```bash
python samples/scrape_company.py
```

Raspa a página da [Microsoft](https://www.linkedin.com/company/microsoft/) por padrão. Retorna nome, setor, tamanho, sede, ano de fundação, site e sobre.

---

### Raspar posts de uma empresa

```bash
python samples/scrape_company_posts.py
```

Retorna os últimos posts da empresa, incluindo texto, data, reações, comentários e reposts.

---

### Buscar vagas

```bash
python samples/scrape_jobs.py
```

Busca vagas de "software engineer" em Toronto por padrão e exibe detalhes das posições encontradas.

---

### Raspar contatos de uma pessoa

```bash
python samples/scrape_person_contacts.py
```

---

### Testar se a sessão está ativa

```bash
python samples/scrape_login.py
```

Verifica se o `linkedin_session.json` ainda está autenticado, testando múltiplas páginas do LinkedIn.

---

## Rodar a API REST (Swagger)

Após ter o `linkedin_session.json`, você pode subir uma API REST completa:

```bash
pip install fastapi "uvicorn[standard]"
uvicorn api:app --reload
```

Acesse o Swagger UI em: **http://localhost:8000/docs**

### Endpoints disponíveis

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/person?url=...` | Raspa perfil de uma pessoa |
| `GET` | `/company?url=...` | Raspa página de uma empresa |
| `GET` | `/company/posts?url=...&limit=10` | Raspa posts de uma empresa |
| `GET` | `/jobs/search?keywords=...&location=...` | Busca vagas |
| `GET` | `/jobs?url=...` | Raspa detalhes de uma vaga |
| `GET` | `/health` | Status da API e da sessão |

### Variável de ambiente (opcional)

Por padrão a API usa `linkedin_session.json` na pasta raiz. Para mudar:

```bash
LINKEDIN_SESSION_FILE=/caminho/para/session.json uvicorn api:app --reload
```

---

## Fluxo resumido

```
1. python3 -m venv .venv
2. source .venv/bin/activate
3. pip install -e .
4. playwright install chromium
5. python samples/create_session.py   ← faz o login e salva a sessão
6. python samples/scrape_person.py    ← scripts de exemplo
   — ou —
   uvicorn api:app --reload           ← API REST com Swagger
```

---

## Solução de problemas

| Problema | Solução |
|---|---|
| `linkedin_session.json` não encontrado | Rode `python samples/create_session.py` primeiro |
| Sessão expirada / erro de autenticação | Rode `create_session.py` novamente para renovar |
| Browser não abre | Verifique se rodou `playwright install chromium` |
| Dependência faltando | Rode `pip install -e .` novamente |
| `externally-managed-environment` | Crie e ative o virtualenv: `python3 -m venv .venv && source .venv/bin/activate` |
| Comando não encontrado após fechar o terminal | Reative o venv: `source .venv/bin/activate` |

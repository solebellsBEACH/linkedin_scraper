"""
LinkedIn Scraper REST API

Run with:
    uvicorn api:app --reload

Swagger UI available at: http://localhost:8000/docs
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from linkedin_scraper import BrowserManager
from linkedin_scraper.scrapers.person import PersonScraper
from linkedin_scraper.scrapers.company import CompanyScraper
from linkedin_scraper.scrapers.company_posts import CompanyPostsScraper
from linkedin_scraper.scrapers.job import JobScraper
from linkedin_scraper.scrapers.job_search import JobSearchScraper
from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    ProfileNotFoundError,
    ScrapingError,
)

SESSION_FILE = os.getenv("LINKEDIN_SESSION_FILE", "linkedin_session.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared browser state
_browser_manager: Optional[BrowserManager] = None
_browser_lock = asyncio.Lock()


async def get_browser() -> BrowserManager:
    global _browser_manager
    async with _browser_lock:
        if _browser_manager is None or not _browser_manager._started:
            _browser_manager = BrowserManager(headless=True)
            await _browser_manager.__aenter__()
            if not os.path.exists(SESSION_FILE):
                raise HTTPException(
                    status_code=503,
                    detail=f"Session file '{SESSION_FILE}' not found. Run 'python samples/create_session.py' first.",
                )
            await _browser_manager.load_session(SESSION_FILE)
            logger.info("Browser started and session loaded.")
    return _browser_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    global _browser_manager
    if _browser_manager is not None:
        try:
            await _browser_manager.__aexit__(None, None, None)
        except Exception:
            pass


app = FastAPI(
    title="LinkedIn Scraper API",
    description=(
        "REST API para extrair dados do LinkedIn usando Playwright.\n\n"
        "**Pré-requisito:** crie o arquivo de sessão antes de usar:\n"
        "```\npython samples/create_session.py\n```"
    ),
    version="3.0.0",
    lifespan=lifespan,
)


# ─── Error handlers ───────────────────────────────────────────────────────────

def handle_scraper_error(e: Exception) -> None:
    if isinstance(e, AuthenticationError):
        raise HTTPException(status_code=401, detail="Sessão expirada. Recrie o linkedin_session.json.")
    if isinstance(e, RateLimitError):
        raise HTTPException(status_code=429, detail=f"Rate limit do LinkedIn. Aguarde {e.suggested_wait_time}s.")
    if isinstance(e, ProfileNotFoundError):
        raise HTTPException(status_code=404, detail="Perfil ou página não encontrado.")
    if isinstance(e, ScrapingError):
        raise HTTPException(status_code=422, detail=f"Erro de scraping: {e}")
    raise HTTPException(status_code=500, detail=str(e))


# ─── Person ───────────────────────────────────────────────────────────────────

@app.get(
    "/person",
    tags=["Pessoa"],
    summary="Raspar perfil de uma pessoa",
    response_description="Dados completos do perfil",
)
async def scrape_person(
    url: str = Query(..., description="URL do perfil LinkedIn (ex: https://linkedin.com/in/username/)", example="https://www.linkedin.com/in/williamhgates/"),
):
    """
    Raspa um perfil de pessoa no LinkedIn.

    Retorna nome, localização, sobre, experiências, educação, interesses,
    conquistas e contatos.
    """
    try:
        browser = await get_browser()
        scraper = PersonScraper(browser.page)
        person = await scraper.scrape(url)
        return person.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        handle_scraper_error(e)


# ─── Company ──────────────────────────────────────────────────────────────────

@app.get(
    "/company",
    tags=["Empresa"],
    summary="Raspar página de uma empresa",
    response_description="Dados completos da empresa",
)
async def scrape_company(
    url: str = Query(..., description="URL da empresa no LinkedIn (ex: https://linkedin.com/company/microsoft/)", example="https://www.linkedin.com/company/microsoft/"),
):
    """
    Raspa a página de uma empresa no LinkedIn.

    Retorna nome, setor, tamanho, sede, site, sobre, especialidades e funcionários.
    """
    try:
        browser = await get_browser()
        scraper = CompanyScraper(browser.page)
        company = await scraper.scrape(url)
        return company.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        handle_scraper_error(e)


@app.get(
    "/company/posts",
    tags=["Empresa"],
    summary="Raspar posts de uma empresa",
    response_description="Lista de posts da empresa",
)
async def scrape_company_posts(
    url: str = Query(..., description="URL da empresa no LinkedIn", example="https://www.linkedin.com/company/microsoft/"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de posts a retornar"),
):
    """
    Raspa os posts mais recentes de uma empresa no LinkedIn.

    Retorna texto, data de publicação, contagens de reações, comentários,
    reposts e URLs de imagens.
    """
    try:
        browser = await get_browser()
        scraper = CompanyPostsScraper(browser.page)
        posts = await scraper.scrape(url, limit=limit)
        return [p.to_dict() for p in posts]
    except HTTPException:
        raise
    except Exception as e:
        handle_scraper_error(e)


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@app.get(
    "/jobs/search",
    tags=["Vagas"],
    summary="Buscar vagas no LinkedIn",
    response_description="Lista de URLs de vagas encontradas",
)
async def search_jobs(
    keywords: Optional[str] = Query(None, description="Palavras-chave da vaga (ex: 'Python Developer')", example="software engineer"),
    location: Optional[str] = Query(None, description="Localização da vaga (ex: 'São Paulo')", example="São Paulo"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados"),
    easy_apply: bool = Query(False, description="Filtrar apenas vagas com Easy Apply"),
    remote: bool = Query(False, description="Filtrar apenas vagas remotas"),
):
    """
    Busca vagas no LinkedIn e retorna as URLs das posições encontradas.

    Use o endpoint `/jobs` para raspar os detalhes de cada vaga.
    """
    try:
        browser = await get_browser()
        scraper = JobSearchScraper(browser.page)
        urls = await scraper.search(keywords=keywords, location=location, limit=limit, easy_apply=easy_apply, remote=remote)
        return {"total": len(urls), "urls": urls}
    except HTTPException:
        raise
    except Exception as e:
        handle_scraper_error(e)


@app.get(
    "/jobs",
    tags=["Vagas"],
    summary="Raspar detalhes de uma vaga",
    response_description="Detalhes completos da vaga",
)
async def scrape_job(
    url: str = Query(..., description="URL da vaga no LinkedIn", example="https://www.linkedin.com/jobs/view/1234567890/"),
):
    """
    Raspa os detalhes de uma vaga no LinkedIn.

    Retorna título, empresa, localização, data de publicação, número de candidatos,
    descrição completa e benefícios.
    """
    try:
        browser = await get_browser()
        scraper = JobScraper(browser.page)
        job = await scraper.scrape(url)
        return job.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        handle_scraper_error(e)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["Status"],
    summary="Verificar status da API",
)
async def health():
    """Verifica se a API está no ar e se a sessão do LinkedIn está configurada."""
    session_ok = os.path.exists(SESSION_FILE)
    return {
        "status": "ok",
        "session_file": SESSION_FILE,
        "session_exists": session_ok,
    }

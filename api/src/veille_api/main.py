"""API de l'interface (SPEC §3.6) : offres, état des sources."""
from fastapi import FastAPI

from veille_api import health, offers

app = FastAPI(title="stagiaire-recruteur")
app.include_router(offers.router)
app.include_router(health.router)

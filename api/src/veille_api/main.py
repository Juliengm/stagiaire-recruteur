"""API de l'interface (SPEC §3.6) : offres, candidatures, état des sources."""
from fastapi import FastAPI

from veille_api import applications, health, offers

app = FastAPI(title="stagiaire-recruteur")
app.include_router(offers.router)
app.include_router(applications.router)
app.include_router(health.router)

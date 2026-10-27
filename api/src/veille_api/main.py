"""API de l'interface (SPEC §3.6) : offres, candidatures, sources et leur état."""
from fastapi import FastAPI

from veille_api import applications, health, manual, offers, runs, sources

app = FastAPI(title="stagiaire-recruteur")
app.include_router(manual.router)  # avant offers : /offers/manual
app.include_router(offers.router)
app.include_router(applications.router)
app.include_router(sources.router)
app.include_router(health.router)
app.include_router(runs.router)

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database.database import Base, engine
from database import models  # noqa: F401
from auth.router import router as auth_router
from organizations.router import router as organizations_router
from services.router import router as services_router
from policies.router import router as policies_router
from knowledge.router import router as knowledge_router
from visitors.router import router as visitors_router
from conversations.router import router as conversations_router
from dashboard.router import router as dashboard_router
from agent.router import router as tools_router
from widget_api import router as widget_router

Base.metadata.create_all(bind=engine)
app=FastAPI(title="EngageAI MVP")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
for router in [auth_router,organizations_router,services_router,policies_router,knowledge_router,visitors_router,conversations_router,dashboard_router,tools_router,widget_router]: app.include_router(router)

# Public assets used by the embeddable chatbot. The owner only needs the
# organization-specific /widget/embed.js URL; that bootstrap script loads
# these assets automatically on the customer website.
WIDGET_DIR = Path(__file__).resolve().parent.parent / "widget"
if WIDGET_DIR.exists():
    app.mount("/widget-assets", StaticFiles(directory=str(WIDGET_DIR)), name="widget-assets")

@app.get("/")
def root(): return {"status":"running","project":"EngageAI MVP"}

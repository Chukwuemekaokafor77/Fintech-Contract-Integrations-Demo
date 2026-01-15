import os

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.models import Base
from app.routes import router


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fintech Contract Integrations Demo")
app.include_router(router)


_ui_dir = os.path.join(os.path.dirname(__file__), "..", "ui")
if os.path.isdir(_ui_dir):
    app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

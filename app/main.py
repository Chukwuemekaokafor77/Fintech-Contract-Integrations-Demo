from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.models import Base
from app.routes import router


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fintech Contract Integrations Demo")
app.include_router(router)


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

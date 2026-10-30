# src/main.py
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from database import init_db
from routers import base, chat

app = FastAPI(title="NewsFoundry API", version="0.1.0")

origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Cette ressource existe déjà."})


app.include_router(base.router)
app.include_router(chat.router)

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
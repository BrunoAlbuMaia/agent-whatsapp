# app/main.py
from fastapi import FastAPI
from src.config import settings
from src.Application import agentRoute


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Registrar Rotas
app.include_router(agentRoute, prefix=settings.API_V1_STR)


import uvicorn

if __name__ == '__main__':
    uvicorn.run(app=app, host="0.0.0.0", port=9005)
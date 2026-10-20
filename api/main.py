from fastapi import FastAPI

from api.routers import sources, spend

app = FastAPI(title="Marketing Fabric API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(spend.router)
app.include_router(sources.router)

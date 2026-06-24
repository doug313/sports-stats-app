from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import search, ai_search, players, mlb_live, retro

app = FastAPI(title="Baseball Stats API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router,     prefix="/api")
app.include_router(ai_search.router,  prefix="/api")
app.include_router(players.router,    prefix="/api")
app.include_router(mlb_live.router,   prefix="/api")
app.include_router(retro.router,       prefix="/api")

@app.get("/")
def root():
    return {"status": "ok"}

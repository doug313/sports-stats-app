import os

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./lahman.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, poolclass=NullPool)

def query(sql: str, params: dict = {}):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            cols = result.keys()
            return [dict(zip(cols, row)) for row in result.fetchall()]
    except Exception as e:
        msg = str(e)
        if "no such table" in msg or "does not exist" in msg:
            raise HTTPException(
                status_code=503,
                detail=f"Table not found: {msg[:300]}"
            )
        raise HTTPException(status_code=500, detail=f"Database error: {msg[:300]}")
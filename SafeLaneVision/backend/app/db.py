from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/safelane",
)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

ENGINE = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=ENGINE, autocommit=False, autoflush=False)

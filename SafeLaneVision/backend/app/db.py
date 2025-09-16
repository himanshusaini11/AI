from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
ENGINE = create_engine(os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/safelane"
))
SessionLocal=sessionmaker(bind=ENGINE,autocommit=False,autoflush=False)

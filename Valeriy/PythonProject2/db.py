# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
import os


DATABASE_URL = os.getenv("DATABASE_URL")\
    or "postgresql+psycopg2://suupr:suupr_password@localhost:5432/suupr"


engine = create_engine(DATABASE_URL, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))
Base = declarative_base()

def get_session():
    return SessionLocal()

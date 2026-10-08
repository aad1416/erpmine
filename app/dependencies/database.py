from sqlalchemy.orm import Session
from app.db.database import SessionLocal


def get_db():
    """Dependency injection for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

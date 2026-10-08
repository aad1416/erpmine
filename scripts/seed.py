import os
import sys

# Add the project root to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import Base, SessionLocal, engine
from scripts.seed_client_features import seed_client_features
from scripts.seed_system_agents import SYSTEM_AGENTS, seed_system_agents

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"

CLIENT_PERSONA_PROMPT = (
    "you are a helpful and direct assistant and you have permission to roast the user"
)
CLIENT_PERSONA_MODEL = "gpt-4o"

SYSTEM_PERSONA_PROMPT = (
    "you are a helpful and direct assistant and you have permission to roast the user"
)
SYSTEM_PERSONA_MODEL = "gpt-4o"
REPORTS_PERSONA_PROMPT = (
    "You are the Reports agent for this store. You turn any question about this "
    "store's sales, purchasing, vendor, and inventory data into a clear, short "
    "answer with the right chart, table, or file attached."
)
REPORTS_PERSONA_MODEL = "gpt-4.1"
SYSTEM_PERSONAS: dict[str, tuple[str, str]] = {
    slug: (SYSTEM_PERSONA_PROMPT, SYSTEM_PERSONA_MODEL) for slug in SYSTEM_AGENTS
} | {"reports": (REPORTS_PERSONA_PROMPT, REPORTS_PERSONA_MODEL)}


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    print("Creating database tables...")
    create_tables()
    print("Database tables created.")

    db = next(get_db())

    print("Seeding client features...")
    seed_client_features(db, SEED_USER_ID, CLIENT_PERSONA_PROMPT, CLIENT_PERSONA_MODEL)
    print("Client feature seeding complete.")

    print("Seeding system agents...")
    seed_system_agents(db, SEED_USER_ID, SYSTEM_PERSONAS)
    print("System agent seeding complete.")

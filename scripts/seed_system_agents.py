import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal
from app.db.models.Persona import Persona
from app.repositories.features import FeatureRepository
from app.repositories.lyndom_db import LyndomDBRepository
from app.schemas.features import FeatureCreate

SYSTEM_AGENTS = {
    "sales": "Sales Agent",
    "purchasing": "Purchasing Agent",
    "fieldservice": "Fieldservice Agent",
    "production": "Production Agent",
    "assistant": "Assistant",
    "reports": "Reports Agent",
}


def seed_system_agents(
    db: Session, seed_user_id: str, personas: dict[str, tuple[str, str]]
):
    lyndom_db_url = os.environ["LYNDOM_DB_URL"]
    lyndom = LyndomDBRepository(lyndom_db_url)
    stores = lyndom.get_stores()
    print(f"Found {len(stores)} stores in Lyndom.")

    feature_repo = FeatureRepository(db)

    seeded = 0
    skipped = 0

    for store in stores:
        store_id = str(store["id"])

        for agent_slug, agent_name in SYSTEM_AGENTS.items():
            if feature_repo.get_by_entity_id_and_store(agent_slug, store_id):
                skipped += 1
                continue

            try:
                persona_prompt, persona_model = personas[agent_slug]
                now = datetime.now()
                persona = Persona(
                    prompt_text=persona_prompt,
                    original_prompt_text=persona_prompt,
                    model_name=persona_model,
                    updated_by_user_id=seed_user_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(persona)
                db.flush()

                feature_request = FeatureCreate(
                    name=agent_name,
                    store_id=store_id,
                    entity_type="system",
                    entity_id=agent_slug,
                )
                feature = feature_repo.create_feature(feature_request)
                feature.persona_id = persona.id
                db.commit()

                print(f"Seeded '{agent_name}' for store '{store['name']}'.")
                seeded += 1
            except IntegrityError:
                db.rollback()
                skipped += 1

    db.close()
    print(f"\nDone. Seeded: {seeded}, Skipped: {skipped}.")

import os
import sys
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal, Base, engine
from app.db.models.Persona import Persona
from app.repositories.features import FeatureRepository
from app.repositories.lyndom_db import LyndomDBRepository
from app.schemas.features import FeatureCreate


def seed_client_features(
    db: Session, seed_user_id: str, persona_prompt: str, persona_model: str
):
    lyndom_db_url = os.environ["LYNDOM_DB_URL"]
    lyndom = LyndomDBRepository(lyndom_db_url)
    clients = lyndom.get_clients()
    print(f"Found {len(clients)} clients in Lyndom.")

    feature_repo = FeatureRepository(db)

    seeded = 0
    skipped = 0

    for client in clients:
        client_id = str(client["id"])

        if feature_repo.get_by_entity_id_and_store(client_id, str(client["store_id"])):
            skipped += 1
            continue

        raw_name = client["name"]
        if not raw_name or str(raw_name).strip().lower() in ("", "undefined", "none"):
            raw_name = client_id
        feature_name = f"{raw_name} agent"

        try:
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
                name=feature_name,
                store_id=str(client["store_id"]),
                entity_type="client",
                entity_id=client_id,
            )
            feature = feature_repo.create_feature(feature_request)
            feature.persona_id = persona.id
            db.commit()

            print(f"Seeded feature + persona for client '{feature_name}'.")
            seeded += 1
        except IntegrityError as e:
            db.rollback()
            skipped += 1

    db.close()
    print(f"\nDone. Seeded: {seeded}, Skipped: {skipped}.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_client_features()

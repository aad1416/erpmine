This is a **clean, modular folder structure** for a FastAPI AI project using:

- **Dependency Injection (DI)**  
- **Alembic** for DB migrations  
- **SQLAlchemy** for ORM
- **Pydantic** for data validation
- **SQLite** as relational database  
- **LangChain** for AI orchestration  
- **ChromaDB** for vector storage  

It is designed to **keep code maintainable, testable, and scalable** by separating concerns.

---

## Folder Structure

```text
ut-ai/
│
├─ app/
│   ├─ main.py             # FastAPI app entrypoint
│   ├─ routes/             # API endpoints (features, chats, documents, classrooms, etc.)
│   │   └─ classrooms.py   # Classroom admin endpoints
│   ├─ services/           # AI orchestration, business logic
│   │   ├─ classroom_service.py  # Classroom management
│   │   └─ ...
│   ├─ repositories/       # DB operations (one per model)
│   │   ├─ classrooms.py
│   │   ├─ classroom_items.py
│   │   ├─ classroom_item_documents.py
│   │   └─ ...
│   ├─ db/
│   │   ├─ models/         # SQLAlchemy models (Feature, Classroom, ClassroomItem, etc.)
│   │   ├─ database.py     # DB client / connection
│   │   └─ migrations/     # Alembic migrations
│   ├─ schemas/            # Request/Response schemas (Pydantic models)
│   ├─ prompts/            # LLM prompt templates
│   │   ├─ __init__.py
│   │   └─ admin_chat.py   # Admin chat prompts
│   ├─ vector_db/          # ChromaDB wrapper
│   │   └─ chroma_client.py
│   ├─ dependencies/       # DI / dependency providers
│   ├─ utils/              # All utils goes here
│   └─ config/             # settings / environment variables
│       └─ settings.py
│
├─ storage/                # All persistent data (DB files, vector stores, etc.)
│   ├─ vector_store/       # ChromaDB persistent storage
│   └─ main.db             # SQLite database
│
├─ tests/                  # unit/integration tests
│   └─ test_agent.py
├─ scripts/                # utility scripts, e.g., data migrations
└─ requirements.txt
```



## Key points to keep it clean

- **Separation of concerns:**  
  - `services` → AI logic / LangChain orchestration  
  - `repositories` → DB / Chroma operations  
  - `routes` → API endpoints only  
  - `prompts` → LLM prompt templates (separate from business logic)

- **Request/Response Types:**  
  All Pydantic schemas for request/response validation go in `schemas/`.

- **Prompt Templates:**  
  All LLM prompts go in `prompts/`, organized by feature (e.g., `admin_chat.py`, `rag.py`). This keeps prompts maintainable, testable, and version-controlled separately from service logic.

- **Persistent Data Storage:**  
  Keep all persistent data (database files, vector stores, etc.) under the root-level `storage/` directory.

- **Dependency Injection (DI):**  
  Centralize shared resources in `dependencies/`.

- **Database & Migrations:**  
  Keep SQLAlchemy models and Alembic migrations inside `db/`.

- **Vector Database:**  
  Keep ChromaDB wrappers in `vector_db/`.

- **Configuration:**  
  Use `config/` for settings and environment variables.

- **Tests:**  
  Mirror the structure of `app/` for clarity and coverage.

- **General Tips:**  
  Keep modules small, readable, and modular for maintainability.

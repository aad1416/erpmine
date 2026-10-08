# AI Agent Development Plan

## Overview
Building an AI agent with:
- **Short-term memory**: Chat-based memory
- **Features**: Each feature has a persona and its own documents
- **Personas**: Configurable prompts with model selection (GPT-3, Gemini, etc.)
- **Document management**: Documents assigned to features, stored in separate vector DB collections per feature
- **Complex workflows**: Answer based on documents using RAG
- **Voice chat**: Speech-to-text input, process through RAG, return text response

---

## Phase 1: Core Data Models & Database Setup

### 1.1 Chat Models
- [x] Create `Chat` model (id, user_id, feature_id, title, created_at, updated_at)
- [x] Create `Message` model (id, chat_id, role, content, created_at)
- [x] Create Alembic migration for Chat and Message tables
- [x] Add relationships: User -> Chats -> Messages, Feature -> Chats
- [x] Note: Each chat belongs to a feature and uses that feature's persona and documents

### 1.2 User Model Enhancement
- [x] Add `user_type` field to `User` model (enum or string: 'admin', 'user', etc., default: 'user')
- [x] Create Alembic migration to add user_type column
- [x] Update user creation logic to support different user types

### 1.3 Feature Model
- [x] Create `Feature` model (id, created_at, updated_at, ...)
- [x] Create Alembic migration for Feature table
- [x] Add relationship: Feature -> Persona (one-to-one)
- [x] Create Alembic data migration to seed initial features
- [x] Note: Features are managed via admin-only CRUD endpoints (`/admin/features`)
- [x] Note: Initial features can also be seeded via Alembic migrations

### 1.4 Persona Model (Replaces SystemPrompt)
- [x] Create `Persona` model (id, feature_id (unique), prompt_text, original_prompt_text, model_name, updated_by_user_id, created_at, updated_at)
- [x] Create Alembic migration for Persona table
- [x] Add relationship: User -> Persona (updated_by)
- [x] Add relationship: Persona -> Feature (one-to-one, unique feature_id)
- [x] Enforce unique constraint on feature_id (one persona per feature)
- [ ] Create Alembic data migration to seed initial personas (one per feature)
- [x] Store original prompt text on initial creation (original_prompt_text = prompt_text on first create)
- [x] Note: model_name specifies which LLM to use (e.g., 'gpt-3.5-turbo', 'gemini-pro', etc.)
- [ ] Note: No create/delete endpoints - only update and read available to client
- [ ] Note: Initial personas should be created via Alembic migrations (one persona per feature)

### 1.5 File Storage Models
- [x] Create `File` model (id, file_name, path, extension, size, mime_type, user_id, created_at, updated_at)
- [x] Create Alembic migration for File table
- [x] Add relationships: User -> Files, File -> Document (one-to-one)
- [x] Note: Files store physical file metadata and location on disk
- [x] Note: Files can exist independently before being processed into documents

### 1.6 Document Storage Models
- [x] Create `Document` model (id, feature_id nullable, file_id, metadata) — `feature_id` is NULL for classroom-uploaded documents
- [x] Create Alembic migration for Document table
- [x] Add relationships: Feature -> Documents, File -> Document (one-to-one)
- [x] Note: Only admins can manage documents (CRUD operations), but documents are available for all users' queries through chat
- [x] Note: Feature documents are stored in ChromaDB collection `feature_{feature_id}`; classroom documents are stored in `classroom_{classroom_id}`
- [x] Note: Metadata is stored in ChromaDB chunks, not in the Document model
- [x] Note: Each Document must have an associated File via `file_id` foreign key

### 1.7 Repository Layer
- [x] Create `chat_repository.py` (CRUD for chats)
- [x] Create `message_repository.py` (CRUD for messages)
- [x] Create `feature_repository.py` (read operations for features)
- [x] Create `persona_repository.py` (read and update operations for personas)
- [x] Create `document_repository.py` (CRUD for documents)
- [x] Create `files_repository.py` (CRUD for files)

---

## Phase 2: Vector Database Setup

### 2.1 ChromaDB Client Wrapper
- [x] Create `app/vector_db/chroma_client.py`
- [x] Implement ChromaDB connection and collection management
- [x] Implement collection per feature (collection name = feature_id)
- [x] Store ChromaDB data in `storage/vector_store/`
- [x] Note: Each feature has its own collection, documents are stored in their feature's collection

### 2.2 Embedding Service
- [x] Create `app/services/embedding_service.py`
- [x] Integrate embedding model (OpenAI, HuggingFace, or local)
- [x] Add configuration for embedding model selection
- [x] Implement batch embedding for documents

### 2.3 Vector Storage Operations
- [x] Document Service receives ChromaDB Collection directly (no Vector Repository abstraction)
- [x] Document Service uses `collection.add()` to store chunks with metadata
- [x] EmbeddingService generates embeddings; ChromaDB stores vectors and metadata
- [x] Store chunks with metadata: document_id, chunk_index, filename, and custom metadata (all metadata stored in ChromaDB)
- [x] Implement similarity search functionality within feature collections (for RAG service)
- [x] Add metadata filtering (document_id, feature_id, custom metadata fields) for retrieving chunks
- [x] Note: All chunk data (content, embeddings, metadata) is managed by ChromaDB, not relational DB
- [x] Note: Search is scoped to feature collection - query documents from specific feature's collection
- [x] Note: Document metadata is stored only in ChromaDB chunks, not in the Document relational model
- [x] Note: Vector Repository may still exist for RAG service, but Document Service uses Collection directly

---

## Phase 3: Memory Management

### 3.1 Short-Term Memory (Chat Memory)
- [x] Create `app/services/memory_service.py`
- [x] Implement chat-based message history retrieval
- [ ] Add conversation context window management
- [ ] Implement message summarization for long conversations (optional)
- [ ] Create schema for chat request/response

### 3.2 Long-Term Memory (Personas)
- [x] Create `app/services/persona_service.py`
- [x] Implement persona retrieval by feature (get persona for a specific feature)
- [x] Implement persona update (admin-only, updates existing persona)
- [x] Implement reset to original prompt functionality (restore prompt_text from original_prompt_text)
- [x] Implement LLM client selection based on persona.model_name
- [x] Create admin dependency: `get_admin_user` (checks user_type == 'admin')
- [x] Create API endpoints for persona management:
  - [x] PUT `/admin/features/{feature_id}/personas` - Update persona for feature (admin only)
  - [x] POST `/admin/features/{feature_id}/personas/reset` - Reset persona prompt to original (admin only)

### 3.3 Features API (Admin-Only)
- [x] Create `app/routes/features.py`
- [x] Implement GET `/admin/features` - List all features (admin only)
- [x] Implement GET `/admin/features/{feature_id}` - Get a feature by ID (admin only)
- [x] Implement POST `/admin/features` - Create a new feature (admin only, 409 on duplicate name)
- [x] Implement PUT `/admin/features/{feature_id}` - Update a feature name (admin only, 409 on name collision)
- [x] Implement DELETE `/admin/features/{feature_id}` - Delete a feature (admin only, 204 on success)
- [x] Add `FeatureUpdate` schema to `app/schemas/features.py`
- [x] Add `update_feature` and `delete_feature` methods to `FeatureRepository`
- [x] Add `update_feature` and `delete_feature` methods to `FeatureService`

---

## Phase 4: File & Document Management (Two-Step Process)

### 4.1 File Upload Service
- [x] Create `app/services/files.py` (File Service)
- [x] Implement file upload and storage on disk
- [x] Store file metadata in File model (file_name, path, extension, size, mime_type, user_id)
- [x] Generate unique id for each uploaded file
- [x] Store files in `storage/` directory (configurable path)
- [x] Create file schemas (request/response)

### 4.2 File Upload API
- [x] Create `app/routes/files.py`
- [x] Implement POST `/files/upload` endpoint (available to authenticated users)
  - [x] Accept multiple file uploads (multipart/form-data)
  - [x] Validate each file individually (type, size limits)
  - [x] Process all files and return list of successfully uploaded files
  - [x] Handle partial success (some files may fail validation while others succeed)
  - [x] Return list of file details (FileResponse objects) for successful uploads
- [x] Implement GET `/files` endpoint - List all files uploaded by current user
- [x] Implement GET `/files/{file_id}` endpoint - Get file details
- [x] Implement GET `/files/{file_id}/download` endpoint - Download file (available to authenticated users, owner only)

### 4.3 Document Processing Service
- [x] Create `app/services/document_service.py`
- [x] Document Service receives ChromaDB Collection directly (no Vector Repository)
- [x] Document Service receives File Service dependency
- [x] Implement `add_documents(file_ids[], metadata)` method
- [x] For each file_id: retrieve File, parse document, chunk text
- [x] Store chunks directly in ChromaDB collection using `collection.add()`
- [x] EmbeddingService generates embeddings during ingestion
- [x] Create Document records linking to Files via `file_id`
- [x] Store chunks with metadata: document_id, chunk_index, filename, and custom metadata (all metadata stored in ChromaDB)
- [x] Note: Chunks are stored only in vector DB, not in relational DB
- [x] Note: Each feature's documents are stored in separate ChromaDB collections (collection name = feature_id)
- [x] Note: Document metadata is stored only in ChromaDB chunks, not in the Document relational model
- [x] Note: Two-step process: 1) Upload file, 2) Process file into document

### 4.4 Document Processing API (Admin-Only)
- [x] Create `app/routes/documents.py`
- [x] Implement POST `/admin/features/{feature_id}/documents/process` endpoint (admin only)
- [x] Accept file_ids[] array and optional metadata object (JSON)
- [x] Use admin dependency: `get_admin_user` for authorization
- [x] Validate feature_id exists (from URL path)
- [x] Call Document Service `add_documents()` method
- [x] Create document schemas (request/response)

### 4.3 Document Management API (Admin-Only)
- [x] GET `/admin/features/{feature_id}/documents` - List documents for a specific feature with file details (admin only). Returns documents with associated file information including file name, size, mime type, extension, and upload timestamps.
- [x] GET `/admin/features/{feature_id}/documents/{id}` - Get document details (admin only)
- [x] PUT `/admin/features/{feature_id}/documents/{id}/metadata` - Update document metadata in ChromaDB chunks (admin only)
- [x] DELETE `/admin/features/{feature_id}/documents?document_ids=id1&document_ids=id2` - Delete one or more documents from DB and all their chunks from ChromaDB collection (admin only)
- [x] POST `/admin/features/{feature_id}/documents/{id}/process` - process document (chunk and embed) (admin only)

---

## Phase 5: AI Agent Core

### 5.1 Chat Service (Orchestration Layer)
- [x] Create `app/services/chat_service.py`
- [x] Implement dependency injection for:
  - [x] MemoryService (chat history)
  - [x] PersonaService (persona retrieval)
  - [x] RAGService (data retrieval only)
  - [x] AgentService (LLM construction & generation)
- [x] Implement `process_message(chat_id, message, feature_id)` orchestration:
  - [x] Retrieve chat history from MemoryService
  - [x] Retrieve persona from PersonaService
  - [x] Retrieve raw data from RAGService (JSON/markdown format)
  - [x] Build prompt combining: chat history + RAG data + user query (NO persona prompt)
  - [x] Pass prompt + persona to AgentService for generation
  - [x] Save messages using MemoryService
  - [x] Return response
- [ ] Add streaming response support (optional)
- [x] Note: ChatService is the orchestration layer that coordinates all services

### 5.1a Admin Chat Service (Multi-Agent Orchestration)
- [x] Create `app/services/admin_chat_service.py`
- [x] Implement dependency injection for:
  - [x] MemoryService (chat history)
  - [x] PersonaService (persona retrieval and update)
  - [x] RAGService (data retrieval)
  - [x] AgentService (LLM construction & generation)
- [x] Implement `process_admin_message(chat_id, message, feature_id, user_id)` orchestration with 3 LLM calls:
  - [x] **Call 1 - Intent Detection** (GPT-3.5-turbo for speed):
    - [x] Input: User query
    - [x] Prompt: "Detect user intent and return JSON with {behavior_change: bool, rag_data: bool}"
    - [x] Output: JSON with intent flags
    - [x] Handle all combinations: (true, false), (false, true), (true, true), (false, false)
  - [x] **Call 2 - Persona Update** (conditional, only if behavior_change=true):
    - [x] Input: Current persona prompt + user request
    - [x] Prompt: "Update persona of an agent according to user needs. Current persona: {persona.prompt_text}"
    - [x] Output: New persona prompt text
    - [x] Auto-save to database (update Persona model)
    - [x] Track updated_by_user_id = admin user ID
  - [x] **Call 3 - Response Synthesis**:
    - [x] Input: Intent result + updated prompt (if any) + RAG data (if any)
    - [x] Prompt: "Synthesize response: inform about persona updates and/or provide data answer"
    - [x] If both flags false: return helpful message explaining no action taken
    - [x] Output: Natural language response
  - [x] Save user message and assistant response
  - [x] Return response with metadata
- [x] Response metadata includes:
  - [x] Intent detection result (behavior_change, rag_data flags)
  - [x] Persona update details (old prompt, new prompt) if updated
  - [x] RAG sources if data retrieved
  - [x] Final synthesized response
- [x] Note: Uses existing chat_id, maintains conversation history like regular chats
- [x] Note: Admin-only access (requires user_type='admin')

### 5.2 Agent Service (LLM Client Factory)
- [x] Create `app/services/agent_service.py`
- [x] Set up LLM client factory (supports multiple providers: OpenAI, Anthropic, Gemini, etc.)
- [x] Implement LLM client selection based on persona.model_name
- [x] Implement `generate(prompt, persona)` method:
  - [x] Apply persona prompt internally (as system message or LLM config)
  - [x] Construct LLM client (e.g., `ChatOpenAI` from `langchain_openai`)
  - [x] Generate response using LangChain
  - [x] Return response
- [x] Note: Agent service handles persona prompt and LLM construction only (no orchestration)

### 5.3 Chat API Routes
- [x] Create `app/routes/chats.py`
- [x] Create chat API endpoints:
  - [x] POST `/features/{feature_id}/chats` - Create new chat
  - [x] GET `/features/{feature_id}/chats` - List user's chats for a feature
  - [x] GET `/features/{feature_id}/chats/{id}` - Get chat with messages
  - [x] POST `/features/{feature_id}/chats/{id}/messages` - Send message to chat (delegates to ChatService)
  - [x] DELETE `/features/{feature_id}/chats/{id}` - Delete chat
  - [x] PUT `/features/{feature_id}/chats/{id}` - Update chat title (bonus)
- [x] Note: Routes delegate to ChatService for message processing

### 5.3a Admin Chat API Route
- [x] Add admin chat endpoint to `app/routes/admin_chat.py`:
  - [x] POST `/admin/features/{feature_id}/chats/{id}/admin-message` - Send admin message (admin only)
    - [x] Requires admin authentication (get_admin_user dependency)
    - [x] Receives chat_id from URL path
    - [x] Validates feature_id exists
    - [x] Validates chat exists (can be any user's chat - admin has access to all)
    - [x] Delegates to AdminChatService for processing
    - [x] Returns response with full metadata (intent, persona updates, RAG sources, synthesized response)
- [x] Note: Admin chat endpoint delegates to AdminChatService for multi-agent orchestration

### 5.4 Response Schemas
- [x] Create chat and message schemas
- [ ] Add streaming response schema (if implemented)
- [x] Add admin chat schemas:
  - [x] `AdminMessageRequest` - Request schema with message field
  - [x] `IntentDetectionResult` - Schema for intent detection (behavior_change, rag_data flags)
  - [x] `PersonaUpdateResult` - Schema for persona update (old_prompt, new_prompt, updated)
  - [x] `AdminMessageResponse` - Response schema with metadata:
    - [x] intent: IntentDetectionResult
    - [x] persona_update: PersonaUpdateResult (optional)
    - [x] sources: List[MessageSource] (optional)
    - [x] response: str (synthesized response)
    - [x] user_message_id: int
    - [x] assistant_message_id: int
    - [x] chat_id: int

---

## Phase 6: Advanced Workflows

### 6.1 Document-Based Q&A (RAG Integration)
- [x] Create `app/services/rag_service.py` (Retrieval Augmented Generation)
- [x] Implement `retrieve(query, feature_id)` method for data retrieval ONLY:
  - [x] Queries `feature_{feature_id}` collection (direct feature document uploads)
  - [x] Queries all `classroom_{id}` collections for classrooms assigned to the feature via the `collections` table
  - [x] Merges results from all collections and re-ranks globally by relevance score before returning top-k
  - [ ] Combine contexts from multiple sources (documents, code, database) - currently documents only
  - [x] Return raw data in JSON/markdown format (NO generation)
- [x] Add document source references in retrieved data
- [x] Integrate RAG service into `ChatService` - all chat messages use RAG to retrieve data from feature's documents and assigned classroom documents
- [x] Note: RAG service only does retrieval, ChatService handles prompt building, AgentService handles generation
- [x] Note: RAG queries are scoped to the feature's own collection plus any assigned classroom collections
- [x] Note: No separate endpoint needed - RAG is integrated into `POST /features/{feature_id}/chats/{id}/messages` via ChatService

### 6.2 Codebase Analysis Workflow
- [ ] Create `app/services/codebase_service.py`
- [ ] Implement code file indexing (optional feature)
- [ ] Add code-specific chunking strategy
- [ ] Create codebase search and retrieval
- [ ] Integrate with agent for code-related queries

### 6.3 Database Query Workflow
- [ ] Create `app/services/db_query_service.py`
- [ ] Implement SQL query generation from natural language
- [ ] Add database schema introspection
- [ ] Create safe query execution (read-only or with validation)
- [ ] Integrate with agent for database queries

---

## Phase 7: Voice Chat

### 7.1 Speech-to-Text (STT) Service
- [x] Create `app/services/stt_service.py`
- [x] create a function named transcribe accepts a file and returns string which supports stream
- [x] Integrate STT provider (OpenAI Whisper, Google Speech-to-Text)
- [x] Add audio file validation (format, size, duration limits)
- [x] Implement audio format conversion if needed (support common formats: WAV, MP3, M4A, OGG)
- [x] Accept STT provider in constructor default it by OpenAI TTS

### 7.2 Voice Chat API
- [x] Create `app/routes/voice.py`
- [x] Implement POST `/features/{feature_id}/chats/{id}/voice-message` endpoint (available to all authenticated users)
- [x] Accept audio file upload and boolean speech_output (multipart/form-data) 
- [x] Process flow:
  - [x] Receive audio file from client
  - [x] Convert speech to text using SpeechService (STT)
  - [x] Delegate to ChatService for processing (same as text chat flow)
  - [x] If speech_output=true answer with message + voice if not just message/string
- [x] Add audio file size and duration limits
- [x] Create voice message schemas (request/response)
- [x] Note: Voice chat uses the same ChatService flow as text chat, with STT/TTS layers before/after

### 7.3 Optional: Text-to-Speech (TTS)
- [x] Create file in `app/services/tts_service.py`
- [x] Create a function named Synthesize accepts a string and returns audio which supports stream 
- [x] Integrate TTS provider (OpenAI TTS, Google TTS)


---

## Phase 7.5: Document Active Status & Classrooms

### 7.5.1 Document Active Status (Refactoring)
- [x] Add `active` to `RESERVED_KEYS` in DocumentService to prevent user override
- [x] Inject `active: "true"` metadata on all new document chunks in `_build_base_metadata`
- [x] Preserve `active` status when reprocessing documents (`reprocess_document`)
- [x] Add `where={"active": "true"}` filter to RAG retrieval in `rag_service.py`
- [x] Enrich document responses with `active` status from ChromaDB (service layer)
- [x] Add `active: Optional[bool]` field to `DocumentResponse` and `DocumentWithFileResponse` schemas
- [x] Add `activate_document` and `deactivate_document` methods to DocumentService

### 7.5.2 Classroom Data Models
- [x] Create `Classroom` model (id, name, timestamps) — standalone, no feature FK
- [x] Create `ClassroomItem` model (id, classroom_id FK, inventory_item_id unique, timestamps)
- [x] Create `ClassroomItemDocument` model (id, item_id FK, document_id FK, inventory_item_document_id unique, timestamps)
- [x] Create `FeatureClassroom` model (id, feature_id FK, classroom_id FK, created_at) — `collections` table, many-to-many
- [x] Remove `feature_id` from `Classroom` model (dropped unique FK constraint)
- [x] Remove `classroom` one-to-one relationship from `Feature` model; add `classroom_assignments` many-to-many relationship
- [x] Make `Document.feature_id` nullable (classroom documents have `feature_id = NULL`)
- [x] Alembic migration: create `collections` table, drop `classrooms.feature_id`, alter `documents.feature_id` nullable

### 7.5.3 Classroom Repositories
- [x] Create `ClassroomRepository` (CRUD — `get_by_feature_id` removed)
- [x] Create `ClassroomItemRepository` (CRUD + `get_by_inventory_item_id`)
- [x] Create `ClassroomItemDocumentRepository` (CRUD + `get_by_inventory_item_document_id`)
- [x] Create `FeatureClassroomRepository` (`assign`, `unassign`, `get_classrooms_for_feature`, `get_assignments_for_feature`)

### 7.5.4 Classroom Service
- [x] Create `ClassroomService` with factory-based `DocumentService` injection (keyed by `classroom_id`, not `feature_id`)
- [x] Implement `create_classroom(name)` — standalone, no feature creation side-effect
- [x] Implement `create_items` (batch item + document creation; documents go to `classroom_{id}` ChromaDB collection)
- [x] Implement `upload_document` (single item document upload)
- [x] Implement `toggle_document_activation` (activate/deactivate via ChromaDB)
- [x] Implement `delete_document` (removes from ChromaDB + files + SQL)
- [x] Implement `download_document` (returns file for streaming)
- [x] `_resolve_classroom_id`: traverses `item_doc → item → classroom_id` (replaces old `_resolve_feature_id`)

### 7.5.5 Classroom API Routes (Admin-Only)
- [x] GET `/admin/classrooms` - List all classrooms (feature_id filter removed; use feature endpoint instead)
- [x] POST `/admin/classrooms` - Create standalone classroom (no feature binding)
- [x] POST `/admin/classrooms/{classroom_id}/items` - Batch create items with documents
- [x] POST `/admin/classroom-items/{inventory_item_id}/documents` - Upload document for item
- [x] PATCH `/admin/classroom-documents/{id}/activation` - Toggle document active status
- [x] DELETE `/admin/classroom-documents/{id}` - Delete document
- [x] GET `/admin/classroom-documents/{id}/download` - Download document file

### 7.5.6 Feature-Classroom Assignment Routes (Admin-Only)
- [x] GET `/admin/features/{feature_id}/classrooms` - List classrooms assigned to feature
- [x] POST `/admin/features/{feature_id}/classrooms` - Assign a classroom to a feature (409 if already assigned)
- [x] DELETE `/admin/features/{feature_id}/classrooms/{classroom_id}` - Remove classroom assignment

### 7.5.7 Classroom ↔ ClassroomItem Many-to-Many
- [x] Convert `Classroom` ↔ `ClassroomItem` from 1:N to M:N
- [x] New join model `ClassroomItemAssignment` (`classroom_item_assignments` table; unique `(classroom_id, item_id)`)
- [x] Drop `classroom_items.classroom_id` column; replace `Classroom.items` with `Classroom.item_assignments`; add `ClassroomItem.classroom_assignments`
- [x] Alembic migration `d4e5f6a7b8c9_classroom_item_m2m.py` creates the join table, backfills from `classroom_items.classroom_id`, then drops the column (SQLite table rebuild + non-SQLite DDL paths)
- [x] New `ClassroomItemAssignmentRepository` (`assign`, `unassign`, `get_assignment`, `get_items_for_classroom`, `get_classrooms_for_item`)
- [x] ChromaDB collections move from per-classroom to per-item: `item_{ClassroomItem.id}` (internal UUID). Existing `classroom_{id}` collections are a fresh break — not migrated
- [x] `app/dependencies/vector_store.py`: replace `get_classroom_collection` with `get_item_collection(item_id)`
- [x] `ClassroomService`:
  - [x] `create_items(items)` — batch items-only (no docs, no classroom)
  - [x] `create_items_with_documents(items)` — batch items + per-item document upload (no classroom)
  - [x] `list_items()` — list every standalone item
  - [x] `list_classroom_items(classroom_id)` — now goes through the join table
  - [x] `assign_item_to_classroom(classroom_id, item_id)` / `unassign_item_from_classroom(classroom_id, item_id)` (409 on duplicate assign)
  - [x] All document methods (`upload_document`, `toggle_document_activation`, `delete_document`, `download_document`) resolve the per-item collection via `item_doc.item_id` (no more classroom resolution)
- [x] Classroom/item routes:
  - [x] Remove `POST /admin/classrooms/{classroom_id}/items` (old batched create)
  - [x] `GET /admin/classroom-items` — list all items
  - [x] `POST /admin/classroom-items` — batch create (items-only)
  - [x] `POST /admin/classroom-items/with-documents` — batch create items + docs (no classroom dependency)
  - [x] `POST /admin/classrooms/{classroom_id}/items/{item_id}` — assign item to classroom (409 on duplicate)
  - [x] `DELETE /admin/classrooms/{classroom_id}/items/{item_id}` — unassign
  - [x] `GET /admin/classrooms/{classroom_id}/items` — still lists items in a classroom, now via the join table
- [x] `RAGService.retrieve` walks feature → classrooms → items and queries each `item_{id}` collection in addition to `feature_{feature_id}`, deduplicating item IDs before issuing vector queries

---

## Phase 8: Configuration & Environment

### 8.1 Settings Enhancement
- [ ] Add LLM provider configuration (OpenAI, Anthropic, etc.)
- [ ] Add API keys management
- [ ] Add embedding model configuration
- [ ] Add vector DB configuration
- [ ] Add file upload limits and allowed types
- [ ] Add STT/TTS provider configuration

### 8.2 Environment Variables
- [ ] Document required environment variables
- [ ] Add `.env.example` file
- [ ] Update settings to load from environment

---

## Phase 9: Testing & Documentation

### 9.1 Unit Tests
- [ ] Test repositories
- [ ] Test services
- [ ] Test vector DB operations
- [ ] Test memory management
- [ ] Test STT/TTS services

### 9.2 Integration Tests
- [ ] Test document upload and processing
- [ ] Test chat flow with memory
- [ ] Test RAG workflows
- [ ] Test API endpoints
- [ ] Test voice chat flow (audio -> text -> RAG -> response)

### 9.3 Documentation
- [ ] Update README with setup instructions
- [ ] Document API endpoints
- [ ] Add code comments and docstrings
- [ ] Create architecture diagram (optional)

---

## Technical Decisions

### LangChain for Workflow Orchestration
- **LangChain**: 
  - ✅ Mature ecosystem, extensive tooling
  - ✅ Good documentation and community
  - ✅ Built-in memory, chains, agents
  - ✅ Already in project dependencies
  - ❌ Can be heavy/complex for simple use cases

**Decision**: Using **LangChain** for Phase 5-6 workflow orchestration, as it's already in dependencies and provides immediate value with comprehensive tooling.

### Embedding Model Options
- OpenAI `text-embedding-3-small` or `text-embedding-3-large` (cloud, paid)
- HuggingFace models (local, free) - e.g., `sentence-transformers/all-MiniLM-L6-v2`
- **Recommendation**: Start with OpenAI for simplicity, add local option later

### LLM Provider Options
- OpenAI GPT-4/GPT-3.5
- Anthropic Claude
- Local models (Ollama, etc.)
- **Recommendation**: Make it configurable, start with OpenAI

### Speech-to-Text (STT) Options
- OpenAI Whisper API (cloud, paid, high accuracy)
- OpenAI Whisper (local, free, requires model download)
- Google Speech-to-Text (cloud, paid)
- **Recommendation**: Start with OpenAI Whisper API for simplicity, add local option later

### Text-to-Speech (TTS) Options (Optional)
- OpenAI TTS API (cloud, paid, natural voices)
- Google Cloud Text-to-Speech (cloud, paid)
- Local TTS models (e.g., Coqui TTS, Piper)
- **Recommendation**: Start with OpenAI TTS if implementing TTS feature

---

## Priority Order

1. **Phase 1** - Foundation (models, DB)
2. **Phase 2** - Vector DB setup
3. **Phase 3** - Memory management
4. **Phase 4** - Document management
5. **Phase 5** - Basic AI agent
6. **Phase 6** - Advanced workflows
7. **Phase 7** - Voice chat
8. **Phase 8** - Configuration
9. **Phase 9** - Testing & docs

---

## Notes

- **ChatService Orchestration**: ChatService is the orchestration layer that coordinates MemoryService, PersonaService, RAGService, and AgentService. All message processing flows through ChatService.
- **Feature Management**: Features are managed via admin-only CRUD endpoints. All feature routes require `user_type == 'admin'`. Duplicate names return a 409 Conflict response.
- **AdminChatService Orchestration**: AdminChatService uses multi-agent orchestration with 3 sequential LLM calls:
  1. **Intent Detection** (GPT-3.5-turbo): Detects if user wants behavior change and/or data retrieval
  2. **Persona Update** (conditional): Generates new persona prompt if behavior change requested, auto-saves to database
  3. **Response Synthesis**: Combines all results into natural language response with metadata
- **Admin Chat vs Regular Chat**:
  - **Regular Chat**: Single LLM call with persona, used by all users for Q&A
  - **Admin Chat**: 3 LLM calls with intent routing, admin-only, can modify persona dynamically
  - **Both**: Share same chat history (use same chat_id), maintain conversation context
- **Service Responsibilities**:
  - **ChatService**: Orchestrates the entire chat flow, builds prompts (history + RAG data + query)
  - **AdminChatService**: Orchestrates admin chat with 3-step multi-agent flow, handles persona updates
  - **RAGService**: Only does retrieval, returns raw data in JSON/markdown format (NO generation)
  - **AgentService**: Handles persona prompt internally, constructs LLM client, generates responses
  - **MemoryService**: Manages chat history retrieval and storage
  - **PersonaService**: Retrieves persona configuration and handles updates
- **Prompt Building**: ChatService builds prompts WITHOUT persona prompt. AgentService applies persona prompt internally when constructing the LLM.
- **Intent Detection Logic**: Admin chat always detects intent first, handles all 4 combinations:
  - `{behavior_change: true, rag_data: false}` - Update persona only
  - `{behavior_change: false, rag_data: true}` - Retrieve data only
  - `{behavior_change: true, rag_data: true}` - Update persona AND retrieve data
  - `{behavior_change: false, rag_data: false}` - General chat, no special action
- **Persona Update Flow**: When behavior_change=true, AdminChatService generates new persona prompt using LLM, auto-saves to database, tracks updated_by_user_id
- **Voice Chat Flow**: Voice chat uses the same ChatService flow with STT (speech-to-text) before and TTS (text-to-speech) after.
- **File-Document Separation**: Files and Documents are separate entities. Files represent uploaded physical files, while Documents represent processed files with embeddings in ChromaDB. This allows files to be uploaded first and processed later.
- **Two-Step Upload Process**: Clients must first upload files (via File Service), then process them into documents (via Document Service). This separation allows for better error handling and retry logic.
- **Direct Vector DB Access**: Document Service receives ChromaDB Collection directly via dependency injection, eliminating the Vector Repository abstraction layer for document operations. EmbeddingService generates embeddings; ChromaDB stores vectors and serves similarity search.
- **File Model**: Stores physical file metadata (path, size, mime_type, etc.) and maintains relationship with User. Files can exist without being processed into documents.
- **Document Model**: Represents processed documents linked to Files via `file_id`. Document chunks and embeddings are stored in ChromaDB, not the relational database.
- Keep existing auth system intact
- Follow the folder structure in `docs/folder-structure.md`
- Use dependency injection pattern consistently
- Store all persistent data in `storage/` directory
- Consider rate limiting for API endpoints
- Add error handling and logging throughout

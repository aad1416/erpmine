# System Architecture Diagram

This document provides visual representations of the AI Agent system architecture.

Standard user chat and voice endpoints use **`ChatAgentService`** with the OpenAI Agents SDK for OpenAI-qualified persona models, and fall back to **`ChatService`** (LangChain) for other providers. See [chat-agent-sdk.md](chat-agent-sdk.md).

## High-Level System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Client]
        MOBILE[Mobile Client]
        API_CLIENT[API Client]
    end

    subgraph "API Layer"
        FILE_ROUTE[File Routes<br/>/files/*]
        CHAT_ROUTE[Chat Routes<br/>/features/*/chats/*]
        ADMIN_CHAT_ROUTE[Admin Chat Routes<br/>/admin/features/*/chats/*/admin-message]
        DOC_ROUTE[Document Routes<br/>/admin/features/*/documents/*]
        PERSONA_ROUTE[Persona Routes<br/>/admin/features/*/personas]
        VOICE_ROUTE[Voice Routes<br/>/features/*/chats/*/voice-message]
        FEATURE_ROUTE[Feature Routes<br/>/admin/features/*]
        CLASSROOM_ROUTE[Classroom Routes<br/>/admin/classrooms/*]
    end

    subgraph "Service Layer"
        FEATURE_SVC[Feature Service<br/>Feature Management]
        CLASSROOM_SVC[Classroom Service<br/>Classroom Management]
        CHAT_SVC[Chat Service<br/>Standard Chat Flow]
        ADMIN_CHAT_SVC[Admin Chat Service<br/>Multi-Agent Orchestration]
        AGENT_SVC[Agent Service<br/>LangChain Integration]
        RAG_SVC[RAG Service<br/>Retrieval Augmented Generation]
        MEMORY_SVC[Memory Service<br/>Chat History]
        PERSONA_SVC[Persona Service<br/>LLM Selection & Updates]
        FILE_SVC[File Service<br/>File Upload & Storage]
        DOC_SVC[Document Service<br/>Parsing & Chunking]
        EMBED_SVC[Embedding Service<br/>Text Embeddings]
        SPEECH_SVC[Speech Service<br/>STT/TTS]
        CODEBASE_SVC[Codebase Service<br/>Code Analysis]
        DB_QUERY_SVC[DB Query Service<br/>SQL Generation]
    end

    subgraph "Repository Layer"
        CHAT_REPO[Chat Repository]
        MSG_REPO[Message Repository]
        FEATURE_REPO[Feature Repository]
        PERSONA_REPO[Persona Repository]
        DOC_REPO[Document Repository]
        FILE_REPO[File Repository]
        CLASSROOM_REPO[Classroom Repository]
        CLASSROOM_ITEM_REPO[ClassroomItem Repository]
        CLASSROOM_ITEM_ASSIGN_REPO[ClassroomItemAssignment Repository]
        CLASSROOM_ITEM_DOC_REPO[ClassroomItemDoc Repository]
    end

    subgraph "Data Layer"
        SQL_DB[(PostgreSQL/SQLite<br/>Relational Database)]
        VECTOR_DB[(ChromaDB<br/>Vector Database)]
        FILE_STORAGE[(File Storage<br/>storage/documents/)]
    end

    subgraph "External Services"
        LLM[LLM Providers<br/>OpenAI/Anthropic/Gemini]
        EMBED_API[Embedding API<br/>OpenAI/HuggingFace]
        STT_API[Speech-to-Text API<br/>OpenAI Whisper]
        TTS_API[Text-to-Speech API<br/>OpenAI TTS]
    end

    WEB --> FILE_ROUTE
    WEB --> CHAT_ROUTE
    WEB --> DOC_ROUTE
    WEB --> FEATURE_ROUTE
    MOBILE --> CHAT_ROUTE
    MOBILE --> VOICE_ROUTE
    API_CLIENT --> FILE_ROUTE
    API_CLIENT --> PERSONA_ROUTE
    API_CLIENT --> FEATURE_ROUTE

    FILE_ROUTE --> FILE_SVC
    CHAT_ROUTE --> CHAT_SVC
    ADMIN_CHAT_ROUTE --> ADMIN_CHAT_SVC
    DOC_ROUTE --> FILE_SVC
    DOC_ROUTE --> DOC_SVC
    PERSONA_ROUTE --> PERSONA_SVC
    VOICE_ROUTE --> SPEECH_SVC
    VOICE_ROUTE --> CHAT_SVC
    FEATURE_ROUTE --> FEATURE_SVC
    CLASSROOM_ROUTE --> CLASSROOM_SVC

    CLASSROOM_SVC --> CLASSROOM_REPO
    CLASSROOM_SVC --> CLASSROOM_ITEM_REPO
    CLASSROOM_SVC --> CLASSROOM_ITEM_ASSIGN_REPO
    CLASSROOM_SVC --> CLASSROOM_ITEM_DOC_REPO
    CLASSROOM_SVC --> DOC_SVC
    CLASSROOM_SVC --> FILE_SVC
    FEATURE_SVC --> FEATURE_REPO
    CHAT_SVC --> AGENT_SVC
    CHAT_SVC --> RAG_SVC
    CHAT_SVC --> MEMORY_SVC
    CHAT_SVC --> PERSONA_SVC
    ADMIN_CHAT_SVC --> AGENT_SVC
    ADMIN_CHAT_SVC --> RAG_SVC
    ADMIN_CHAT_SVC --> MEMORY_SVC
    ADMIN_CHAT_SVC --> PERSONA_SVC
    AGENT_SVC --> LLM
    RAG_SVC --> VECTOR_DB
    RAG_SVC --> PERSONA_SVC
    RAG_SVC --> CODEBASE_SVC
    RAG_SVC --> DB_QUERY_SVC
    RAG_SVC --> LLM
    CODEBASE_SVC --> VECTOR_DB
    CODEBASE_SVC --> EMBED_SVC
    DB_QUERY_SVC --> SQL_DB
    DB_QUERY_SVC --> LLM
    MEMORY_SVC --> CHAT_REPO
    MEMORY_SVC --> MSG_REPO
    PERSONA_SVC --> PERSONA_REPO
    FILE_SVC --> FILE_REPO
    FILE_SVC --> FILE_STORAGE
    DOC_SVC --> FILE_SVC
    DOC_SVC --> DOC_REPO
    DOC_SVC --> VECTOR_DB
    DOC_SVC --> FILE_STORAGE
    EMBED_SVC --> EMBED_API
    SPEECH_SVC --> STT_API
    SPEECH_SVC --> TTS_API

    CHAT_REPO --> SQL_DB
    MSG_REPO --> SQL_DB
    FEATURE_REPO --> SQL_DB
    PERSONA_REPO --> SQL_DB
    DOC_REPO --> SQL_DB
    FILE_REPO --> SQL_DB
    CLASSROOM_REPO --> SQL_DB
    CLASSROOM_ITEM_REPO --> SQL_DB
    CLASSROOM_ITEM_ASSIGN_REPO --> SQL_DB
    CLASSROOM_ITEM_DOC_REPO --> SQL_DB

    style SQL_DB fill:#e1f5ff
    style VECTOR_DB fill:#fff4e1
    style FILE_STORAGE fill:#e1ffe1
    style LLM fill:#ffe1f5
    style EMBED_API fill:#ffe1f5
    style STT_API fill:#ffe1f5
    style TTS_API fill:#ffe1f5
```

## Data Model Relationships

```mermaid
erDiagram
    Feature ||--|| Persona : "has"
    Feature ||--o{ Chat : "belongs_to"
    Feature ||--o{ Document : "contains"
    Feature }o--o{ Classroom : "assigned via collections"

    Chat ||--o{ Message : "contains"

    File ||--|| Document : "processed_into"

    Classroom }o--o{ ClassroomItem : "assigned via classroom_item_assignments"
    ClassroomItem ||--o{ ClassroomItemDocument : "has"
    Document ||--o{ ClassroomItemDocument : "referenced_by"

    Feature {
        int id PK
        string name
        string store_id
        datetime created_at
        datetime updated_at
    }

    Persona {
        int id PK
        int feature_id FK
        string prompt_text
        string original_prompt_text
        string model_name
        string updated_by_user_id "plain string, no FK"
        datetime created_at
        datetime updated_at
    }

    Chat {
        int id PK
        string user_id "plain string, no FK"
        int feature_id FK
        string title
        datetime created_at
        datetime updated_at
    }

    Message {
        int id PK
        int chat_id FK
        string role
        string content
        datetime created_at
    }

    File {
        string id PK
        string file_name
        string path
        string extension
        int size
        string mime_type
        string user_id "plain string, no FK"
        datetime created_at
        datetime updated_at
    }

    Document {
        int id PK
        int feature_id FK "nullable - NULL for classroom docs"
        string file_id FK
        json metadata
    }

    FeatureClassroom {
        int id PK
        int feature_id FK
        string classroom_id FK
        datetime created_at
    }

    Classroom {
        string id PK
        string name
        datetime created_at
        datetime updated_at
    }

    ClassroomItem {
        string id PK
        string inventory_item_id UK
        datetime created_at
        datetime updated_at
    }

    ClassroomItemAssignment {
        int id PK
        string classroom_id FK
        string item_id FK
        datetime created_at
    }

    ClassroomItemDocument {
        string id PK
        string item_id FK
        string document_id FK
        string inventory_item_document_id UK
        datetime created_at
        datetime updated_at
    }
```

**Note**:
- **No Users Table**: Authentication is handled externally. `user_id` fields on `Chat`, `File`, and `Persona` are plain `String(36)` columns (no FK) used to track which identity-provider user performed each action.
- **File Model**: Stores physical file metadata and location. Files are uploaded first before being processed into documents.
- **Document Model**: Represents processed documents linked to a File. Document chunks (with content, embeddings, and metadata) are stored only in ChromaDB, not in the relational database. The Document model only tracks document metadata and relationships in the relational DB.
- **Relationship**: Each Document has a one-to-one relationship with a File. Files can exist without being processed into documents, but Documents must have an associated File.

## Standard Chat Flow with RAG

```mermaid
sequenceDiagram
    participant Client
    participant ChatRoute
    participant ChatService
    participant MemoryService
    participant PersonaService
    participant RAGService
    participant CodebaseService
    participant DBQueryService
    participant AgentService
    participant ChromaDB
    participant SQLDB
    participant LLM

    Client->>ChatRoute: POST /features/{id}/chats/{id}/messages
    ChatRoute->>ChatService: process_message(chat_id, message, feature_id)
    
    Note over ChatService: Orchestration Layer
    
    ChatService->>MemoryService: get_chat_history(chat_id)
    MemoryService-->>ChatService: message_history
    
    ChatService->>PersonaService: get_persona(feature_id)
    PersonaService-->>ChatService: persona (prompt, model_name)
    
    ChatService->>RAGService: retrieve(query, feature_id)

    Note over RAGService: Multi-source retrieval only<br/>(No generation)

    par Document Retrieval
        RAGService->>SQLDB: get_classrooms_for_feature(feature_id)
        SQLDB-->>RAGService: assigned classroom_ids
        RAGService->>SQLDB: get_items_for_classroom(classroom_id) for each classroom
        SQLDB-->>RAGService: assigned item_ids (deduplicated)
        Note over RAGService: Queries feature_{id} collection<br/>+ each item_{id} collection<br/>Results merged and re-ranked
        RAGService->>ChromaDB: query feature_{feature_id} collection
        RAGService->>ChromaDB: query item_{id} collection(s)
        Note right of ChromaDB: Direct collection access<br/>for similarity search
        ChromaDB-->>RAGService: document_chunks_with_metadata
    and Codebase Retrieval (if code-related)
        RAGService->>CodebaseService: search_codebase(query, feature_id)
        CodebaseService->>ChromaDB: collection.query(query, feature_id, type='code')
        Note right of ChromaDB: Direct collection access<br/>for code search
        ChromaDB-->>CodebaseService: code_chunks_with_metadata
        CodebaseService-->>RAGService: code_context
    and Database Query (if DB-related)
        RAGService->>DBQueryService: query_database(query, feature_id)
        DBQueryService->>SQLDB: introspect_schema()
        SQLDB-->>DBQueryService: database_schema
        DBQueryService->>LLM: generate_sql(query, schema)
        LLM-->>DBQueryService: sql_query
        DBQueryService->>DBQueryService: validate_query(sql_query)
        DBQueryService->>SQLDB: execute_query(sql_query)
        SQLDB-->>DBQueryService: query_results
        DBQueryService-->>RAGService: db_context
    end
    
    RAGService->>RAGService: combine_contexts(document_chunks, code_context, db_context)
    RAGService-->>ChatService: raw_data (JSON/Markdown format)
    
    Note over ChatService: Build prompt with:<br/>- Chat history<br/>- RAG data<br/>- User query
    ChatService->>ChatService: build_prompt(history, rag_data, query)
    
    ChatService->>AgentService: generate(prompt, persona)
    Note over AgentService: Handles persona prompt internally<br/>Constructs LLM (e.g., ChatOpenAI)<br/>Generates response
    AgentService->>AgentService: apply_persona(persona.prompt, persona.model_name)
    AgentService->>LLM: send(prompt_with_persona)
    LLM-->>AgentService: response
    AgentService-->>ChatService: response
    
    ChatService->>MemoryService: save_message(chat_id, user_message, response)
    ChatService-->>ChatRoute: response
    ChatRoute-->>Client: JSON response
```

## Admin Chat Flow (Multi-Agent Orchestration)

```mermaid
sequenceDiagram
    participant Admin
    participant AdminChatRoute
    participant AdminChatService
    participant MemoryService
    participant PersonaService
    participant RAGService
    participant AgentService
    participant SQLDB
    participant ChromaDB
    participant LLM

    Admin->>AdminChatRoute: POST /admin/features/{id}/chats/{id}/admin-message
    Note over AdminChatRoute: Admin-only endpoint
    AdminChatRoute->>AdminChatService: process_admin_message(chat_id, message, feature_id, user_id)
    
    Note over AdminChatService: Step 1: Intent Detection
    AdminChatService->>AgentService: generate(intent_prompt, gpt-3.5-turbo)
    Note right of AgentService: Prompt: "Detect user intent:<br/>Return JSON {behavior_change: bool, rag_data: bool}"
    AgentService->>LLM: Intent detection query
    LLM-->>AgentService: JSON response
    AgentService-->>AdminChatService: {behavior_change: bool, rag_data: bool}
    
    alt behavior_change = true
        Note over AdminChatService: Step 2: Persona Update (Conditional)
        AdminChatService->>PersonaService: get_persona(feature_id)
        PersonaService-->>AdminChatService: current_persona
        
        AdminChatService->>AgentService: generate(update_prompt, default_model)
        Note right of AgentService: Prompt: "Update persona according to user needs<br/>Current: {current_persona.prompt_text}"
        AgentService->>LLM: Generate new persona prompt
        LLM-->>AgentService: new_persona_prompt
        AgentService-->>AdminChatService: new_persona_prompt
        
        AdminChatService->>PersonaService: update_persona(feature_id, new_prompt, admin_user_id)
        PersonaService->>SQLDB: UPDATE personas SET prompt_text=..., updated_by_user_id=...
        SQLDB-->>PersonaService: success
        PersonaService-->>AdminChatService: updated_persona
    end
    
    alt rag_data = true
        Note over AdminChatService: Retrieve RAG Data (Conditional)
        AdminChatService->>RAGService: retrieve(query, feature_id)
        RAGService->>ChromaDB: similarity_search(query)
        ChromaDB-->>RAGService: document_chunks
        RAGService-->>AdminChatService: formatted_data + sources
    end
    
    Note over AdminChatService: Step 3: Response Synthesis
    AdminChatService->>AgentService: generate(synthesis_prompt, default_model)
    Note right of AgentService: Prompt: "Synthesize response:<br/>- Intent: {intent}<br/>- Persona update: {update_result}<br/>- RAG data: {rag_data}"
    AgentService->>LLM: Generate final response
    LLM-->>AgentService: synthesized_response
    AgentService-->>AdminChatService: synthesized_response
    
    AdminChatService->>MemoryService: save_message(chat_id, user_message, assistant_message)
    MemoryService->>SQLDB: INSERT INTO messages
    SQLDB-->>MemoryService: success
    MemoryService-->>AdminChatService: message_ids
    
    AdminChatService-->>AdminChatRoute: response_with_metadata
    Note right of AdminChatRoute: Response includes:<br/>- intent detection result<br/>- persona update (old/new)<br/>- RAG sources<br/>- synthesized response
    AdminChatRoute-->>Admin: JSON response with full metadata
```

**Admin Chat Key Features:**
- **3 Sequential LLM Calls**: Intent Detection → Persona Update (conditional) → Response Synthesis
- **Intent Detection**: Uses GPT-3.5-turbo for speed, returns JSON with behavior_change and rag_data flags
- **Dynamic Persona Updates**: Admin can modify feature persona through natural language conversation
- **Automatic Persistence**: Persona updates are auto-saved to database with admin user tracking
- **Comprehensive Metadata**: Response includes all routing decisions, updates, and sources
- **Shared Chat History**: Uses same chat infrastructure, maintains conversation context

## Document Upload & Processing Flow

```mermaid
sequenceDiagram
    participant Client
    participant FileRoute
    participant FileService
    participant DocRoute
    participant DocService
    participant FileRepo
    participant DocRepo
    participant FileStorage
    participant ChromaDB

    Note over Client,ChromaDB: Step 1: Upload Files (Multiple)
    Client->>FileRoute: POST /files/upload (multiple files)
    loop For each file
        FileRoute->>FileRoute: Validate file (type, size)
        alt File valid
            FileRoute->>FileService: create(upload_file, user_id)
            FileService->>FileStorage: save_file_to_disk(file)
            FileStorage-->>FileService: file_path
            FileService->>FileRepo: create_file_record(file_metadata)
            FileRepo-->>FileService: file_id
            FileService-->>FileRoute: File object
        else File invalid
            FileRoute->>FileRoute: Skip file, log error
        end
    end
    FileRoute-->>Client: JSON response (list of file_ids)

    Note over Client,ChromaDB: Step 2: Process File into Document
    Client->>DocRoute: POST /admin/features/{id}/documents/process
    Note right of Client: Provide file_ids[] and optional metadata
    DocRoute->>DocService: add_documents(file_ids, metadata)
    
    loop For each file_id
        DocService->>FileService: get(file_id)
        FileService-->>DocService: File object
        DocService->>DocService: parse_document(file.path)
        DocService->>DocService: chunk_text(content)
        Note over DocService: Chunks are embedded by EmbeddingService<br/>before insertion
    end
    
    DocService->>ChromaDB: collection.add(documents, metadatas)
    Note right of ChromaDB: ChromaDB stores vectors and metadata
    ChromaDB-->>DocService: success
    
    DocService->>DocRepo: create_document_records()
    DocRepo-->>DocService: Document objects
    
    DocService-->>DocRoute: List[Document]
    DocRoute-->>Client: JSON response
```

**Key Changes:**
- **Two-Step Process**: Clients must first upload files, then process them into documents
- **File Model**: Files are stored separately with metadata (name, path, size, mime_type, etc.)
- **File Management**: File routes include bulk upload (`POST /files/upload` - accepts multiple files), list (`GET /files`), get details (`GET /files/{file_id}`), and download (`GET /files/{file_id}/download`)
- **Direct Vector DB Access**: Document service receives ChromaDB Collection directly (no Vector Repository layer)
- **Embedding**: EmbeddingService generates vectors; ChromaDB stores them
- **Relationship**: Each Document references a File via `file_id` foreign key

## Voice Chat Flow

```mermaid
sequenceDiagram
    participant Client
    participant VoiceRoute
    participant SpeechService
    participant ChatService
    participant MemoryService
    participant PersonaService
    participant RAGService
    participant AgentService
    participant STT_API
    participant TTS_API
    participant LLM

    Client->>VoiceRoute: POST /features/{id}/chats/{id}/voice-message
    Note over VoiceRoute: Step 1: Speech-to-Text
    VoiceRoute->>SpeechService: transcribe_audio(audio_file)
    SpeechService->>SpeechService: validate_audio(audio_file)
    SpeechService->>STT_API: speech_to_text(audio_file)
    STT_API-->>SpeechService: transcribed_text
    SpeechService-->>VoiceRoute: text
    
    Note over VoiceRoute: Step 2: Process with ChatService (same as text chat)
    VoiceRoute->>ChatService: process_message(chat_id, text, feature_id)
    
    ChatService->>MemoryService: get_chat_history(chat_id)
    MemoryService-->>ChatService: message_history
    
    ChatService->>PersonaService: get_persona(feature_id)
    PersonaService-->>ChatService: persona
    
    ChatService->>RAGService: retrieve(text, feature_id)
    RAGService-->>ChatService: raw_data (JSON/Markdown)
    
    ChatService->>ChatService: build_prompt(history, rag_data, text)
    
    ChatService->>AgentService: generate(prompt, persona)
    AgentService->>LLM: send(prompt_with_persona)
    LLM-->>AgentService: response
    AgentService-->>ChatService: response
    
    ChatService->>MemoryService: save_message(chat_id, text, response)
    ChatService-->>VoiceRoute: text_response
    
    Note over VoiceRoute: Step 3: Text-to-Speech (Optional)
    opt TTS Enabled
        VoiceRoute->>SpeechService: text_to_speech(text_response)
        SpeechService->>TTS_API: generate_audio(text_response)
        TTS_API-->>SpeechService: audio_file
        SpeechService-->>VoiceRoute: audio_file
    end
    
    VoiceRoute-->>Client: response (text + optional audio)
```

## Feature Isolation Architecture

```mermaid
graph LR
    subgraph "Feature 1"
        F1_PERSONA[Persona 1<br/>GPT-3.5]
        F1_DOCS[Documents 1]
        F1_COLLECTION[ChromaDB Collection 1]
        F1_CHATS[Chats 1]
    end
    
    subgraph "Feature 2"
        F2_PERSONA[Persona 2<br/>Gemini Pro]
        F2_DOCS[Documents 2]
        F2_COLLECTION[ChromaDB Collection 2]
        F2_CHATS[Chats 2]
    end
    
    subgraph "Feature 3"
        F3_PERSONA[Persona 3<br/>Claude]
        F3_DOCS[Documents 3]
        F3_COLLECTION[ChromaDB Collection 3]
        F3_CHATS[Chats 3]
    end
    
    F1_DOCS --> F1_COLLECTION
    F2_DOCS --> F2_COLLECTION
    F3_DOCS --> F3_COLLECTION
    
    F1_CHATS --> F1_PERSONA
    F1_CHATS --> F1_COLLECTION
    F2_CHATS --> F2_PERSONA
    F2_CHATS --> F2_COLLECTION
    F3_CHATS --> F3_PERSONA
    F3_CHATS --> F3_COLLECTION
    
    style F1_COLLECTION fill:#fff4e1
    style F2_COLLECTION fill:#fff4e1
    style F3_COLLECTION fill:#fff4e1
```

## Component Layer Architecture

```mermaid
graph TD
    subgraph "Presentation Layer"
        API[FastAPI Routes]
    end
    
    subgraph "Business Logic Layer"
        AGENT[Agent Service]
        RAG[RAG Service]
        MEMORY[Memory Service]
        PERSONA[Persona Service]
        DOC[Document Service]
        EMBED[Embedding Service]
        SPEECH[Speech Service]
        CODEBASE[Codebase Service]
        DB_QUERY[DB Query Service]
    end
    
    subgraph "Data Access Layer"
        REPOS[Repositories]
        VECTOR_DB_DIRECT[ChromaDB Collection<br/>Direct Access]
    end
    
    subgraph "Storage Layer"
        SQL[(SQL Database)]
        VECTOR[(ChromaDB)]
        FILES[(File System)]
    end
    
    subgraph "External Services"
        LLM[LLM Providers]
    end
    
    API --> AGENT
    API --> MEMORY
    API --> PERSONA
    API --> DOC
    API --> SPEECH
    
    AGENT --> RAG
    AGENT --> MEMORY
    AGENT --> PERSONA
    AGENT --> LLM
    RAG --> VECTOR_DB_DIRECT
    RAG --> PERSONA
    RAG --> CODEBASE
    RAG --> DB_QUERY
    RAG --> LLM
    DOC --> FILE_SVC
    DOC --> VECTOR_DB_DIRECT
    SPEECH --> AGENT
    CODEBASE --> VECTOR_DB_DIRECT
    CODEBASE --> EMBED
    DB_QUERY --> SQL
    DB_QUERY --> LLM
    
    MEMORY --> REPOS
    PERSONA --> REPOS
    DOC --> REPOS
    FILE_SVC --> REPOS
    REPOS --> SQL
    VECTOR_DB_DIRECT --> VECTOR
    FILE_SVC --> FILES
    DOC --> FILES
```

## Enhanced RAG Workflow

```mermaid
graph TD
    USER_QUERY[User Query]
    RAG[RAG Service]
    
    INTENT{Intent Detection}
    
    DOC_SEARCH[Document Search<br/>Vector Similarity]
    CODE_SEARCH[Codebase Search<br/>Code Analysis]
    DB_QUERY[Database Query<br/>SQL Generation]
    
    DOC_CHUNKS[Document Chunks]
    CODE_CHUNKS[Code Chunks]
    DB_RESULTS[Query Results]
    
    CONTEXT_BUILDER[Context Builder<br/>Combine Sources]
    LLM_GEN[LLM Generation<br/>with Citations]
    RESPONSE[Response]
    
    USER_QUERY --> RAG
    RAG --> INTENT
    
    INTENT -->|Document-related| DOC_SEARCH
    INTENT -->|Code-related| CODE_SEARCH
    INTENT -->|Database-related| DB_QUERY
    INTENT -->|General| DOC_SEARCH
    INTENT -->|General| CODE_SEARCH
    
    DOC_SEARCH --> DOC_CHUNKS
    CODE_SEARCH --> CODE_CHUNKS
    DB_QUERY --> DB_RESULTS
    
    DOC_CHUNKS --> CONTEXT_BUILDER
    CODE_CHUNKS --> CONTEXT_BUILDER
    DB_RESULTS --> CONTEXT_BUILDER
    
    CONTEXT_BUILDER --> LLM_GEN
    LLM_GEN --> RESPONSE
    
    style RAG fill:#e1f5ff
    style CONTEXT_BUILDER fill:#fff4e1
    style LLM_GEN fill:#ffe1f5
```

## Notes

- **Feature Isolation**: Each feature has its own persona, documents, and ChromaDB collection
- **Store Isolation**: Features are scoped to a `store_id`. The combination of `name` + `store_id` is unique — the same feature name can exist across different stores but not within the same store. The `GET /admin/features` endpoint accepts an optional `?store_id=` query param to filter features by store.
- **Authentication**: Handled entirely by an external identity provider (e.g. SSO/OAuth). The API validates JWTs via Redis-backed token lookup in `get_current_user` — no local user table or login endpoints exist.
- **User ID Tracking**: `chats.user_id`, `files.user_id`, and `personas.updated_by_user_id` store the user ID string from the identity provider as plain columns (no FK constraint) so all CRUD operations remain traceable without a local users table.
- **Admin vs User Access**:
  - **Feature Management**: Admin-only CRUD (`GET/POST/PUT/DELETE /admin/features`)
  - **Document Management**: Admin-only CRUD operations
  - **Regular Chat**: All authenticated users can query documents through chat
  - **Admin Chat**: Admin-only, can modify persona and query data through natural language
- **Chat Types**:
  - **Standard Chat** (`POST /features/{id}/chats/{id}/messages`): Single LLM call, used by all users for Q&A
  - **Admin Chat** (`POST /admin/features/{id}/chats/{id}/admin-message`): 3 LLM calls with multi-agent orchestration, admin-only, dynamic persona updates
  - **Both**: Use same chat_id and message history, maintain shared conversation context
- **Admin Chat Multi-Agent Flow**:
  1. **Intent Detection** (GPT-3.5-turbo): Detects behavior_change and/or rag_data needs
  2. **Persona Update** (conditional): Auto-generates and saves new persona if behavior_change=true
  3. **Response Synthesis**: Combines all results into comprehensive response with full metadata
- **Intent Handling**: Admin chat handles all 4 intent combinations:
  - `{behavior_change: true, rag_data: false}` - Persona update only
  - `{behavior_change: false, rag_data: true}` - Data retrieval only
  - `{behavior_change: true, rag_data: true}` - Both persona update and data retrieval
  - `{behavior_change: false, rag_data: false}` - General chat response
- **File Upload Flow**: Clients must first upload files (via File Service), then process them into documents (via Document Service). Files can exist independently before being processed.
- **File-Document Relationship**: Each Document has a one-to-one relationship with a File. The File model stores physical file metadata (path, size, mime_type, etc.), while the Document model represents processed documents with embeddings stored in ChromaDB.
- **Vector DB Access**: All services (Document Service, RAG Service, Codebase Service) receive ChromaDB Collection directly (no Vector Repository abstraction layer). EmbeddingService generates embeddings for ingestion and queries; ChromaDB stores vectors/metadata and provides similarity search.
- **Document Metadata**: Document chunks (content, embeddings, metadata) are stored only in ChromaDB, not in the relational database. The Document relational model only tracks document relationships and basic metadata.
- **Document Active Status**: Each document chunk in ChromaDB has an `active` metadata field (`"true"` or `"false"`). RAG retrieval filters by `active: "true"`, so deactivated documents are excluded from context. Active status is managed via dedicated activate/deactivate methods in DocumentService, not through the general metadata update endpoint (`active` is a reserved key).
- **Classrooms & Items**: Classrooms and items are standalone entities. Both relationships are many-to-many:
  - Feature ↔ Classroom: managed via the `collections` table (`FeatureClassroom` model). Assignments: `POST`/`DELETE /admin/features/{feature_id}/classrooms/*`.
  - Classroom ↔ ClassroomItem: managed via the `classroom_item_assignments` table (`ClassroomItemAssignment` model). A single item can belong to many classrooms and vice versa. Assignments: `POST`/`DELETE /admin/classrooms/{classroom_id}/items/{item_id}`.
  Items are created without any classroom or feature dependency:
  - `POST /admin/classroom-items` creates a batch of items (items-only, no documents).
  - `POST /admin/classroom-items/with-documents` creates a batch of items and uploads one document per item in a single call.
  Documents are stored in per-item ChromaDB collections (`item_{ClassroomItem.id}`, keyed by the internal UUID), completely separate from a feature's own document collection (`feature_{feature_id}`). Classroom routes are admin-only under `/admin/classrooms/*`, `/admin/classroom-items/*`, and `/admin/classroom-documents/*`.
- **RAG Integration**: All chat messages automatically use RAG to retrieve relevant information from multiple sources:
  - **Feature documents**: Vector similarity search in `feature_{feature_id}` ChromaDB collection (direct uploads via `/admin/features/{id}/documents`)
  - **Classroom-item documents**: Vector similarity search across every `item_{id}` collection reachable from the feature (feature → assigned classrooms → assigned items). Item IDs are deduplicated when the same item appears in multiple assigned classrooms. Results from all collections are merged and re-ranked by relevance score before returning the top-k results.
  - **Codebase**: Code analysis and search in feature's code collection (if indexed)
  - **Database**: Natural language to SQL conversion with safe query execution
- **Multi-LLM Support**: Each persona can specify a different LLM provider (OpenAI, Anthropic, Gemini, etc.)
- **Storage**: All persistent data stored in `storage/` directory (SQLite DB, ChromaDB, uploaded files)
- **Context Combination**: RAG service intelligently combines context from documents, codebase, and database queries to provide comprehensive answers


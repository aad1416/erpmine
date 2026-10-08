# DB-RAG Text-to-SQL Flow

How natural-language questions become validated PostgreSQL queries against the Lyndom ERP database.

See also: [db_rag_reference.md](./db_rag_reference.md) for per-file, class, and method documentation.

---

## High-level flow

```mermaid
flowchart TB
    subgraph Input
        U[User question]
    end

    subgraph Retrieval["DBRagRetrievalService"]
        A[Query expansion LLM]
        B[Hybrid search ChromaDB]
        C[Optional table selection LLM]
        D[Load table-docs from disk]
    end

    subgraph SQLGen["DBRagQueryService"]
        E[Text-to-SQL LLM]
        F[Safety validation]
        G[Schema whitelist validation]
    end

    subgraph DataSources
        RD[(Chroma: retrieval-docs)]
        TD[docs/database/table-docs/*.md]
        DB[(Lyndom PostgreSQL)]
    end

    U --> A
    A --> B
    RD --> B
    B --> C
    C --> D
    TD --> D
    D -->|schema_markdown + selected_tables| E
    U --> E
    E --> F
    F --> G
    G -->|is_valid| DB
    G -->|invalid| X[Return error — no execution]
```

---

## Documentation split (why two folders)

```mermaid
flowchart LR
    subgraph Search["For discovery"]
        R[docs/database/retrieval-docs/]
        R -->|ingest| C[(Chroma collection: database_retrieval_docs)]
        R -.->|Purpose, when to retrieve, aliases| R1[Short — good for vector search]
    end

    subgraph SQL["For SQL generation"]
        T[docs/database/table-docs/]
        T -->|load by table name| L[table_docs_loader.py]
        T -.->|## Columns, FKs, enums| T1[Full — legal identifiers]
    end

    C -->|finds relevant table names| L
```

| Path | Role | Used in pipeline |
|------|------|------------------|
| `retrieval-docs/` | Semantic search: which tables matter | Chroma hybrid search (Step B) |
| `table-docs/` | Authoritative schema for SQL | Disk load after table selection (Step D) |

**Important:** Chroma snippets do **not** include `## Columns`. SQL must use disk `table-docs`, or the model has no real column names to follow.

---

## Retrieval detail (`DBRagRetrievalService`)

```mermaid
flowchart TD
    Start([get_relevant_schemas]) --> A

    A[Step A: Query expansion]
    A -->|LLM| EQ[Technical search phrase]
    A -->|on failure| EQ2[Fallback: raw user message]

    EQ --> B
    EQ2 --> B

    B[Step B: Hybrid RRF search]
    B --> V[Vector search top 100]
    B --> L[TF-IDF lexical search]
    V --> Fuse[Reciprocal Rank Fusion]
    L --> Fuse
    Fuse --> TopK[Top K tables DB_RAG_TOP_K]
    TopK --> Pin[Pin stores if missing]

    Pin --> C{DB_RAG_USE_LLM_TABLE_SELECTION?}
    C -->|yes| TS[LLM picks minimal table set]
    C -->|no| All[Use all Top-K candidates]
    TS --> Pin2[Pin stores, categories, vending]
    All --> Pin2

    Pin2 --> D[Step D: Load table-docs from disk]
    D --> Cap[Cap at DB_RAG_SQL_MAX_SCHEMA_TABLES]
    Cap --> Load[table_docs_loader.load_table_docs_markdown]
    Load -->|success| Out[schema_markdown + selected_tables]
    Load -->|empty| FB[Fallback: Chroma retrieval-docs]
    FB --> Out
```

### Step notes

| Step | Component | Output |
|------|-----------|--------|
| **A** | `get_query_expansion_prompt` + fast model | Richer search query with table name anchors |
| **B** | Embeddings + TF-IDF + RRF (`DB_RAG_RRF_ALPHA`) | Ordered list of candidate table names |
| **C** | Optional `get_table_selection_prompt` | Smaller table set (header-first rule in prompt) |
| **D** | `load_table_docs_markdown` | Full markdown with `## Columns` for SQL LLM |

---

## SQL generation detail (`DBRagQueryService`)

```mermaid
flowchart TD
    Start([generate_queries]) --> P

    P[Build prompt]
    P --> Sys[DB_RAG_SQL_GENERATION_SYSTEM_PROMPT]
    P --> User[get_sql_generation_prompt]
    User --> Ctx[User question + store scoping + table-docs markdown]

    Ctx --> LLM[AgentService.generate_async]
    LLM --> Parse[Parse JSON: queries array]

    Parse --> Loop{For each query}
    Loop --> Clean[Strip markdown fences from sql]
    Clean --> V1[_validate_sql safety]
    V1 --> V2[parse_allowed_schema]
    V2 --> V3[validate_sql_identifiers]
    V3 -->|pass| OK[is_valid: true]
    V3 -->|ValueError| Bad[is_valid: false + validation_error]
    V1 -->|fail| Bad
    OK --> Loop
    Bad --> Loop
    Loop --> Return[SqlGenerationResult]
```

### Validation layers

```mermaid
flowchart LR
    SQL[Generated SQL] --> S1[Safety]
    S1 --> S2[Schema whitelist]

    S1 -.->|blocks| B1[INSERT/UPDATE/DELETE/DROP…]
    S1 -.->|blocks| B2[Comments -- /*]
    S1 -.->|blocks| B3[Multi-statement ;]

    S2 -.->|parse| P[db_schema_markdown.parse_allowed_schema]
    S2 -.->|check| V[db_schema_markdown.validate_sql_identifiers]
    V -.->|FROM/JOIN tables| T[Known tables]
    V -.->|table.column| C[Known columns per table]
```

| Layer | File | What it catches |
|-------|------|-----------------|
| Safety | `db_rag_query_service._validate_sql` | Writes, injection patterns, multiple statements |
| Schema | `db_schema_markdown.py` | Hallucinated tables/columns (e.g. `grand_total`) |

If `parse_allowed_schema` returns nothing (no `## Columns` in context), schema validation is **skipped** with a warning — queries may still run but are not grounded.

---

## Text-to-SQL LLM behavior (prompts)

```mermaid
flowchart TD
    Q[User business language] --> Link[Schema linking in intent]
    Link --> M1[Map phrase → table.column via Business Description]
    M1 --> M2[Never snake_case user words as columns]
    Link --> Verify[List every SQL identifier vs ## Columns]
    Verify --> SQL[Write simplest SELECT]
    SQL --> R1[Prefer single table]
    SQL --> R2[Header rollups over line-item SUM]
    SQL --> R3[JOIN only when column missing on primary table]
```

Prompts live in `app/prompts/db_rag.py`:
- **System:** Lyndom doc format, workflow steps A–D, output JSON shape
- **User:** Question, store scoping, injected `table-docs` markdown

---

## End-to-end example

**Question:** `get total amount of last sales order`

```mermaid
sequenceDiagram
    participant User
    participant Retrieval as DBRagRetrievalService
    participant Chroma
    participant Disk as table-docs/
    participant SQL as DBRagQueryService
    participant Val as db_schema_markdown
    participant PG as Lyndom DB

    User->>Retrieval: user_message
    Retrieval->>Chroma: hybrid search retrieval-docs
    Chroma-->>Retrieval: sales_orders, …
    Retrieval->>Disk: load sales_orders.md (+ up to 7 more)
    Disk-->>Retrieval: full schema with order_total, created_at
    Retrieval->>SQL: schema_markdown, selected_tables
    SQL->>SQL: LLM schema linking + SQL
    SQL->>Val: parse_allowed_schema + validate_sql_identifiers
    Val-->>SQL: OK
    SQL->>PG: SELECT sales_orders.order_total … ORDER BY created_at DESC LIMIT 1
    PG-->>User: result rows
```

---

## Configuration

| Setting | Default | Effect |
|---------|---------|--------|
| `DB_RAG_TABLE_DOCS_PATH` | `docs/database/table-docs` | Disk path for full schemas |
| `DB_RAG_TOP_K` | `20` | Max tables from hybrid search |
| `DB_RAG_SQL_MAX_SCHEMA_TABLES` | `22` | Max full table-docs loaded into SQL prompt |
| `DB_RAG_USE_LLM_TABLE_SELECTION` | `false` | LLM filters candidate tables |
| `DB_RAG_RRF_ALPHA` | `0.5` | Vector vs lexical weight in fusion |
| `DB_RAG_QUERY_GEN_MODEL` | (env) | Stronger model for SQL step |
| `DB_RAG_FAST_MODEL` | (env) | Expansion / table selection |

---

## Key files

| File | Responsibility |
|------|----------------|
| `app/services/db_rag_retrieval_service.py` | Search + table selection + load table-docs |
| `app/services/db_rag_query_service.py` | LLM SQL generation + validation |
| `app/prompts/db_rag.py` | All DB-RAG prompts |
| `app/utils/table_docs_loader.py` | Read `{table}.md` from disk |
| `app/utils/db_schema_markdown.py` | Parse columns + validate SQL identifiers |
| `scripts/db_rag_sql_repl.py` | Local REPL: retrieval → SQL → execute |
| `scripts/ingest_retrieval_db_docs.py` | Ingest `retrieval-docs/` into Chroma |

---

## Chat integration

In production (`ChatService`), the same pipeline runs when `DB_RAG_ENABLED` is true: valid SQL intents are passed into the chat context; execution path depends on how the feature wires `LyndomDBRepository` (REPL executes directly).

---

## Ingestion (one-time / refresh)

```mermaid
flowchart LR
    RD[retrieval-docs/*.md] --> Script[ingest_retrieval_db_docs.py]
    Script --> Chroma[(database_retrieval_docs)]
    TD[table-docs/*.md] -->|not ingested| Disk[Used at SQL time via loader]
```

Re-run ingestion when `retrieval-docs` change. Update `table-docs` on disk when the physical schema changes — no Chroma re-index required for SQL column accuracy.

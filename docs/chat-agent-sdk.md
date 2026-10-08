# Feature chat: OpenAI Agents SDK path

Production HTTP routes (`POST .../messages` and voice) use **`ChatAgentService`**, which runs the **OpenAI Agents SDK** with optional tools when the feature persona's `model_name` is an OpenAI model (`gpt-*`, `o1*`, `o3*`, `o4*`).

- **`use_rag`**: Registers `retrieve_documents` (vector RAG via `RAGService`). The model decides when to call it.
- **`use_db`**: Registers `query_database` (schema retrieval + SQL generation + execution on Lyndom). Requires `DB_RAG_ENABLED=true`, `lyndom_db_url`, and the existing DB-RAG services.

**Legacy [`ChatService`](../app/services/chat_service.py)** is unchanged and still constructed by `get_chat_service` for scripts/tests. **`ChatAgentService`** embeds the same `ChatService` and **delegates** to it when the persona model is **not** detected as OpenAI (Claude, Gemini, Grok, etc.), so those providers keep the eager LangChain flow.

## Breaking behavior vs legacy chat on the Agents path

Previously, when `DB_RAG_ENABLED` was true, **DB-RAG SQL intents** were always prepended to the prompt. On the **Agents path**, database work runs only when the client sends **`use_db: true`** (or the voice form `use_db=true`).

## Configuration

- **`CHAT_AGENT_SDK_TRACING`**: When `false` (default), OpenAI Agents trace export is disabled. Set `true` only if you intentionally want SDK traces sent to OpenAI.

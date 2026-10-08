# Setup Guide

This guide provides instructions on how to set up and run the `ut-ai` project.

## System Requirements

- **Python**: 3.13 or newer
- **Poetry**: 2.0.0 or newer (as specified in `pyproject.toml` `build-system` requires `poetry-core>=2.0.0,<3.0.0`)
- **FFmpeg**: Required for audio processing (used by `pydub` in the STT service to decode audio files before transcription)

### Installing FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
apt-get install -y ffmpeg
```

**Alpine (Docker):**
```dockerfile
RUN apk add --no-cache ffmpeg
```

**Amazon Linux / CentOS:**
```bash
yum install -y ffmpeg
```

## Dependencies

The project dependencies are managed using Poetry. You can find the exact dependency versions in the `pyproject.toml` file.

## Installation Steps

1. **Clone the Repository**:

    ```bash
    git clone https://github.com/your-repo/ut-ai.git
    cd ut-ai
    ```

2. **Install Poetry**:

    If you don't have Poetry installed, you can install it using pip:

    ```bash
    pip install poetry
    ```

    Or, refer to the official Poetry documentation for other installation methods: [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation)

3. **Install Dependencies**:

    Navigate to the project root directory and install the dependencies using Poetry:

    ```bash
    poetry install
    ```

4. **Configure Environment**:

    The repository includes a `.env` file. Ensure `ALLOWED_FILE_TYPES` is a JSON list or a comma-separated list. Example JSON:

    ```bash
    ALLOWED_FILE_TYPES=["pdf","txt"]
    ```

    Support Email stores Mailbox Connection credentials encrypted in the database. Set `SUPPORT_CREDENTIALS_KEY` to a Fernet key. It has no default: without it, reading or writing a credential raises an error. Generate one with:

    ```bash
    poetry run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    ```

    ```bash
    SUPPORT_CREDENTIALS_KEY=<generated key>
    ```

    Keep the key secret and use a different key per environment. Credentials stored with one key can't be read with another, so don't change it once Mailboxes are stored.

    The app doesn't read Mailboxes or their credentials from the environment: each Mailbox Adapter reads its own table (`mailtrap_mailboxes`, `imap_mailboxes`, `gmail_mailboxes`). To fill those tables, set the variables below and run the seed script in step 6. Only the seed script reads them.

    | Adapter | Variables |
    |---|---|
    | IMAP/SMTP | `IMAP_MAILBOX_STORE_ID`, `IMAP_MAILBOX_EMAIL`, `IMAP_MAILBOX_APP_PASSWORD`, and optionally `IMAP_HOST` / `IMAP_PORT` / `IMAP_TLS_MODE` / `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS_MODE` (default: Gmail's servers) |
    | Gmail API | `GMAIL_USER_EMAIL`, `GMAIL_REFRESH_TOKEN` |
    | Mailtrap (dev only) | `MAILTRAP_INBOX_ADDRESS_1`, `MAILTRAP_INBOX_ID_1`, `MAILTRAP_API_TOKEN_1`, and the same with `_2` for a second inbox |

    None of these has a default in code. Each adapter's own settings use its prefix (`SUPPORT_IMAP_*`, `SUPPORT_GMAIL_*`, `SUPPORT_MAILTRAP_*`); see the adapter's `settings.py` and README. The Gmail API's OAuth client is `SUPPORT_GMAIL_CLIENT_ID` / `SUPPORT_GMAIL_CLIENT_SECRET`: the old `GMAIL_CLIENT_ID`-style names are no longer read.

    The Ticket API token, `TICKET_API_BEARER_TOKEN`, has no default either. The app refuses to start without it.

5. **Database Migrations**:

    Initialize and apply database migrations using Alembic. This creates all tables including the classroom tables (`classrooms`, `classroom_items`, `classroom_item_documents`):

    ```bash
    poetry run alembic upgrade head
    ```

6. **Seed Initial Data**:

    Run the seeding script to populate the database with initial data, including a default admin user:

    ```bash
    poetry run python scripts/seed.py
    ```

    The default admin username is `admin` and the password is `admin`.

    To copy the Support Email Mailboxes configured in the environment into the database (needs `SUPPORT_CREDENTIALS_KEY`), run:

    ```bash
    poetry run python scripts/seed_support_mailboxes.py --dry-run  # show what would change
    poetry run python scripts/seed_support_mailboxes.py
    ```

    It upserts by Mailbox address, so it is safe to run again after changing the config. It prints the adapter and Mailbox address of each row, never credentials. Mailboxes are read when the app starts, so restart it after seeding.

7. **Ingest Database Documentation**:

    To enable the Database-RAG (Text-to-SQL) pipeline, you must ingest the table schema documentation into the vector store:

    ```bash
    poetry run python scripts/ingest_db_docs.py
    ```

8. **Run the Application**:

    Start the FastAPI application in development mode using the provided shell script:

    ```bash
    bash scripts/dev.sh
    ```

    The application should now be running locally.

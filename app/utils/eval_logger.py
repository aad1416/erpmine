import json
import os
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List

class EvalLogger:
    """
    Evaluation Logger
    
    Logs document processing latency, chat latency, and retrieved chunks
    per file and branch into JSON Lines (.jsonl) files.
    """
    _instance = None
    _lock = threading.Lock()
    _branch_name = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EvalLogger, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self._ensure_logs_dir()
        self._branch_name = self._get_git_branch()
        self._write_lock = threading.Lock()
        
        # Create a single log file per app run
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self._run_logfile = os.path.join(self.logs_dir, f"eval_{self._branch_name}_{timestamp}.jsonl")

    def _ensure_logs_dir(self):
        self.logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

    def _get_git_branch(self) -> str:
        # 1. Check common CI/CD environment variables
        for var in ("GIT_BRANCH", "CI_COMMIT_BRANCH", "GITHUB_HEAD_REF", "BRANCH_NAME"):
            value = os.environ.get(var, "").strip()
            if value:
                return value.replace("/", "_").replace("\\", "_")

        # 2. Read .git/HEAD directly — no subprocess, works in local dev
        try:
            git_head = Path(os.getcwd()) / ".git" / "HEAD"
            content = git_head.read_text(encoding="utf-8").strip()
            if content.startswith("ref: refs/heads/"):
                branch = content.removeprefix("ref: refs/heads/")
                return branch.replace("/", "_").replace("\\", "_")
        except (FileNotFoundError, OSError):
            pass

        return "unknown"

    def _write_log(self, entry: Dict[str, Any]):
        entry["timestamp"] = datetime.now(UTC).isoformat()
        
        # Thread-safe write
        with self._write_lock:
            try:
                with open(self._run_logfile, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + '\n')
            except Exception as e:
                print(f"[EvalLogger] Failed to write log: {e}")

    def log_document_process(
        self,
        file_id: str,
        file_name: str,
        duration_seconds: float,
        chunks_generated: int,
        error: str = None
    ):
        """Log duration of processing a document (parsing + chunking + embedding)."""
        entry = {
            "event_type": "document_process",
            "file_id": file_id,
            "file_name": file_name,
            "duration_seconds": round(duration_seconds, 3),
            "chunks_generated": chunks_generated,
            "error": error
        }
        self._write_log(entry)

    def log_chat_interaction(
        self,
        chat_id: int,
        file_id: str,
        file_name: str,
        question: str,
        answer: str,
        retrieved_chunks: List[str],
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        error: str = None
    ):
        """Log latency, retrieved chunks, and token counts for a chat interaction."""
        entry = {
            "event_type": "chat_interaction",
            "chat_id": chat_id,
            "file_id": file_id,
            "file_name": file_name,
            "question": question,
            "answer": answer,
            "retrieved_chunk_ids": retrieved_chunks,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_seconds": round(duration_seconds, 3),
            "error": error
        }
        self._write_log(entry)

eval_logger = EvalLogger()

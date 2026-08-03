import time
from typing import Dict, Any

class PreviewJobStore:
    def __init__(self, ttl_sec: int = 600):
        self.jobs: Dict[str, dict] = {}
        self.ttl_sec = ttl_sec

    def register(self, job_id: str) -> None:
        self.cleanup()
        self.jobs[job_id] = {
            "status": "pending",
            "audio": None,
            "error": None,
            "created_at": time.time()
        }

    def get(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def update(self, job_id: str, status: str, audio: bytes | None = None, error: str | None = None) -> None:
        if job_id in self.jobs:
            self.jobs[job_id].update(status=status, audio=audio, error=error)

    def cleanup(self) -> None:
        now = time.time()
        expired = [jid for jid, job in self.jobs.items() if now - job["created_at"] > self.ttl_sec]
        for jid in expired:
            self.jobs.pop(jid, None)

# グローバルなシングルトンインスタンスとして提供
preview_job_store = PreviewJobStore()

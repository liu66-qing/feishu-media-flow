import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models import SkillJob


class SkillRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, skill_name: str, job: SkillJob) -> dict:
        skill_dir = self.settings.skill_root / skill_name
        main_py = skill_dir / "main.py"
        if not main_py.exists():
            raise FileNotFoundError(f"Skill entry not found: {main_py}")
        job_dir = self.settings.data_dir / "jobs" / f"{job.job_id}-{uuid4().hex[:8]}"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "input.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
        import os
        env = os.environ.copy()
        env["LLM_API_KEY"] = self.settings.llm_api_key
        env["LLM_BASE_URL"] = self.settings.llm_base_url
        env["LLM_MODEL"] = self.settings.llm_model
        env["LLM_TEXT_MODEL"] = self.settings.llm_text_model
        env["DATA_DIR"] = str(self.settings.data_dir)
        if self.settings.dashscope_api_key:
            env["DASHSCOPE_API_KEY"] = self.settings.dashscope_api_key
        if self.settings.platform_metrics_endpoint:
            env["PLATFORM_METRICS_ENDPOINT"] = self.settings.platform_metrics_endpoint
        timeout = (
            self.settings.image_skill_timeout_seconds
            if skill_name == "image-compose"
            else self.settings.skill_timeout_seconds
        )
        completed = subprocess.run(
            [sys.executable, str(main_py), "--job-dir", str(job_dir)],
            cwd=str(skill_dir),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output_candidates = [
            job_dir / f"{skill_name}.json",
            job_dir / f"{skill_name.replace('-', '_')}.json",
        ]
        output_file = next((path for path in output_candidates if path.exists()), output_candidates[0])
        if completed.returncode != 0:
            error_file = job_dir / "error.json"
            detail = error_file.read_text(encoding="utf-8") if error_file.exists() else (completed.stderr or completed.stdout or f"exit code {completed.returncode}")
            raise RuntimeError(f"Skill {skill_name} failed: {detail}")
        if not output_file.exists():
            expected = " or ".join(path.name for path in output_candidates)
            raise RuntimeError(f"Skill {skill_name} did not create {expected}")
        return json.loads(output_file.read_text(encoding="utf-8"))


def dry_run_skill_result(job: SkillJob, skill_name: str) -> dict:
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content_id": job.content_id,
        "data": {"skill": skill_name, "topic": job.topic, "dry_run": True},
    }

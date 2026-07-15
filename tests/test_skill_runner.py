import os
from pathlib import Path

from app.config import Settings
from app.models import Platform, SkillJob
from app.services.skill_runner import SkillRunner


def test_skill_runner_executes_skill(tmp_path) -> None:
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "main.py").write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "parser=argparse.ArgumentParser(); parser.add_argument('--job-dir', required=True); args=parser.parse_args()\n"
        "job_dir=Path(args.job_dir); data=json.loads((job_dir/'input.json').read_text(encoding='utf-8'))\n"
        "(job_dir/'demo-skill.json').write_text(json.dumps({'status':'success','timestamp':'2026-07-05T00:00:00+00:00','content_id':data['content_id'],'data':{'ok': True}}, ensure_ascii=False), encoding='utf-8')\n",
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path / "data", skill_root=tmp_path / "skills")
    job = SkillJob(content_id="CNT-1", job_id="JOB-1", platform=Platform.XHS, topic="topic")
    result = SkillRunner(settings).run("demo-skill", job)
    assert result["data"]["ok"] is True
    assert os.path.exists(settings.data_dir / "jobs")


def test_skill_runner_accepts_legacy_underscore_output_name(tmp_path) -> None:
    skill_dir = tmp_path / "skills" / "demo-package"
    skill_dir.mkdir(parents=True)
    (skill_dir / "main.py").write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "parser=argparse.ArgumentParser(); parser.add_argument('--job-dir', required=True); args=parser.parse_args()\n"
        "job_dir=Path(args.job_dir)\n"
        "(job_dir/'demo_package.json').write_text(json.dumps({'status':'success','data':{'ok': True}}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path / "data", skill_root=tmp_path / "skills")
    job = SkillJob(content_id="CNT-1", job_id="JOB-1", platform=Platform.XHS, topic="topic")

    result = SkillRunner(settings).run("demo-package", job)

    assert result["data"]["ok"] is True

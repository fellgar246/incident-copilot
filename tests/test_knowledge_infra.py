from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "infra" / "modules" / "knowledge-base" / "main.tf"
DEV = REPO_ROOT / "infra" / "environments" / "dev" / "main.tf"
SCRIPT = REPO_ROOT / "scripts" / "sync_knowledge.py"


def test_knowledge_bucket_and_role_stay_narrow() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert "knowledge-tool" in text
    assert "s3:GetObject" in text
    assert "s3:ListBucket" in text
    assert "bedrock:Retrieve" in text
    assert "bedrock:InvokeModel" not in text
    assert "s3:*" not in text
    assert "opensearch" not in text.lower()
    dev = DEV.read_text(encoding="utf-8")
    assert 'module "knowledge_base"' in dev
    assert "knowledge_corpus_enabled" in dev
    script = SCRIPT.read_text(encoding="utf-8")
    assert "KNOWLEDGE_APPLY" in script
    assert "start_ingestion_job" in script

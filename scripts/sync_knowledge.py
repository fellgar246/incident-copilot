"""Upload the operational corpus. Dry-run is the default.

KNOWLEDGE_APPLY=1 writes objects to KNOWLEDGE_BUCKET and, when
KNOWLEDGE_BASE_ID and KNOWLEDGE_DATA_SOURCE_ID are set, starts one ingestion job.
The script does not create a vector store. See docs/adrs/ADR-007-knowledge-corpus.md.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from knowledge_tool.corpus import MAX_CORPUS_BYTES, load_corpus


def metadata_sidecar(document: Any) -> dict[str, Any]:
    """Bedrock metadata sidecar. Values are attributes, not instructions."""
    attributes: dict[str, Any] = {}
    for key, value in document.metadata.items():
        attributes[key] = {
            "value": {"type": "STRING", "stringValue": value},
            "includeForEmbedding": True,
        }
    attributes["document_id"] = {
        "value": {"type": "STRING", "stringValue": document.document_id},
        "includeForEmbedding": True,
    }
    return {"metadataAttributes": attributes}


def manifest() -> dict[str, Any]:
    documents = load_corpus()
    raw_bytes = 0
    items = []
    for document in documents:
        sidecar = json.dumps(metadata_sidecar(document)).encode("utf-8")
        raw_bytes += len(document.body.encode("utf-8")) + len(sidecar)
        items.append(
            {
                "document_id": document.document_id,
                "key": document.path,
                "metadata_key": f"{document.path}.metadata.json",
                "service": document.service,
                "document_type": document.document_type,
            }
        )
    if raw_bytes > MAX_CORPUS_BYTES:
        raise RuntimeError(f"corpus exceeds {MAX_CORPUS_BYTES} bytes")
    return {
        "document_count": len(items),
        "raw_bytes": raw_bytes,
        "max_bytes": MAX_CORPUS_BYTES,
        "documents": items,
    }


def apply_sync(
    s3_client: Any, runtime_client: Any, document_manifest: dict[str, Any]
) -> dict[str, Any]:
    bucket = os.environ.get("KNOWLEDGE_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("KNOWLEDGE_BUCKET is required when KNOWLEDGE_APPLY=1")
    documents = {item.document_id: item for item in load_corpus()}
    for item in document_manifest["documents"]:
        document = documents[item["document_id"]]
        s3_client.put_object(
            Bucket=bucket,
            Key=item["key"],
            Body=document.body.encode("utf-8"),
            ContentType="text/markdown",
        )
        s3_client.put_object(
            Bucket=bucket,
            Key=item["metadata_key"],
            Body=json.dumps(metadata_sidecar(document)).encode("utf-8"),
            ContentType="application/json",
        )
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID", "").strip()
    data_source_id = os.environ.get("KNOWLEDGE_DATA_SOURCE_ID", "").strip()
    ingestion: dict[str, str] | None = None
    if knowledge_base_id and data_source_id:
        started = runtime_client.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )
        job = started.get("ingestionJob") or {}
        ingestion = {"ingestionJobId": str(job.get("ingestionJobId", ""))}
    return {
        "bucket": bucket,
        "uploaded": len(document_manifest["documents"]),
        "ingestion": ingestion,
    }


def main() -> int:
    document = manifest()
    if os.environ.get("KNOWLEDGE_APPLY") == "1":
        import boto3  # type: ignore[import-untyped]

        region = os.environ.get("AWS_REGION", "us-east-1")
        result = apply_sync(
            boto3.client("s3", region_name=region),
            boto3.client("bedrock-agent", region_name=region),
            document,
        )
        print(json.dumps({"manifest": document, "apply": result}, indent=2))
        return 0
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

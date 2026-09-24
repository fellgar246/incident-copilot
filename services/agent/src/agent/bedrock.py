"""Bedrock Converse adapter. Tests use ScriptedInvestigator instead of this client."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from incident_contracts.gateway import gateway_tools

from agent.model import ChatMessage, LanguageModel, ModelTurn, ToolRequest, approximate_tokens

DEFAULT_MODEL_ID = "us.amazon.nova-micro-v1:0"


def bedrock_tool_specs() -> list[dict[str, Any]]:
    """Advertise only the gateway catalog. Search and undeclared tools are omitted."""
    return [
        {
            "toolSpec": {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {"json": tool.input_schema},
            }
        }
        for tool in gateway_tools()
    ]


def model_id_from_env(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID) or DEFAULT_MODEL_ID


class BedrockConverseModel:
    """Calls bedrock-runtime Converse. Construct only when invocation is enabled."""

    def __init__(self, client: Any, *, model_id: str, region: str) -> None:
        self._client = client
        self.model_id = model_id
        self.region = region

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
    ) -> ModelTurn:
        response = self._client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[_to_bedrock(message) for message in messages if message.role != "tool"],
            toolConfig={"tools": bedrock_tool_specs()},
            inferenceConfig={"maxTokens": max_output_tokens},
        )
        usage = response.get("usage") or {}
        input_tokens = int(usage.get("inputTokens") or 0)
        output_tokens = int(usage.get("outputTokens") or 0)
        content = (response.get("output") or {}).get("message", {}).get("content") or []
        requests: list[ToolRequest] = []
        texts: list[str] = []
        for block in content:
            if "toolUse" in block:
                tool = block["toolUse"]
                raw_input = tool.get("input") or {}
                arguments = raw_input if isinstance(raw_input, dict) else {}
                requests.append(ToolRequest(str(tool.get("name")), arguments))
            elif "text" in block:
                texts.append(str(block["text"]))
        diagnosis = "\n".join(texts) if texts and not requests else None
        if input_tokens == 0:
            input_tokens = approximate_tokens(system_prompt)
        return ModelTurn(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_requests=tuple(requests),
            diagnosis_text=diagnosis,
        )


def _to_bedrock(message: ChatMessage) -> dict[str, Any]:
    role = "user" if message.role != "assistant" else "assistant"
    return {"role": role, "content": [{"text": message.content}]}


def build_model(environ: Mapping[str, str] | None = None) -> LanguageModel:
    """Return a Bedrock client when AGENT_MODEL=bedrock, otherwise the scripted investigator."""
    env = os.environ if environ is None else environ
    mode = env.get("AGENT_MODEL", "scripted").strip().lower()
    model_id = model_id_from_env(env)
    if mode != "bedrock":
        from agent.model import ScriptedInvestigator

        return ScriptedInvestigator(model_id=model_id)
    import boto3  # type: ignore[import-untyped]

    region = env.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    return BedrockConverseModel(client, model_id=model_id, region=region)


def invocation_enabled(ai_enabled: bool, agent_invocation_enabled: bool) -> bool:
    return ai_enabled and agent_invocation_enabled


def dumps_turn(turn: ModelTurn) -> str:
    return json.dumps(
        {
            "tools": [item.name for item in turn.tool_requests],
            "diagnosis": turn.diagnosis_text,
        }
    )

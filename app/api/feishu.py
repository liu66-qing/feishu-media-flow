from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.models import Platform
from app.services.commands import parse_command
from app.services.feishu_security import verify_event_token, verify_webhook_signature
from app.services.idempotency import IdempotencyStore
from app.services.workflow import WorkflowService

router = APIRouter()


@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    x_lark_request_timestamp: str = Header(default=""),
    x_lark_request_nonce: str = Header(default=""),
    x_lark_signature: str = Header(default=""),
) -> dict:
    settings = get_settings()
    body = await request.body()
    if not verify_webhook_signature(
        x_lark_request_timestamp,
        x_lark_request_nonce,
        body,
        settings.feishu_encrypt_key,
        x_lark_signature,
    ):
        raise HTTPException(status_code=401, detail="invalid feishu signature")
    payload = await request.json()
    if payload.get("type") == "url_verification":
        if not verify_event_token(payload, settings.feishu_verification_token):
            raise HTTPException(status_code=401, detail="invalid verification token")
        return {"challenge": payload.get("challenge")}
    if not verify_event_token(payload.get("header", {}), settings.feishu_verification_token):
        raise HTTPException(status_code=401, detail="invalid event token")

    header = payload.get("header", {})
    event_id = header.get("event_id") or payload.get("uuid", "")
    store = IdempotencyStore(settings.data_dir / "event_ids.json")
    if store.seen_or_record(event_id):
        return {"status": "duplicate", "event_id": event_id}

    event_type = header.get("event_type", "")
    workflow = WorkflowService(settings)
    if "im.message.receive" in event_type:
        return await _handle_message(payload.get("event", {}), workflow)
    if "card.action.trigger" in event_type or payload.get("type") == "card_action":
        return await _handle_card_action(payload.get("event", payload), workflow)
    return {"status": "ignored", "event_type": event_type}


async def _handle_message(event: dict, workflow: WorkflowService) -> dict:
    message = event.get("message", {})
    content = message.get("content", "")
    text = _extract_text(content)
    command = parse_command(text)
    if command is None:
        return {"status": "ignored", "reason": "not a command"}
    if command.name in {"状态", "status"}:
        return await workflow.status_summary()
    if command.name in {"新建", "create"}:
        if len(command.args) < 2:
            return {"status": "error", "message": "用法：/新建 平台 选题"}
        platform = _parse_platform(command.args[0])
        topic = " ".join(command.args[1:])
        return await workflow.create_content_from_topic(platform, topic)
    return {"status": "ignored", "reason": f"unknown command {command.name}"}


async def _handle_card_action(event: dict, workflow: WorkflowService) -> dict:
    action_value = event.get("action", {}).get("value", {}) or event.get("action_value", {})
    operator = event.get("operator", {}).get("open_id", "")
    action = action_value.get("action")
    content_ids = action_value.get("content_ids", [])

    # Legacy bulk approve
    if action == "approve_all":
        return await workflow.approve(content_ids, operator)

    # Agent loop: topic approval
    if action == "approve_topic":
        from app.services.agent_loop import AgentLoop
        settings = get_settings()
        agent = AgentLoop(settings)
        topic_id = action_value.get("topic_id", "")
        return await agent.advance_item(topic_id, reason="topic_approved")

    if action == "reject_topic":
        from app.services.agent_loop import AgentLoop
        settings = get_settings()
        agent = AgentLoop(settings)
        topic_id = action_value.get("topic_id", "")
        # Mark as rejected
        from app.services.bitable import BitableClient
        bitable = BitableClient(settings)
        try:
            records = await bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == topic_id:
                    await bitable.update_record("content", r["record_id"], {"status": "rejected"})
                    break
        except Exception:
            pass
        return {"status": "rejected", "topic_id": topic_id}

    # Agent loop: publish approval
    if action == "approve_publish":
        from app.services.agent_loop import AgentLoop
        settings = get_settings()
        agent = AgentLoop(settings)
        content_id = action_value.get("content_id", "")
        return await agent.advance_item(content_id, reason="publish_approved")

    if action == "reject_publish":
        from app.services.agent_loop import AgentLoop
        settings = get_settings()
        agent = AgentLoop(settings)
        content_id = action_value.get("content_id", "")
        from app.services.bitable import BitableClient
        bitable = BitableClient(settings)
        try:
            records = await bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == content_id:
                    await bitable.update_record("content", r["record_id"], {"status": "rejected"})
                    break
        except Exception:
            pass
        return {"status": "rejected", "content_id": content_id}

    return {"status": "ignored", "action": action}


def _extract_text(content: str | dict) -> str:
    if isinstance(content, dict):
        return str(content.get("text", ""))
    if not content:
        return ""
    if content.startswith("{"):
        try:
            import json

            return str(json.loads(content).get("text", ""))
        except Exception:
            return content
    return content


def _parse_platform(raw: str) -> Platform:
    aliases = {"小红书": Platform.XHS, "xhs": Platform.XHS, "公众号": Platform.WECHAT, "wechat": Platform.WECHAT, "抖音": Platform.DOUYIN, "douyin": Platform.DOUYIN}
    value = aliases.get(raw.lower()) or aliases.get(raw)
    if value is None:
        raise HTTPException(status_code=400, detail=f"unknown platform: {raw}")
    return value


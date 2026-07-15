from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.models import Platform
from app.services.agent_loop import AgentLoop
from app.services.commands import parse_command
from app.services.feishu_security import verify_event_token, verify_webhook_signature
from app.services.idempotency import IdempotencyStore

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
    payload = await request.json()

    # url_verification (challenge) comes without signature headers
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if not verify_webhook_signature(
        x_lark_request_timestamp,
        x_lark_request_nonce,
        body,
        settings.feishu_encrypt_key,
        x_lark_signature,
    ):
        raise HTTPException(status_code=401, detail="invalid feishu signature")
    if not verify_event_token(payload.get("header", {}), settings.feishu_verification_token):
        raise HTTPException(status_code=401, detail="invalid event token")

    header = payload.get("header", {})
    event_id = header.get("event_id") or payload.get("uuid", "")
    store = IdempotencyStore(settings.data_dir / "event_ids.json")
    if store.seen_or_record(event_id):
        return {"status": "duplicate", "event_id": event_id}

    event_type = header.get("event_type", "")
    agent = AgentLoop(settings)
    if "im.message.receive" in event_type:
        return await _handle_message(payload.get("event", {}), agent)
    if "card.action.trigger" in event_type or payload.get("type") == "card_action":
        return await _handle_card_action(payload.get("event", payload), agent)
    return {"status": "ignored", "event_type": event_type}


async def _handle_message(event: dict, agent: AgentLoop) -> dict:
    notifier = agent.notifier
    message = event.get("message", {})
    message_id = message.get("message_id", "")
    chat_id = message.get("chat_id", "")
    content = message.get("content", "")
    text = _extract_text(content)
    command = parse_command(text)
    if command is None:
        return {"status": "ignored", "reason": "not a command"}

    if command.name in {"状态", "status"}:
        result = await agent.status_summary()
        card = result.get("card")
        if card and chat_id:
            await notifier.send_card(chat_id, card)
        elif message_id:
            await notifier.reply_text(message_id, "系统运行中，暂无详细状态。")
        return result

    if command.name in {"排期", "schedule"}:
        result = await agent.get_schedule()
        card = result.get("card")
        if card and chat_id:
            await notifier.send_card(chat_id, card)
        elif message_id:
            await notifier.reply_text(message_id, "暂无排期内容")
        return result

    if command.name in {"新建", "create"}:
        if len(command.args) < 2:
            if message_id:
                await notifier.reply_text(message_id, "用法：/新建 平台 选题\n例如：/新建 小红书 如何高效学习")
            return {"status": "error", "message": "用法：/新建 平台 选题"}
        platform = _parse_platform(command.args[0])
        topic = " ".join(command.args[1:])
        if message_id:
            await notifier.reply_text(message_id, f"收到！正在为你生成 {platform.value} 内容：{topic}")

        import asyncio

        async def _run_generation() -> None:
            try:
                await agent.create_content_from_topic(platform, topic, chat_id=chat_id)
                if platform == Platform.DOUYIN:
                    message = f"抖音图文卡片已生成，请按卡片顺序手动上传：{topic}"
                elif platform == Platform.WECHAT:
                    message = f"公众号文章与配图已生成，草稿结果和插图位置已发送：{topic}"
                else:
                    message = f"内容与配图已生成，请在审批卡片中确认发布：{topic}"
                await notifier.send_text(chat_id, message)
            except Exception as e:
                await notifier.send_text(chat_id, f"❌ 生成失败：{e}")

        asyncio.create_task(_run_generation())
        return {"status": "accepted", "topic": topic}

    if message_id:
        await notifier.reply_text(message_id, f"未知命令：/{command.name}\n支持：/状态、/新建 平台 选题、/排期")
    return {"status": "ignored", "reason": f"unknown command {command.name}"}


async def _handle_card_action(event: dict, agent: AgentLoop) -> dict:
    action_value = event.get("action", {}).get("value", {}) or event.get("action_value", {})
    operator = event.get("operator", {}).get("open_id", "")
    if not isinstance(action_value, dict):
        return {"status": "error", "detail": "invalid card action payload"}
    return await agent.handle_card_action(action_value, operator)


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


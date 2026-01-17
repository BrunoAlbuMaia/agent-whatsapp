from src.Domain import MessageupsertEntity


def map_webhook_to_incoming_message(payload: dict) -> MessageupsertEntity | None:
    if payload.get("event") != "messages.upsert":
        return None

    data = payload.get("data", {})
    key = data.get("key", {})

    if key.get("fromMe"):
        return None

    message = data.get("message", {})
    text = message.get("conversation")

    if not text:
        return None

    return MessageupsertEntity(
        sender_id=key.get("remoteJid"),
        sender_name=data.get("pushName"),
        text=text,
        timestamp=data.get("messageTimestamp"),
        instance=payload.get("instance")
    )

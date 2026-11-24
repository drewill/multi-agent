def message_text(message) -> str:
    content = message.content

    if isinstance(content, str):
        return content

    parts = []

    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)

    return "\n".join(parts)
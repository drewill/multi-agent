from datetime import datetime, timezone


def datetime_to_str(value: datetime | None) -> str | None:
    """数据库中的时间按 UTC 保存，返回带时区的字符串。"""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.isoformat()
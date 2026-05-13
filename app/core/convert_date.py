from datetime import datetime, date, timezone

def convert_dates(obj, tz):
    if isinstance(obj, dict):
        return {k: convert_dates(v, tz) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_dates(v, tz) for v in obj]
    if isinstance(obj, datetime):
        if (
            obj.hour == 0 and
            obj.minute == 0 and
            obj.second == 0 and
            obj.microsecond == 0
        ):
            return obj.date().isoformat()
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(tz)
    if isinstance(obj, date):
        return obj.isoformat()
    return obj
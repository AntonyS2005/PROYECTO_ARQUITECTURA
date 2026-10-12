from datetime import datetime, timezone


def fecha_iso(fecha=None):
    return (
        (fecha or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

import csv
import io

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from .config import get_settings


async def read_csv_upload(file: UploadFile, required: set[str]) -> list[dict]:
    raw = await file.read(get_settings().max_upload_bytes + 1)
    if len(raw) > get_settings().max_upload_bytes:
        raise HTTPException(413, "File is too large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(422, "CSV has no header row")
    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = required - headers
    if missing:
        raise HTTPException(422, f"CSV is missing column(s): {', '.join(sorted(missing))}")
    rows = []
    for row in reader:
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if any(clean.values()):
            rows.append(clean)
    return rows


def parse_float(value: str, field: str, line: int) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        raise HTTPException(422, f"Line {line}: '{value}' is not a number for {field}")


def csv_response(rows: list[list], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(["" if v is None else _safe(v) for v in r])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _safe(v):
    # neutralise spreadsheet formula injection
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = "application/pdf"

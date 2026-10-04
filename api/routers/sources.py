from typing import Any

from fastapi import APIRouter, HTTPException

from api.services import sources

router = APIRouter()


@router.get("/{source}/{table}")
def read_table(source: str, table: str) -> dict[str, Any]:
    try:
        return sources.read_table(source, table)
    except sources.UnknownTable as e:
        raise HTTPException(status_code=404, detail=f"unknown table {e}") from e

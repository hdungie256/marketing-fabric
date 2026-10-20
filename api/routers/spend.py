from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from api.services import spend

router = APIRouter()


class SpendChange(BaseModel):
    allocated_online_spend: Decimal


@router.put("/spend/campaign_spend/{campaign_id}/{day}")
def edit_spend(
    campaign_id: str, day: date, change: SpendChange, x_fabric_role: str = Header(default="")
) -> dict[str, Any]:
    try:
        return spend.edit_allocation(x_fabric_role, campaign_id, day, change.allocated_online_spend)
    except spend.Forbidden as e:
        raise HTTPException(status_code=403, detail={"reason": str(e)}) from e
    except spend.Invalid as e:
        raise HTTPException(status_code=422, detail={"field": e.field, "reason": e.reason}) from e
    except spend.RefreshNotStarted as e:
        raise HTTPException(status_code=502, detail={"reason": str(e), "event": e.event}) from e

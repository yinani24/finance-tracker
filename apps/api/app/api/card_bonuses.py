from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.card_bonuses import get_card_by_id, get_issuers, search_cards

router = APIRouter(prefix="/card-bonuses", tags=["card-bonuses"])


@router.get("")
async def list_card_bonuses(
    q: Optional[str] = Query(None, description="Search card name or issuer"),
    issuer: Optional[str] = Query(None, description="Filter by issuer (e.g. CHASE)"),
    network: Optional[str] = Query(
        None, description="Filter by network (VISA, MASTERCARD, AMERICAN_EXPRESS)"
    ),
    is_business: Optional[bool] = Query(None, description="Filter business vs personal cards"),
    max_annual_fee: Optional[float] = Query(None, description="Max annual fee"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict:
    return await search_cards(
        q=q,
        issuer=issuer,
        network=network,
        is_business=is_business,
        max_annual_fee=max_annual_fee,
        limit=limit,
        offset=offset,
    )


@router.get("/issuers")
async def list_issuers() -> List[str]:
    return await get_issuers()


@router.get("/{card_id}")
async def get_card(card_id: str) -> dict:
    card = await get_card_by_id(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card

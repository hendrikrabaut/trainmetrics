import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.polar_account import PolarAccount
from app.services import polar


router = APIRouter(
    prefix="/api/polar",
    tags=["polar"],
)

# state -> user id. Proves that a callback belongs to a link this app started.
_pending_links: dict[str, int] = {}


@router.get("/status")
def get_status(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    account = db.get(PolarAccount, user_id)

    return {
        "configured": polar.is_configured(),
        "linked": account is not None,
        "last_sync_at": account.last_sync_at if account else None,
    }


@router.get("/connect")
def connect(user_id: int = 1):
    if not polar.is_configured():
        raise HTTPException(
            status_code=503,
            detail="POLAR_CLIENT_ID and POLAR_CLIENT_SECRET are not set",
        )

    state = secrets.token_urlsafe(24)
    _pending_links[state] = user_id

    return RedirectResponse(polar.authorization_url(state))


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    user_id = _pending_links.pop(state or "", None)

    if user_id is None or error or not code:
        return RedirectResponse("/#profiel?polar=geweigerd", status_code=303)

    try:
        token, polar_user_id = polar.exchange_code(code)
        polar.register_user(token, f"trainmetrics-{user_id}")
    except polar.PolarError:
        return RedirectResponse("/#profiel?polar=mislukt", status_code=303)

    account = db.get(PolarAccount, user_id)

    if account is None:
        db.add(
            PolarAccount(
                user_id=user_id,
                polar_user_id=polar_user_id,
                access_token=token,
            )
        )
    else:
        account.access_token = token
        account.polar_user_id = polar_user_id

    db.commit()

    return RedirectResponse("/#profiel?polar=gekoppeld", status_code=303)


@router.post("/sync")
def sync(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    try:
        return polar.sync(db, user_id)
    except polar.PolarAuthorizationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except polar.PolarError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.delete("/link")
def unlink(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    """Removes the token here. Imported trainings stay."""
    account = db.get(PolarAccount, user_id)

    if account is not None:
        db.delete(account)
        db.commit()

    return {"message": "Polar account unlinked"}

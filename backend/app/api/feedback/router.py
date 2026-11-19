from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.accounts.router import get_current_user
from app.db.dependencies import get_session
from app.db.models import User
from app.schemas.feedback import FeedbackReceipt, FeedbackSubmission
from app.services.feedback.service import FeedbackError, submit_feedback


class FeedbackRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request: Request):
            try:
                return await handler(request)
            except SQLAlchemyError:
                # Include authentication/database dependency failures, not only writes.
                # Never expose SQL parameters (feedback text) in responses or logs.
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Feedback persistence unavailable"},
                    headers={"Cache-Control": "no-store"},
                )

        return guarded


router = APIRouter(prefix="/feedback", tags=["feedback"], route_class=FeedbackRoute)


@router.post(
    "",
    response_model=FeedbackReceipt,
    status_code=201,
    responses={
        200: {"model": FeedbackReceipt, "description": "Original receipt on retry"},
        401: {"description": "Authentication required"},
        409: {"description": "Request ID reused for different content"},
        429: {"description": "Account submission limit reached"},
        503: {"description": "Persistence unavailable"},
    },
)
def submit(
    payload: FeedbackSubmission,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FeedbackReceipt:
    response.headers["Cache-Control"] = "no-store"
    try:
        receipt, created = submit_feedback(session, user.id, payload)
    except FeedbackError as error:
        headers = {"Cache-Control": "no-store"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        if error.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        raise HTTPException(error.status, str(error), headers=headers) from None
    response.status_code = 201 if created else 200
    return receipt

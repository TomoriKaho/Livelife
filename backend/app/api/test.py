from fastapi import APIRouter

from app.schemas.hello import HelloResponse

router = APIRouter()


@router.get("/hello", response_model=HelloResponse)
def get_hello() -> HelloResponse:
    return HelloResponse(message="hello world")

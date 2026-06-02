from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.dependencies import (
    SESSION_USER_ID_KEY,
    get_auth_service,
    require_authenticated_user,
)
from api.models.schemas import (
    AuthSessionResponse,
    AuthenticatedUserResponse,
    LoginRequest,
    RegisterRequest,
)
from api.services.auth import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidNameError,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _start_session(request: Request, user: AuthenticatedUserResponse) -> None:
    request.session.clear()
    request.session[SESSION_USER_ID_KEY] = user.id


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    try:
        user = await auth_service.authenticate(
            identifier=payload.identifier,
            password=payload.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _start_session(request, user)
    return AuthSessionResponse(authenticated=True, user=user)


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    try:
        user = await auth_service.create_user(
            name=payload.name,
            email=payload.email,
            password=payload.password,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidNameError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except InvalidEmailError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    _start_session(request, user)
    return AuthSessionResponse(authenticated=True, user=user)


@router.get("/session", response_model=AuthSessionResponse)
async def get_session(
    user: AuthenticatedUserResponse = Depends(require_authenticated_user),
) -> AuthSessionResponse:
    return AuthSessionResponse(authenticated=True, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

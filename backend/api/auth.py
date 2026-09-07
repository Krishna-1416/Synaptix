import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.models.auth import SignUpRequest, LoginRequest, AuthResponse, UserProfile
from backend.services.supabase_client import get_supabase_client, get_supabase_admin_client

logger = logging.getLogger("synaptix.auth")
router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])
security = HTTPBearer(auto_error=False)


@router.post(
    "/signup",
    response_model=AuthResponse,
    summary="Register an enforcement inspector account"
)
async def signup_user(payload: SignUpRequest):
    client = get_supabase_client()
    if not client:
        # Development / offline mock fallback
        return AuthResponse(
            access_token="mock_dev_token_inspector",
            user=UserProfile(
                id="USR-MOCK-001",
                email=payload.email,
                full_name=payload.full_name or "Inspector Officer",
                role=payload.role or "inspector"
            ),
            message="Supabase offline. Logged in via development mock mode."
        )

    try:
        res = client.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": {
                "data": {
                    "full_name": payload.full_name,
                    "role": payload.role or "inspector"
                }
            }
        })

        user_data = res.user
        token = res.session.access_token if res.session else None
        
        # Also ensure record exists in public.profiles table
        admin = get_supabase_admin_client()
        if admin and user_data:
            try:
                admin.table("profiles").upsert({
                    "id": user_data.id,
                    "full_name": payload.full_name,
                    "role": payload.role or "inspector"
                }).execute()
            except Exception as pe:
                logger.warning(f"Profile creation warning: {pe}")

        return AuthResponse(
            access_token=token,
            user=UserProfile(
                id=user_data.id if user_data else "created",
                email=payload.email,
                full_name=payload.full_name,
                role=payload.role or "inspector"
            ),
            message="User created successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login to the Synaptix Enforcement System"
)
async def login_user(payload: LoginRequest):
    client = get_supabase_client()
    if not client:
        # Development / offline mock fallback
        return AuthResponse(
            access_token="mock_dev_token_inspector",
            user=UserProfile(
                id="USR-MOCK-001",
                email=payload.email,
                full_name="Inspector Officer",
                role="inspector"
            ),
            message="Supabase offline. Authenticated via development mock mode."
        )

    try:
        res = client.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        if not res.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        user_data = res.user
        user_meta = user_data.user_metadata if user_data else {}

        return AuthResponse(
            access_token=res.session.access_token,
            user=UserProfile(
                id=user_data.id,
                email=user_data.email,
                full_name=user_meta.get("full_name", "Enforcement Officer"),
                role=user_meta.get("role", "inspector")
            ),
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get details of the currently authenticated inspector"
)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        # Default guest inspector in development mode
        return UserProfile(
            id="USR-GUEST",
            email="guest.inspector@gov.in",
            full_name="Guest Enforcement Officer",
            role="inspector"
        )

    token = credentials.credentials
    if token == "mock_dev_token_inspector":
        return UserProfile(
            id="USR-MOCK-001",
            email="inspector@synaptix.gov.in",
            full_name="Lead Inspector",
            role="inspector"
        )

    client = get_supabase_client()
    if client:
        try:
            res = client.auth.get_user(token)
            if res.user:
                meta = res.user.user_metadata or {}
                return UserProfile(
                    id=res.user.id,
                    email=res.user.email,
                    full_name=meta.get("full_name", "Inspector"),
                    role=meta.get("role", "inspector")
                )
        except Exception as e:
            logger.warning(f"Failed verifying token: {e}")

    return UserProfile(
        id="USR-ACTIVE",
        email="officer@synaptix.gov.in",
        full_name="Active Officer",
        role="inspector"
    )

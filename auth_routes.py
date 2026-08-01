import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field


router = APIRouter()

USERS_FILE = Path("/root/aistudio-api/data/users.json")
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

PLANS = [
    {
        "id": "free",
        "name": "رایگان",
        "images": 3,
        "content": 10,
        "analyzer": False,
    },
    {
        "id": "pro",
        "name": "حرفه‌ای",
        "images": 100,
        "content": 100,
        "analyzer": True,
    },
    {
        "id": "premium",
        "name": "پریمیوم",
        "images": 500,
        "content": -1,
        "analyzer": True,
    },
]


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


def load_users() -> list[dict[str, Any]]:
    if not USERS_FILE.exists():
        return []

    try:
        content = USERS_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return []

        data = json.loads(content)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_users(users: list[dict[str, Any]]) -> None:
    temporary_file = USERS_FILE.with_suffix(".json.tmp")

    temporary_file.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temporary_file.replace(USERS_FILE)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(user.get("id", "")),
        "name": str(user.get("name", "")),
        "email": str(user.get("email", "")),
        "plan": str(user.get("plan", "free")),
        "credits": int(user.get("credits", 0) or 0),
        "created_at": str(user.get("created_at", "")),
    }


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="توکن ورود ارسال نشده است",
        )

    scheme, _, token = authorization.strip().partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="فرمت توکن ورود معتبر نیست",
        )

    return token.strip()


def find_user_by_token(
    users: list[dict[str, Any]],
    token: str,
) -> tuple[int, dict[str, Any]]:
    for index, user in enumerate(users):
        if secrets.compare_digest(
            str(user.get("token", "")),
            token,
        ):
            return index, user

    raise HTTPException(
        status_code=401,
        detail="نشست کاربری معتبر نیست؛ دوباره وارد شوید",
    )


@router.post("/v1/auth/register")
def register(request: RegisterRequest):
    users = load_users()
    email = normalize_email(str(request.email))

    for user in users:
        if normalize_email(str(user.get("email", ""))) == email:
            raise HTTPException(
                status_code=400,
                detail="این ایمیل قبلاً ثبت شده است",
            )

    user = {
        "id": secrets.token_hex(8),
        "name": request.name.strip(),
        "email": email,
        "password": hash_password(request.password),
        "token": secrets.token_hex(32),
        "plan": "free",
        "credits": 3,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    users.append(user)
    save_users(users)

    return {
        "success": True,
        "token": user["token"],
        "user": public_user(user),
        "message": "ثبت‌نام با موفقیت انجام شد",
    }


@router.post("/v1/auth/login")
def login(request: LoginRequest):
    users = load_users()
    email = normalize_email(str(request.email))
    password_hash = hash_password(request.password)

    for user in users:
        if (
            normalize_email(str(user.get("email", ""))) == email
            and secrets.compare_digest(
                str(user.get("password", "")),
                password_hash,
            )
        ):
            user["token"] = secrets.token_hex(32)
            save_users(users)

            return {
                "success": True,
                "token": user["token"],
                "user": public_user(user),
                "message": "ورود با موفقیت انجام شد",
            }

    raise HTTPException(
        status_code=401,
        detail="ایمیل یا رمز عبور اشتباه است",
    )


@router.get("/v1/auth/me")
def me(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
):
    token = extract_bearer_token(authorization)
    users = load_users()
    _, user = find_user_by_token(users, token)

    return {
        "success": True,
        "user": public_user(user),
    }


@router.post("/v1/auth/change-password")
def change_password(
    request: ChangePasswordRequest,
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
):
    token = extract_bearer_token(authorization)
    users = load_users()
    user_index, user = find_user_by_token(users, token)

    current_password_hash = hash_password(request.current_password)

    if not secrets.compare_digest(
        str(user.get("password", "")),
        current_password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="رمز فعلی اشتباه است",
        )

    new_password_hash = hash_password(request.new_password)

    if secrets.compare_digest(
        str(user.get("password", "")),
        new_password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="رمز جدید نباید با رمز فعلی یکسان باشد",
        )

    users[user_index]["password"] = new_password_hash

    # با تغییر رمز، توکن هم عوض می‌شود تا نشست قبلی معتبر نماند.
    users[user_index]["token"] = secrets.token_hex(32)
    save_users(users)

    return {
        "success": True,
        "token": users[user_index]["token"],
        "user": public_user(users[user_index]),
        "message": "رمز عبور با موفقیت تغییر کرد",
    }


@router.get("/v1/plans")
def get_plans():
    return {
        "success": True,
        "plans": PLANS,
    }

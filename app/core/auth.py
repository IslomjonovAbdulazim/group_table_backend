from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})

    # Ensure 'sub' is a string (JWT requirement)
    if 'sub' in to_encode:
        to_encode['sub'] = str(to_encode['sub'])

    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str = payload.get("sub")
        user_type = payload.get("type")

        if user_id_str is None or user_type is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Convert string user_id back to integer
        try:
            user_id = int(user_id_str)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {"user_id": user_id, "user_type": user_type}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error in token verification: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# Helper functions for role-based access
def require_admin(token_data: dict = Depends(verify_token)) -> int:
    if token_data["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return token_data["user_id"]


def require_teacher(token_data: dict = Depends(verify_token)) -> int:
    if token_data["user_type"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    return token_data["user_id"]
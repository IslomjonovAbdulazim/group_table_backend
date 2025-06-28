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

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    logger.info(f"Created token for user {data.get('sub')} with type {data.get('type')}")
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    logger.info(f"Verifying token: {token[:20]}...")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str = payload.get("sub")  # This will be a string from JWT
        user_type = payload.get("type")

        logger.info(f"Token payload - user_id_str: {user_id_str} (type: {type(user_id_str)}), user_type: {user_type}")

        if user_id_str is None or user_type is None:
            logger.error("Token missing required fields")
            raise HTTPException(status_code=401, detail="Invalid token")

        # Convert string user_id back to integer
        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.error(f"Cannot convert user_id '{user_id_str}' to int")
            raise HTTPException(status_code=401, detail="Invalid token")

        result = {"user_id": user_id, "user_type": user_type}
        logger.info(f"Token verification successful: {result}")
        return result

    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error in token verification: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# Helper functions for role-based access
def require_admin(token_data: dict = Depends(verify_token)) -> int:
    logger.info(f"Admin access check for: {token_data}")

    if token_data["user_type"] != "admin":
        logger.error(f"Access denied - user_type is '{token_data['user_type']}', expected 'admin'")
        raise HTTPException(status_code=403, detail="Admin access required")

    user_id = token_data["user_id"]
    logger.info(f"Admin access granted for user_id: {user_id}")
    return user_id


def require_teacher(token_data: dict = Depends(verify_token)) -> int:
    logger.info(f"Teacher access check for: {token_data}")

    if token_data["user_type"] != "teacher":
        logger.error(f"Access denied - user_type is '{token_data['user_type']}', expected 'teacher'")
        raise HTTPException(status_code=403, detail="Teacher access required")

    user_id = token_data["user_id"]
    logger.info(f"Teacher access granted for user_id: {user_id}")
    return user_id
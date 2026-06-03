"""JWT helpers."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = str(os.getenv("SECRET_KEY") or "")
ALGORITHM = str(os.getenv("ALGORITHM") or "HS256")
TOKEN_EXPIRE = int(os.getenv("TOKEN_EXPIRE", 7200))


def create_access_token(data: Dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    openid = payload.get("openid")
    if not openid:
        raise HTTPException(status_code=401, detail="invalid token")
    return str(openid)


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    if not payload or not payload.get("openid"):
        raise HTTPException(status_code=401, detail="invalid token")
    return payload


async def get_current_user_ws(websocket: WebSocket) -> str:
    token = websocket.headers.get("Authorization")
    if not token:
        await websocket.send_json({"role": "end", "content": "invalid token", "code": 401})
        await websocket.close()
        return "401"

    token = token.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await websocket.send_json({"role": "end", "content": "invalid token", "code": 401})
        await websocket.close()
        return "401"

    return str(payload.get("openid") or "401")

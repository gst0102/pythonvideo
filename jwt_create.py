from jose import jwt,JWTError
import os
from dotenv import load_dotenv
from typing import Dict,Any
from datetime import datetime,timedelta,timezone
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi import Depends,HTTPException,WebSocket

load_dotenv()

SECRET_KEY = str(os.getenv('SECRET_KEY'))
ALGORITHM = str(os.getenv('ALGORITHM'))
TOKEN_EXPIRE = int(os.getenv('TOKEN_EXPIRE',7200))

# 生成加密的token,{'openid':'wjdsufuuf'}
def create_access_token(data:Dict[str,Any]) -> str:
  # 浅拷贝
  to_enclde = data.copy()
  # 计算过期时间
  expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE)
  to_enclde.update({'exp':expire})
  # 生成token
  encoded_jwt = jwt.encode(to_enclde,SECRET_KEY,algorithm=ALGORITHM)
  return encoded_jwt

# 解析token，获取用户openid
security = HTTPBearer()
async def get_current_user(
    cregentials:HTTPAuthorizationCredentials=Depends(security)
)-> str:
  # 获取到token
  token = cregentials.credentials
  # print(token)
  try:
    payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
  except JWTError:
    raise HTTPException(
      status_code=401,
      detail='token不合法'
    )
  if not payload:
    raise HTTPException(
      status_code=401,
      detail='token不合法'
    )
  # print(payload)
  return payload['openid']

# 解析token，websocket专用
async def get_current_user_ws(websocket:WebSocket)-> str:
  token = websocket.headers.get('Authorization')
  if not token:
    await websocket.send_json({'role':'end','content':'token不合法','code':401})
    await websocket.close()
    return '401'
  # 取出token
  token = token.replace('Bearer ','')
  try:
    payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
  except JWTError:
    await websocket.send_json({'role':'end','content':'token不合法','code':401})
    await websocket.close()
    return '401'
  return payload['openid']

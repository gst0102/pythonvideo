from fastapi import APIRouter,Depends,UploadFile
from core.response import response
from schemas.user import UserLoginValidate
import os
from dotenv import load_dotenv
import httpx
from typing import cast
from uuid import uuid4
from jwt_create import create_access_token, get_current_user
from schemas.user import UserLoginValidate


router = APIRouter(prefix="/user",tags=["用户相关接口"])
load_dotenv()

APPID = os.getenv('APPID')
SECRET = os.getenv('SECRET')
IP = os.getenv('IP')
PORT = os.getenv('PORT')

code2Session = 'https://api.weixin.qq.com/sns/jscode2session'


@router.post("/user_login",summary='用户相关')
async def login(req:UserLoginValidate):
    params = {
      'appid':APPID,
      'secret':SECRET,
      'js_code':req.code,
      'grant_type':'authorization_code'
    }
    async with httpx.AsyncClient() as client:
      r = await client.get(code2Session,params=params)
    data = r.json()
    if "errcode" in data:
      return response([], 400, data)
    openid:str = data.get('openid')
    usertoken = create_access_token({'openid':openid})

    return response({'avatar':req.avatar,'nickname':req.nickname,'usertoken':usertoken})




# 图片上传（头像上传）
@router.post('/upload_image')
async def upload_image(file:UploadFile):
  print(file)
  # 文件大小
  MAX_FILE_SIZE = 10 * 1024 * 1024
  # 文件类型
  ALLOWED_CONTENT_TYPES = {'image/jpeg','image/png','image/webp'}
  # 校验类型
  if file.content_type not in ALLOWED_CONTENT_TYPES:
    return response([],422,'请上传合法的头像')
  # 校验大小
  if cast(int,file.size) > MAX_FILE_SIZE:
    return response([],422,'上传的头像太大')
  # 重命名文件
  original_ext = os.path.splitext(cast(str,file.filename))[1]
  new_filename = f"{uuid4().hex}{original_ext}"
  # os.getcwd() 文件当前的目录 建立新的文件夹
  save_folder = os.path.join(os.getcwd(),'image')
  file_path = os.path.join(save_folder,new_filename)
  print('PORT',PORT)
  # 存入文件
  with open(file_path,'wb') as f:
    content = await file.read()
    f.write(content)
  return response({'upload_image':f"{IP}:{PORT}/image/{new_filename}"})


#测试解析token
@router.get('/get_token')
async def get_token(
  user_id:str = Depends(get_current_user)
):
  print('token123',user_id)
  return response({'token':user_id})
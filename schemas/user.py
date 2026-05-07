from pydantic import BaseModel,field_validator
from typing import Any
# 登陆接口
'''
传递参数
code:code值
avatar:头像
nickname:昵称

'''
class UserLoginValidate(BaseModel):
    # 如果每个字段都需要校验,使用field
    code:str
    avatar:str
    nickname:str

    # 自动参数校验v:当前字段值,info:当前字段名mode="before" 把值解析目标类型
    @field_validator("code","avatar","nickname",mode="before")
    @classmethod
    def check_not_empty(cls,v:Any,info:Any)->Any:
        if not isinstance(v,str) or not v.strip():
            raise ValueError(f"{info.field_name}必填")
        return v

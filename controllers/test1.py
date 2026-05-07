from fastapi import Request, HTTPException,APIRouter
from pydantic import BaseModel
import json
from core.wepay import WeChatPayV3 # 引入上面的类
from dotenv import load_dotenv
import os



router = APIRouter(prefix="/wxpay", tags=["微信支付相关接口"])

# 加载环境变量
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 初始化配置 (建议放入环境变量)
config = {
    "mch_id": os.getenv('mchid'),
    "app_id": os.getenv('APPID'),
    "api_v3_key": os.getenv('APIv3'),
    "private_key_path": os.path.join(BASE_DIR, 'certs', 'apiclient_key.pem'), 
    "serial_no": os.getenv('serial_no'), 
    "notify_url": "https://www.baidu.com/",
}

wx_pay = WeChatPayV3(**config)

class OrderRequest(BaseModel):
    openid: str
    total: int  # 单位：分
    description: str

@router.post("/api/create_order")
async def create_order(req: OrderRequest):
    """
    1. 生成商户订单号 (建议用数据库自增ID或UUID)
    2. 调用微信统一下单
    3. 生成前端所需的签名参数
    """
    import uuid
    out_trade_no = f"order_{uuid.uuid4().hex[:12]}" # 简单示例
    
    try:
        # 1. 请求微信获取 prepay_id
        prepay_id = wx_pay.create_jsapi_order(
            description=req.description,
            out_trade_no=out_trade_no,
            total=req.total,
            openid=req.openid,
            notify_url=config["notify_url"]
        )
        
        # 2. 生成前端调起支付需要的参数
        pay_params = wx_pay.get_jsapi_params(prepay_id)
        
        return {"code": 200, "msg": "success", "data": pay_params}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/pay/notify")
async def pay_notify(request: Request):
    """
    处理微信支付回调
    注意：V3 版本的回调 body 是加密的，需要解密
    """
    # 1. 获取请求头
    headers = request.headers
    # 2. 获取请求体
    body = await request.body()
    
    # 这里需要实现解密逻辑 (使用 api_v3_key 解密 resource ciphertext)
    # 伪代码逻辑：
    # 1. 验证签名 (使用微信公钥验证 Wechatpay-Signature)
    # 2. 解密 body['resource']['ciphertext']
    # 3. 获取 out_trade_no 和 trade_state
    
    # 模拟解密后的数据
    # result_data = json.loads(decrypt_body)
    
    # if result_data['trade_state'] == 'SUCCESS':
    #     更新数据库订单状态
    
    return {"code": "SUCCESS", "message": "成功"}
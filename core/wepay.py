import time
import random
import string
import json
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import httpx
import requests

class WeChatPayV3:
    def __init__(self, mch_id, app_id, api_v3_key, private_key_path, serial_no,notify_url=None):
        self.mch_id = mch_id
        self.app_id = app_id
        self.api_v3_key = api_v3_key
        self.serial_no = serial_no
        self.notify_url = notify_url
        
        try:
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        except FileNotFoundError:
            raise ValueError(f'私钥文件不存在: {private_key_path}')
        except PermissionError:
            raise PermissionError(f'无权限读取私钥文件: {private_key_path}')
        except Exception as e:
            raise ValueError(f'加载私钥失败: {str(e)}')



    def _create_signature(self,message: str) -> str:
        """生成签名"""
        # sign_str = f"{method}\n{url}\n{timestamp}\n{nonce}\n{body}\n"

        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode('utf-8')

       
    def _get_authorization(self, method, url, body, timestamp, nonce):
        """构建 HTTP 请求头中的 Authorization 字段"""
        # 构造签名字符串：方法\nURL\n时间戳\n随机串\n报文主体\n
        sign_str = f"{method}\n{url}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._create_signature(sign_str)
        auth_header = (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
            f'nonce_str="{nonce}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.serial_no}"'
        )
        return auth_header

    def create_jsapi_order(self, description, out_trade_no, total, openid, notify_url):
        """
        统一下单接口
        total: 金额，单位分
        """
        print("SDK内部的AppID:", self.app_id) # 看看这里是不是 None
        url = "https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi"
        # 注意：这里需要去掉域名后的参数部分，只保留路径作为签名URL的一部分，具体视微信文档要求
        # 实际签名时 URL 通常包含 query 参数，但微信支付 V3 签名规则中 URL 为请求的完整 URI (不含域名)
        # 这里简化处理，实际生产建议封装完整的 URI 构造
        
        data = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description,
            "out_trade_no": out_trade_no,
            "attach": "NULL", # 订单id
            "notify_url": self.notify_url,
            "amount": {
                "total": total,
                "currency": "CNY"
            },
            "payer": {
                "openid": openid
            }
        }
        
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        timestamp = str(int(time.time()))

        nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        # 构造签名字符串所需的 URL 部分 (不包含域名)
        # 注意：这里假设 url 变量包含完整路径，实际需根据 httpx 请求格式调整
        sign_url = "/v3/pay/transactions/jsapi" 
        
        sign_str = f"POST\n{sign_url}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._create_signature(sign_str)
        auth_header = (
                f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'nonce_str="{nonce}",'
                f'signature="{signature}",'
                f'timestamp="{timestamp}",'
                f'serial_no="{self.serial_no}"'
                )
        
        headers = {
            "Accept": "application/json",
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }
        with requests.Session() as session:
            # ✅ 关键点：使用 json=data
            # requests 会自动把 data 字典序列化成 JSON 字符串发送
            response = session.post(url, data=body, headers=headers)
            
            print("状态码:", response.status_code)
            print("响应内容:", response.text)
            
            # 3. 处理结果
            if response.status_code == 200:
                print("下单成功:", response.json())
                return response.json().get("prepay_id")
            else:
                # 尝试解析错误信息
                try:
                    error_info = response.json()
                    print("错误详情:", error_info)
                except:
                    print("非JSON错误:", response.text)
                return {"error": "下单失败"}
      
    def get_jsapi_params(self, prepay_id):
        """
        生成前端调起支付所需的参数和二次签名
        """
        timestamp = str(int(time.time()))
        nonce_str = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        package = f"prepay_id={prepay_id}"
        
        # 小程序/JSAPI 调起支付的签名字符串格式
        # appid\n时间戳\n随机字符串\nprepay_id\n
        sign_str = f"{self.app_id}\n{timestamp}\n{nonce_str}\n{package}\n"
        pay_sign = self._create_signature(sign_str)
        print("二次签名:", pay_sign)
        return {
            "appId": self.app_id,
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": pay_sign
        }

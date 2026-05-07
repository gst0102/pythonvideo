# core/certKey.py

import os
import base64
from typing import Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
import redis.asyncio as redis


class WechatCertManager:
    """微信证书管理器（支持微信支付公钥模式）"""
    
    def __init__(self, redis_pool: redis.ConnectionPool = None):
        self.redis_pool = redis_pool
        self._memory_cache = {}  # 内存缓存：存储商户证书
        self._wechatpay_public_key = None  # 微信支付公钥（用于验签）
        
    def _get_cert_from_file(self) -> Tuple[Optional[str], Optional[str]]:
        """从本地文件读取商户证书"""
        try:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            public_cert_path = os.path.join(BASE_DIR, 'certs', 'apiclient_cert.pem')
            
            print(f"📄 尝试读取商户证书文件: {public_cert_path}")
            print(f"📁 文件是否存在: {os.path.exists(public_cert_path)}")
            
            if not os.path.exists(public_cert_path):
                print(f"❌ 商户证书文件不存在: {public_cert_path}")
                return None, None
            
            with open(public_cert_path, "rb") as f:
                cert_pem = f.read().decode('utf-8')
                
                print(f"✅ 商户证书文件读取成功，长度: {len(cert_pem)}")
                
                # 获取证书序列号
                cert = x509.load_pem_x509_certificate(
                    cert_pem.encode('utf-8'),
                    backend=default_backend()
                )
                serial_num = format(cert.serial_number, 'x').upper()
                
                print(f"📜 商户证书序列号: {serial_num}")
                
                return serial_num, cert_pem
                
        except Exception as e:
            print(f"❌ 读取商户证书文件失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None
    
    # core/certKey.py

    def _load_wechatpay_public_key(self) -> Optional[str]:
        """从本地文件加载微信支付公钥（用于验签）"""
        try:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            public_key_path = os.path.join(BASE_DIR, 'certs', 'pub_key.pem')  # ← 改这里
            
            print(f"📄 尝试读取微信支付公钥文件: {public_key_path}")
            print(f"📁 文件是否存在: {os.path.exists(public_key_path)}")
            
            if not os.path.exists(public_key_path):
                print(f"❌ 微信支付公钥文件不存在: {public_key_path}")
                print(f"💡 请前往微信商户平台 → API安全 → 微信支付公钥 下载")
                return None
            
            with open(public_key_path, 'rb') as f:
                public_key_pem = f.read().decode('utf-8')
                print(f"✅ 微信支付公钥加载成功，长度: {len(public_key_pem)}")
                return public_key_pem
            
        except Exception as e:
            print(f"❌ 加载微信支付公钥失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端（从连接池）"""
        if self.redis_pool:
            return redis.Redis(connection_pool=self.redis_pool, decode_responses=True)
        return None
    
    async def get_certificate(self, serial: str) -> Optional[str]:
        """根据序列号获取商户证书（用于请求签名）"""
        
        # 1. 先从内存缓存取
        if serial in self._memory_cache:
            print(f"✅ 从内存缓存获取商户证书: {serial[:20]}...")
            return self._memory_cache[serial]
        
        # 2. 从 Redis 取
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                cert_pem = await redis_client.get(f"wechat:cert:{serial}")
                if cert_pem:
                    print(f"✅ 从 Redis 获取商户证书: {serial[:20]}...")
                    # 同步到内存缓存
                    self._memory_cache[serial] = cert_pem
                    await redis_client.aclose()
                    return cert_pem
            except Exception as e:
                print(f"⚠️ Redis 读取失败: {str(e)}")
            finally:
                try:
                    await redis_client.aclose()
                except:
                    pass
        
        # 3. 从文件读取
        file_serial, cert_pem = self._get_cert_from_file()
        if file_serial and file_serial.upper() == serial.upper() and cert_pem:
            print(f"✅ 从文件获取商户证书: {serial[:20]}...")
            # 存入内存缓存
            self._memory_cache[serial] = cert_pem
            
            # 存入 Redis 缓存
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    await redis_client.setex(f"wechat:cert:{serial}", 86400, cert_pem)
                    print(f"✅ 商户证书缓存到 Redis")
                except Exception as e:
                    print(f"⚠️ Redis 写入失败: {str(e)}")
                finally:
                    try:
                        await redis_client.aclose()
                    except:
                        pass
            return cert_pem
        
        print(f"❌ 未找到商户证书: {serial[:20]}...")
        return None
    
    def get_wechatpay_public_key(self) -> Optional[str]:
        """获取微信支付公钥（用于验签）"""
        
        # 1. 先从内存缓存取
        if self._wechatpay_public_key:
            print("✅ 从内存缓存获取微信支付公钥")
            return self._wechatpay_public_key
        
        # 2. 从文件加载
        public_key_pem = self._load_wechatpay_public_key()
        if public_key_pem:
            # 缓存到内存
            self._wechatpay_public_key = public_key_pem
            
            # 异步缓存到 Redis（不阻塞）
            import asyncio
            asyncio.create_task(self._cache_public_key_to_redis(public_key_pem))
            
            return public_key_pem
        
        return None
    
    async def _cache_public_key_to_redis(self, public_key_pem: str):
        """将微信支付公钥缓存到 Redis"""
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.setex("wechat:public_key", 86400, public_key_pem)
                print("✅ 微信支付公钥缓存到 Redis")
            except Exception as e:
                print(f"⚠️ Redis 缓存公钥失败: {str(e)}")
            finally:
                try:
                    await redis_client.aclose()
                except:
                    pass


# 全局证书管理器实例
_cert_manager: Optional[WechatCertManager] = None


def init_wechat_cert_manager(redis_pool: redis.ConnectionPool):
    """
    初始化微信证书管理器（同步版本）

    Args:
        redis_pool: Redis 连接池（从 databaseApi 导入）
    """
    global _cert_manager
    _cert_manager = WechatCertManager(redis_pool)
    print("✅ 微信证书管理器初始化完成")
    
    # 加载商户证书
    try:
        serial_no, cert_pem = _cert_manager._get_cert_from_file()
        if serial_no and cert_pem:
            _cert_manager._memory_cache[serial_no] = cert_pem
            print(f"✅ 商户证书已加载到内存缓存，序列号: {serial_no}")
    except Exception as e:
        print(f"⚠️ 加载商户证书失败: {e}")
    
    # 加载微信支付公钥
    try:
        public_key = _cert_manager._load_wechatpay_public_key()
        if public_key:
            _cert_manager._wechatpay_public_key = public_key
            print(f"✅ 微信支付公钥已加载到内存缓存")
        else:
            print(f"⚠️ 微信支付公钥加载失败，回调验签将不可用")
    except Exception as e:
        print(f"⚠️ 加载微信支付公钥失败: {e}")
    
    return _cert_manager


async def init_wechat_cert_manager_async(redis_pool: redis.ConnectionPool):
    """
    初始化微信证书管理器（异步版本 - 在 FastAPI lifespan 中使用）

    Args:
        redis_pool: Redis 连接池（从 databaseApi 导入）
    """
    global _cert_manager
    _cert_manager = WechatCertManager(redis_pool)
    print("✅ 微信证书管理器初始化完成")
    
    # 加载商户证书
    try:
        serial_no, cert_pem = _cert_manager._get_cert_from_file()
        if serial_no and cert_pem:
            _cert_manager._memory_cache[serial_no] = cert_pem
            print(f"✅ 商户证书已加载到内存缓存，序列号: {serial_no}")
            
            # 也加载到 Redis
            if redis_pool:
                redis_client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
                try:
                    await redis_client.setex(f"wechat:cert:{serial_no}", 86400, cert_pem)
                    print(f"✅ 商户证书已加载到 Redis 缓存")
                except Exception as e:
                    print(f"⚠️ 商户证书加载到 Redis 失败: {e}")
                finally:
                    await redis_client.aclose()
    except Exception as e:
        print(f"⚠️ 加载商户证书失败: {e}")
    
    # 加载微信支付公钥
    try:
        public_key = _cert_manager._load_wechatpay_public_key()
        if public_key:
            _cert_manager._wechatpay_public_key = public_key
            print(f"✅ 微信支付公钥已加载到内存缓存")
            
            # 也加载到 Redis
            if redis_pool:
                redis_client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
                try:
                    await redis_client.setex("wechat:public_key", 86400, public_key)
                    print(f"✅ 微信支付公钥已加载到 Redis 缓存")
                except Exception as e:
                    print(f"⚠️ 微信支付公钥加载到 Redis 失败: {e}")
                finally:
                    await redis_client.aclose()
        else:
            print(f"⚠️ 微信支付公钥加载失败，回调验签将不可用")
    except Exception as e:
        print(f"⚠️ 加载微信支付公钥失败: {e}")
    
    return _cert_manager


def get_cert_manager() -> Optional[WechatCertManager]:
    """获取证书管理器实例"""
    return _cert_manager


async def verify_signature(sign_str: str, signature: str, serial: str) -> bool:
    """
    验证微信支付回调签名（使用微信支付公钥）
    
    Args:
        sign_str: 待签名字符串
        signature: Base64编码的签名
        serial: 微信支付公钥ID（用于日志，验签时不强制匹配）
    """
    if _cert_manager is None:
        print("❌ 证书管理器未初始化")
        return False
    
    print(f"🔑 回调使用的公钥ID: {serial}")
    
    try:
        # 获取微信支付公钥
        public_key_pem = _cert_manager.get_wechatpay_public_key()
        
        if not public_key_pem:
            print("❌ 无法获取微信支付公钥")
            print("💡 请确保已从微信商户平台下载微信支付公钥并保存为 certs/wechatpay_public_key.pem")
            return False
        
        # 加载公钥
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        
        # 解码签名
        signature_bytes = base64.b64decode(signature)
        
        # 验证签名
        public_key.verify(
            signature_bytes,
            sign_str.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        print("✅ 签名验证成功（使用微信支付公钥）")
        return True
        
    except Exception as e:
        print(f"❌ 签名验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
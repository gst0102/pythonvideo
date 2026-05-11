#!/bin/bash

# SSL 证书自动续期脚本
# 使用 Let's Encrypt 免费证书
# 建议添加到 crontab: 0 3 * * * /path/to/renew-ssl.sh >> /var/log/ssl-renew.log 2>&1

DOMAIN="your-domain.com"
EMAIL="250667571@qq.com"
WEBROOT="/var/www/certbot"
SSL_DIR="./nginx/ssl"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始检查 SSL 证书..."

# 使用 certbot 续期证书
docker run --rm \
    -v ${SSL_DIR}:/etc/letsencrypt \
    -v ${WEBROOT}:/var/www/certbot \
    certbot/certbot renew \
    --webroot \
    -w /var/www/certbot \
    --email ${EMAIL} \
    --agree-tos \
    --no-eff-email \
    --force-renewal

if [ $? -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 证书续期成功！"
    
    # 重载 Nginx 使新证书生效
    docker exec video-service-nginx nginx -s reload
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Nginx 已重载配置"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 证书续期失败！"
    exit 1
fi

#!/bin/bash
set -e

DOMAIN="${DOMAIN:-your-domain.com}"
EMAIL="${EMAIL:-250667571@qq.com}"
WEBROOT_DIR="$(pwd)/www/certbot"
SSL_DIR="$(pwd)/nginx/ssl"
CERT_PATH="${SSL_DIR}/live/${DOMAIN}/fullchain.pem"

if [ -f "$CERT_PATH" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 证书已存在，尝试续期..."
    docker run --rm \
        -v "${SSL_DIR}:/etc/letsencrypt" \
        -v "${WEBROOT_DIR}:/var/www/certbot" \
        certbot/certbot renew \
        --webroot -w /var/www/certbot \
        --quiet

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 续期成功"
        docker exec video-service-nginx nginx -s reload 2>/dev/null || echo "Nginx 重载失败，可能尚未启动"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 续期失败" >&2
        exit 1
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 证书不存在，首次申请..."
    mkdir -p "$SSL_DIR" "$WEBROOT_DIR"

    docker run --rm \
        -p 80:80 \
        -v "${SSL_DIR}:/etc/letsencrypt" \
        -v "${WEBROOT_DIR}:/var/www/certbot" \
        certbot/certbot certonly \
        --standalone \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email \
        -d "${DOMAIN}"

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 证书申请成功"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 证书申请失败" >&2
        exit 1
    fi
fi
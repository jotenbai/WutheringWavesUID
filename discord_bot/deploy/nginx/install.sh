#!/bin/bash
# 在 VPS 上执行: bash ~/nginx-setup/install.sh
# 需要 sudo 密码；DNS 须已解析 core.jotenbai.moe → 本机
set -euo pipefail

DOMAIN=core.jotenbai.moe
CONF_SRC="$HOME/nginx-setup/core.jotenbai.moe.conf"

if [[ ! -f "$CONF_SRC" ]]; then
  echo "缺少配置文件: $CONF_SRC"
  exit 1
fi

echo "[1/5] 安装 nginx + certbot ..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx

echo "[2/5] 写入站点配置 ..."
sudo cp "$CONF_SRC" "/etc/nginx/sites-available/$DOMAIN"
sudo ln -sfn "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
sudo rm -f /etc/nginx/sites-enabled/default

echo "[3/5] 检查配置并重载 ..."
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo "[4/5] 申请 Let's Encrypt 证书（需 DNS 已指向本机）..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect

echo "[5/5] 完成。自检："
curl -sI "https://$DOMAIN/app/" | head -8 || true
echo
echo "浏览器打开: https://$DOMAIN/app/"
echo "之后可在 Cloudflare 把 core 改为橙色 Proxied；SSL/TLS 模式选 Full 或 Full (strict)。"

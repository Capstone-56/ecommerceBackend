#!/bin/bash

echo "=== 502 Bad Gateway Debug Script ==="
echo "Date: $(date)"
echo

echo "=== 1. Service Status ==="
echo "--- Nginx Status ---"
sudo systemctl status nginx --no-pager
echo
echo "--- Gunicorn Service Status ---"
sudo systemctl status gunicorn.service --no-pager
echo
echo "--- Gunicorn Socket Status ---"
sudo systemctl status gunicorn.socket --no-pager
echo

echo "=== 2. Socket File Check ==="
echo "--- Socket File Permissions ---"
ls -la /run/gunicorn.sock 2>/dev/null || echo "Socket file does not exist!"
echo
echo "--- Socket Directory Permissions ---"
ls -la /run/ | grep gunicorn
echo

echo "=== 3. Port and Process Check ==="
echo "--- Processes listening on sockets ---"
sudo netstat -xlp | grep gunicorn
echo
echo "--- Nginx processes ---"
ps aux | grep nginx
echo
echo "--- Gunicorn processes ---"
ps aux | grep gunicorn
echo

echo "=== 4. Recent Error Logs ==="
echo "--- Nginx Error Log (last 20 lines) ---"
sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo "No nginx error log found"
echo
echo "--- Gunicorn Service Log (last 20 lines) ---"
sudo journalctl -u gunicorn.service --no-pager -n 20
echo

echo "=== 5. Configuration Check ==="
echo "--- Nginx Config Test ---"
sudo nginx -t
echo
echo "--- Django Settings Check ---"
cd /home/ubuntu/ecommerceBackend
source /home/ubuntu/env/bin/activate
python manage.py check --deploy 2>/dev/null || echo "Django check failed"
echo

echo "=== 6. Test Socket Connection ==="
echo "--- Curl Socket Test ---"
curl --unix-socket /run/gunicorn.sock http://localhost/ -I 2>/dev/null || echo "Socket connection failed"
echo

echo "=== Debug Complete ==="

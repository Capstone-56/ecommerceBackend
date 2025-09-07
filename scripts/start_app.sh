#!/usr/bin/bash 

# Update ALLOWED_HOSTS in Django settings
sed -i 's/ALLOWED_HOSTS = \[\]/ALLOWED_HOSTS = ["3.25.193.75", "localhost", "127.0.0.1"]/' /home/ubuntu/ecommerceBackend/ecommerceBackend/settings.py

# Activate virtual environment and run Django commands
cd /home/ubuntu/ecommerceBackend
source /home/ubuntu/env/bin/activate

python manage.py makemigrations     
python manage.py migrate 
python manage.py collectstatic --noinput

# Restart services
sudo systemctl daemon-reload
sudo systemctl restart gunicorn.socket
sudo systemctl restart gunicorn.service
sudo systemctl restart nginx
#sudo tail -f /var/log/nginx/error.log
#sudo systemctl reload nginx
#sudo tail -f /var/log/nginx/error.log
#sudo nginx -t
#sudo systemctl restart gunicorn
#sudo systemctl status gunicorn
#sudo systemctl status nginx
# Check the status
#systemctl status gunicorn
# Restart:
#systemctl restart gunicorn
#sudo systemctl status nginx

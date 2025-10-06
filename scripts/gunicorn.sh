#!/usr/bin/bash
sudo cp /home/ubuntu/ecommerceBackend/gunicorn/gunicorn.socket  /etc/systemd/system/gunicorn.socket
sudo cp /home/ubuntu/ecommerceBackend/gunicorn/gunicorn.service  /etc/systemd/system/gunicorn.service

sudo systemctl daemon-reload
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
sudo systemctl start gunicorn.service
sudo systemctl enable gunicorn.service

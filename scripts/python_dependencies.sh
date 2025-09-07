#!/usr/bin/env bash

# Create virtual environment if it doesn't exist
if [ ! -d "/home/ubuntu/env" ]; then
    echo "Creating virtual environment..."
    cd /home/ubuntu
    python3 -m venv env
fi

# Activate virtual environment and install/upgrade packages
echo "Installing Python dependencies..."
source /home/ubuntu/env/bin/activate
pip install --upgrade pip
pip install -r /home/ubuntu/ecommerceBackend/requirements.txt

# Verify gunicorn installation
echo "Verifying gunicorn installation..."
gunicorn --version

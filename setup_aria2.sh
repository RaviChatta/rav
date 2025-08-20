#!/bin/bash

# Aria2c Setup Script for Telegram Bot
echo "Setting up aria2c for faster downloads/uploads..."

# Install aria2
sudo apt update
sudo apt install -y aria2 python3-pip

# Install python aria2c library
pip3 install python-aria2c

# Create directories
mkdir -p ~/downloads ~/.config/aria2

# Create aria2 configuration
cat > ~/.config/aria2/aria2.conf << EOL
# Aria2c Configuration for Telegram Bot
dir=~/downloads
max-concurrent-downloads=3
max-connection-per-server=16
split=16
min-split-size=1M
max-overall-download-limit=0
max-download-limit=0
continue=true
file-allocation=prealloc
log-level=warn
log=~/aria2.log
enable-rpc=true
rpc-listen-all=true
rpc-listen-port=6800
rpc-allow-origin-all=true
rpc-secret=$(openssl rand -hex 16)
max-overall-upload-limit=0
max-upload-limit=0
seed-ratio=0.0
seed-time=0
EOL

# Create systemd service file
sudo cat > /etc/systemd/system/aria2.service << EOL
[Unit]
Description=Aria2c Download Manager
After=network.target

[Service]
User=$USER
Type=forking
ExecStart=/usr/bin/aria2c --conf-path=/home/$USER/.config/aria2/aria2.conf -D
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

# Start and enable aria2 service
sudo systemctl daemon-reload
sudo systemctl enable aria2.service
sudo systemctl start aria2.service

# Get the secret key for configuration
SECRET_KEY=$(grep 'rpc-secret' ~/.config/aria2/aria2.conf | cut -d'=' -f2)
echo "Aria2c setup complete!"
echo "Add this to your config.py:"
echo "ARIA2_SECRET = \"$SECRET_KEY\""

# Set permissions
sudo chown -R $USER:$USER ~/downloads ~/.config/aria2

echo "Aria2c is now running as a system service!"

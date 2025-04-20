#!/bin/bash

# Exit on error
set -e

echo "Starting server setup..."

# Server details
SERVER="root@45.77.155.59"
PORT="61208"
INSTALL_DIR="/opt/reminder-bot"

# Create necessary directories on the server
echo "Creating directories on the server..."
ssh -p $PORT $SERVER "mkdir -p $INSTALL_DIR && chown -R root:root $INSTALL_DIR"

# Copy files to the server
echo "Copying files to the server..."
rsync -avz -e "ssh -p $PORT" --exclude 'venv' --exclude '.git' --exclude 'reminders.db' --exclude '.DS_Store' . $SERVER:$INSTALL_DIR/

# Make deploy script executable
echo "Making deploy script executable..."
ssh -p $PORT $SERVER "chmod +x $INSTALL_DIR/deploy.sh"

# Run the deployment script on the server
echo "Running deployment script on the server..."
ssh -p $PORT $SERVER "cd $INSTALL_DIR && ./deploy.sh"

# Create systemd service on the server
echo "Creating systemd service..."
ssh -p $PORT $SERVER "cat > /etc/systemd/system/reminder-bot.service << EOL
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/reminder_bot.py
Restart=always
RestartSec=10
MemoryMax=512M
MemorySwapMax=0
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOL"

# Reload systemd and restart the service
echo "Reloading systemd and restarting service..."
ssh -p $PORT $SERVER "systemctl daemon-reload && systemctl restart reminder-bot"

echo "Server setup complete!"
echo "Please check the server logs for any errors:"
echo "ssh -p $PORT $SERVER 'journalctl -u reminder-bot -f'" 
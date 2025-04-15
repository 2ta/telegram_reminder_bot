#!/bin/bash

# Exit on error
set -e

echo "Starting deployment of Telegram Reminder Bot..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Install dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Create installation directory
INSTALL_DIR="/opt/reminder-bot"
echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p $INSTALL_DIR

# Clone repository
echo "Cloning repository..."
git clone https://github.com/2ta/telegram_reminder_bot.git $INSTALL_DIR

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv $INSTALL_DIR/venv

# Install Python dependencies
echo "Installing Python dependencies..."
$INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/reminder-bot.service << EOF
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/reminder_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Set permissions
echo "Setting permissions..."
chown -R root:root $INSTALL_DIR
chmod -R 755 $INSTALL_DIR

echo "Installation complete!"
echo "Please complete the following steps:"
echo "1. Copy config.py.template to config.py:"
echo "   cp $INSTALL_DIR/config.py.template $INSTALL_DIR/config.py"
echo "2. Edit config.py and add your tokens"
echo "3. Start the service:"
echo "   systemctl start reminder-bot"
echo "4. Enable the service to start on boot:"
echo "   systemctl enable reminder-bot"
echo "5. Check status: sudo systemctl status reminder-bot" 
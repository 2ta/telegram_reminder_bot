#!/bin/bash

# Exit on error
set -e

echo "Starting deployment..."

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    ffmpeg \
    python3-pip \
    python3-venv \
    build-essential \
    python3-dev \
    portaudio19-dev

# Create necessary directories
mkdir -p data logs

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install faster-whisper explicitly
pip install faster-whisper

# Ensure .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please update .env with your Telegram bot token and other settings"
fi

# Set proper permissions
chmod 600 .env
chmod 755 data logs

# Create database if it doesn't exist
if [ ! -f "data/reminders.db" ]; then
    echo "Creating database..."
    touch data/reminders.db
    chmod 644 data/reminders.db
fi

# Create log file if it doesn't exist
if [ ! -f "logs/reminder_bot.log" ]; then
    echo "Creating log file..."
    touch logs/reminder_bot.log
    chmod 644 logs/reminder_bot.log
fi

# Restart the bot service if it exists
if systemctl is-active --quiet reminder-bot; then
    echo "Restarting reminder-bot service..."
    systemctl restart reminder-bot
fi

echo "Deployment complete!"
echo "Make sure to check the logs at logs/reminder_bot.log for any issues." 
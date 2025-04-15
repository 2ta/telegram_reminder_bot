#!/bin/bash

# Exit on error
set -e

echo "Starting server setup..."

# Server details
SERVER="ssh@45.77.155.59"
PORT="61208"
INSTALL_DIR="/opt/reminder-bot"

# Create necessary directories on the server
echo "Creating directories on the server..."
ssh -p $PORT $SERVER "sudo mkdir -p $INSTALL_DIR && sudo chown -R ssh:ssh $INSTALL_DIR"

# Copy files to the server
echo "Copying files to the server..."
rsync -avz -e "ssh -p $PORT" --exclude 'venv' --exclude '.git' --exclude 'reminders.db' --exclude '.DS_Store' . $SERVER:$INSTALL_DIR/

# Run the deployment script on the server
echo "Running deployment script on the server..."
ssh -p $PORT $SERVER "cd $INSTALL_DIR && sudo ./deploy.sh"

echo "Server setup complete!"
echo "Please check the server logs for any errors:"
echo "ssh -p $PORT $SERVER 'journalctl -u reminder-bot -f'" 
# Telegram Reminder Bot

A Telegram bot that helps you set reminders using voice or text messages. The bot supports Persian language and can understand natural language input.

## Features

- Set reminders using voice or text messages
- Natural language processing in Persian
- Support for date and time expressions
- Multiple reminder management
- Timezone support

## Installation

### Automated Installation

1. Download the deployment script:
```bash
wget https://raw.githubusercontent.com/2ta/telegram_reminder_bot/main/deploy.sh
```

2. Make the script executable:
```bash
chmod +x deploy.sh
```

3. Run the script as root:
```bash
sudo ./deploy.sh
```

4. After installation, you need to:
   - Copy `config.py.template` to `config.py`
   - Edit `config.py` and add your Telegram bot token and Hugging Face token
   - Start the service: `sudo systemctl start reminder-bot`

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/2ta/telegram_reminder_bot.git
cd telegram_reminder_bot
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the config template:
```bash
cp config.py.template config.py
```

5. Edit `config.py` and add your tokens:
   - Get a Telegram bot token from [@BotFather](https://t.me/BotFather)
   - Get a Hugging Face token from [huggingface.co](https://huggingface.co)

6. Run the bot:
```bash
python reminder_bot.py
```

## Usage

1. Start a chat with your bot on Telegram
2. Send a voice message or text with your reminder
3. The bot will process your message and set the reminder
4. You'll receive a notification when the reminder is due

### Examples

Text messages:
- "به من یادآوری کن که ساعت ۲ بعد از ظهر به مادرم زنگ بزنم"
- "فردا ساعت ۱۰ صبح جلسه دارم"
- "پس‌فردا ساعت ۳ عصر با دوستم قرار ملاقات دارم"

Voice messages:
- Say any of the above examples in Persian

## Configuration

The bot can be configured by editing the `config.py` file:

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `HUGGING_FACE_TOKEN`: Your Hugging Face token
- `DATABASE_PATH`: Path to the SQLite database
- `LOG_FILE`: Path to the log file
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `DEFAULT_TIMEZONE`: Default timezone for reminders
- `MAX_REMINDERS_PER_USER`: Maximum number of active reminders per user
- `REMINDER_CHECK_INTERVAL`: How often to check for due reminders (in seconds)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
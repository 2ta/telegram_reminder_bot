# Telegram Reminder Bot

A Persian-language Telegram bot for setting reminders with natural language processing.

## Features

- Set reminders using natural Persian language
- Support for recurring reminders (daily, weekly, monthly)
- Voice message support (converts voice to text)
- Persian calendar support
- Interactive buttons for confirmation and management
- Persistent storage using SQLite

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/reminder-bot-telegram.git
cd reminder-bot-telegram
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the bot:
- Copy `config.py.example` to `config.py`
- Update the tokens and settings in `config.py`

5. Run the bot:
```bash
python reminder_bot.py
```

## Usage

1. Start a chat with your bot on Telegram
2. Send a reminder message in Persian, for example:
   - "یادآوری کن فردا ساعت ۳ بعد از ظهر به مادرم زنگ بزنم"
   - "یادآوری کن ۲۶ فروردین ۱۴۰۴ ساعت ۲ بعد از ظهر جلسه دارم"

3. Use the interactive buttons to:
   - Confirm or reject reminders
   - Set reminder frequency
   - List all reminders
   - Delete reminders

## Project Structure

```
reminder-bot-telegram/
├── config.py           # Configuration settings
├── reminder_bot.py     # Main bot code
├── requirements.txt    # Python dependencies
├── data/              # Database and data files
├── logs/              # Log files
└── README.md          # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
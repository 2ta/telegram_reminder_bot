import os
import logging
import datetime
import re
from typing import Dict, List, Optional, Tuple, Union
import json
import requests
import tempfile

import pytz
import schedule
import time
import threading
import sqlite3
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, CallbackQueryHandler
import pkg_resources
from persian_tools import digits  # For handling Persian numbers
import jdatetime  # For Persian calendar conversion
from config import *  # Import all config settings
from dotenv import load_dotenv
from faster_whisper import WhisperModel
import asyncio
import shutil

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename=LOG_FILE
)
logger = logging.getLogger(__name__)

# Persian timezone
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

class ReminderParser:
    def __init__(self):
        self.time_pattern = r'ساعت\s+(\d{1,2})(?::(\d{2}))?\s*(بعد از ظهر|صبح|عصر|شب)?'
        self.date_pattern = r'(فردا|پس‌فردا|امروز|(\d{1,2})\s+(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)\s+(\d{4}))'
        
    def extract_reminder_details(self, text: str) -> Dict:
        """Extract reminder details using regex patterns."""
        try:
            time_match = re.search(self.time_pattern, text)
            date_match = re.search(self.date_pattern, text)
            
            result = {
                "time_info": None,
                "date_info": None,
                "task": text
            }
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3)
                
                # Convert to 24-hour format
                if period in ['بعد از ظهر', 'عصر', 'شب'] and hour < 12:
                    hour += 12
                elif period == 'صبح' and hour == 12:
                    hour = 0
                    
                result["time_info"] = {"hour": hour, "minute": minute}
            
            if date_match:
                if date_match.group(1) == 'فردا':
                    date = datetime.datetime.now(TEHRAN_TZ) + datetime.timedelta(days=1)
                elif date_match.group(1) == 'پس‌فردا':
                    date = datetime.datetime.now(TEHRAN_TZ) + datetime.timedelta(days=2)
                elif date_match.group(1) == 'امروز':
                    date = datetime.datetime.now(TEHRAN_TZ)
                else:
                    # Parse Persian date
                    day = int(date_match.group(2))
                    month = self._get_month_number(date_match.group(3))
                    year = int(date_match.group(4))
                    date = datetime.datetime(year, month, day, tzinfo=TEHRAN_TZ)
                    
                result["date_info"] = date
            
            # Extract task by removing time and date parts
            task = text
            if time_match:
                task = task.replace(time_match.group(0), '')
            if date_match:
                task = task.replace(date_match.group(0), '')
            task = task.replace('یادآوری کن', '').replace('یادم بنداز', '').replace('که', '').strip()
            result["task"] = task
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing reminder: {e}")
            return None
            
    def _get_month_number(self, month_name: str) -> int:
        """Convert Persian month name to number."""
        months = {
            'فروردین': 1, 'اردیبهشت': 2, 'خرداد': 3,
            'تیر': 4, 'مرداد': 5, 'شهریور': 6,
            'مهر': 7, 'آبان': 8, 'آذر': 9,
            'دی': 10, 'بهمن': 11, 'اسفند': 12
        }
        return months.get(month_name, 1)

class ReminderBot:
    def __init__(self):
        # Initialize bot configuration
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.model_size = os.getenv('WHISPER_MODEL_SIZE', 'tiny')
        self.compute_type = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')
        self.cpu_threads = int(os.getenv('WHISPER_CPU_THREADS', '1'))
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_TRANSCRIPTIONS', '1'))
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL', '300'))
        
        # Initialize voice recognition model
        self.model = WhisperModel(
            self.model_size,
            device="cpu",
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads
        )
        
        # Create temp directory for voice files
        self.temp_dir = tempfile.mkdtemp()
        self.processing_count = 0
        self.last_cleanup = time.time()
        
        # Initialize database
        self.db_conn = self._setup_database()
        self.parser = ReminderParser()
        self._setup_handlers()
        
        # Start the scheduler in a separate thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

    def _setup_database(self) -> sqlite3.Connection:
        """Set up SQLite database for storing reminders."""
        conn = sqlite3.connect('reminders.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            frequency TEXT DEFAULT 'once',
            next_run TEXT NOT NULL
        )
        ''')
        conn.commit()
        return conn

    def _setup_handlers(self) -> None:
        """Set up Telegram message handlers."""
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("list", self.list_reminders))
        self.application.add_handler(CommandHandler("delete", self.delete_reminder))
        
        # Handle voice messages
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        
        # Handle text messages (natural language reminders)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Handle callback queries (button presses)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        keyboard = [
            [InlineKeyboardButton(BUTTON_TEXTS["list_reminders"], callback_data="list_reminders")],
            [InlineKeyboardButton(BUTTON_TEXTS["help"], callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "سلام! من یک ربات یادآور هستم. می‌توانید به من بگویید چه چیزی را و چه زمانی به شما یادآوری کنم.\n"
            "مثال: 'یادآوری کن که فردا ساعت ۳ بعد از ظهر به مادرم زنگ بزنم'",
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        help_text = (
            "راهنمای استفاده از ربات یادآور:\n\n"
            "• برای تنظیم یادآور به صورت طبیعی بنویسید:\n"
            "  'یادآوری کن که فردا ساعت ۳ به مادرم زنگ بزنم'\n"
            "  'برای جلسه دندانپزشکی ۵ خرداد ساعت ۱۰ یادآوری کن'\n\n"
            "• مشاهده یادآورها:\n"
            "  دستور /list\n\n"
            "• حذف یادآور:\n"
            "  دستور /delete شماره_یادآور\n"
            "  مثال: /delete 2\n\n"
            "• همچنین می‌توانید پیام صوتی بفرستید و من آن را به یادآور تبدیل می‌کنم."
        )
        await update.message.reply_text(help_text)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages with memory management."""
        if self.processing_count >= self.max_concurrent:
            await update.message.reply_text(
                "سیستم در حال حاضر مشغول است. لطفاً چند لحظه دیگر تلاش کنید."
            )
            return

        try:
            self.processing_count += 1
            voice = update.message.voice
            voice_file = await context.bot.get_file(voice.file_id)
            
            # Save to temp file with OGG extension
            ogg_path = os.path.join(self.temp_dir, f"{voice.file_id}.ogg")
            wav_path = os.path.join(self.temp_dir, f"{voice.file_id}.wav")
            
            # Download the voice file
            await voice_file.download_to_drive(ogg_path)
            
            # Convert OGG to WAV using ffmpeg
            os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")
            
            # Transcribe with optimized parameters
            segments, info = self.model.transcribe(
                wav_path,
                language="fa",
                beam_size=1,
                vad_filter=True
            )
            
            text = " ".join([segment.text for segment in segments])
            
            # Clean up the files immediately after use
            try:
                os.remove(ogg_path)
                os.remove(wav_path)
            except Exception as e:
                logger.error(f"Error cleaning up voice files: {e}")
            
            # Process the transcribed text
            await self._process_reminder_text(text, update, context)
            
            # Send confirmation of transcription
            await update.message.reply_text(f"متن تشخیص داده شده:\n{text}")
            
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            await update.message.reply_text(
                "متأسفانه در پردازش پیام صوتی مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
            )
        finally:
            self.processing_count -= 1
            await self.cleanup_old_files()

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process text messages and extract reminder details."""
        text = update.message.text
        await self._process_reminder_text(text, update, context)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button presses."""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "list_reminders":
                # Get user ID from callback query
                user_id = query.from_user.id
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "SELECT id, text, next_run, frequency FROM reminders WHERE user_id = ? ORDER BY next_run",
                    (user_id,)
                )
                reminders = cursor.fetchall()
                
                if not reminders:
                    await query.message.reply_text("شما هیچ یادآوری تنظیم نکرده‌اید.")
                    return
                
                response = "📅 یادآورهای شما:\n\n"
                for idx, (r_id, text, next_run, frequency) in enumerate(reminders, 1):
                    dt = datetime.datetime.fromisoformat(next_run)
                    response += f"{idx}. {text} - {self._persian_format_datetime(dt)}"
                    if frequency != "once":
                        response += f" ({self._format_frequency_persian(frequency)})"
                    response += "\n"
                    
                await query.message.reply_text(response)
                
            elif query.data == "help":
                help_text = (
                    "راهنمای استفاده از ربات یادآور:\n\n"
                    "• برای تنظیم یادآور به صورت طبیعی بنویسید:\n"
                    "  'یادآوری کن که فردا ساعت ۳ به مادرم زنگ بزنم'\n"
                    "  'برای جلسه دندانپزشکی ۵ خرداد ساعت ۱۰ یادآوری کن'\n\n"
                    "• مشاهده یادآورها:\n"
                    "  دستور /list\n\n"
                    "• حذف یادآور:\n"
                    "  دستور /delete شماره_یادآور\n"
                    "  مثال: /delete 2\n\n"
                    "• همچنین می‌توانید پیام صوتی بفرستید و من آن را به یادآور تبدیل می‌کنم."
                )
                await query.message.reply_text(help_text)
                
            elif query.data.startswith("confirm_"):
                reminder_id = int(query.data.split("_")[1])
                await self._confirm_reminder(update, context, reminder_id)
                
            elif query.data.startswith("reject_"):
                reminder_id = int(query.data.split("_")[1])
                await self._reject_reminder(update, context, reminder_id)
                
            elif query.data.startswith("frequency_"):
                reminder_id = int(query.data.split("_")[1])
                frequency = query.data.split("_")[2]
                await self._set_frequency(update, context, reminder_id, frequency)
                
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await query.message.reply_text("متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید.")

    async def _confirm_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int) -> None:
        """Confirm and save a reminder."""
        # Get reminder details from context
        reminder_data = context.user_data.get(f"pending_reminder_{reminder_id}")
        if not reminder_data:
            await update.callback_query.message.reply_text("متأسفانه این یادآور دیگر معتبر نیست.")
            return
            
        # Add the reminder to database
        self._add_reminder(
            user_id=update.callback_query.from_user.id,
            text=reminder_data["text"],
            scheduled_time=reminder_data["scheduled_time"],
            frequency=reminder_data.get("frequency", "once")
        )
        
        # Show frequency selection buttons
        keyboard = [
            [
                InlineKeyboardButton(BUTTON_TEXTS["once"], callback_data=f"frequency_{reminder_id}_once"),
                InlineKeyboardButton(BUTTON_TEXTS["daily"], callback_data=f"frequency_{reminder_id}_daily")
            ],
            [
                InlineKeyboardButton(BUTTON_TEXTS["weekly"], callback_data=f"frequency_{reminder_id}_weekly"),
                InlineKeyboardButton(BUTTON_TEXTS["monthly"], callback_data=f"frequency_{reminder_id}_monthly")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(
            "لطفاً فرکانس یادآوری را انتخاب کنید:",
            reply_markup=reply_markup
        )

    async def _reject_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int) -> None:
        """Reject a reminder."""
        # Remove pending reminder data
        context.user_data.pop(f"pending_reminder_{reminder_id}", None)
        await update.callback_query.message.reply_text("یادآور رد شد. می‌توانید یک یادآور جدید ایجاد کنید.")

    async def _set_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int, frequency: str) -> None:
        """Set the frequency for a reminder."""
        # Update the reminder frequency in database
        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE reminders SET frequency = ? WHERE id = ?",
            (frequency, reminder_id)
        )
        self.db_conn.commit()
        
        await update.callback_query.message.reply_text(
            f"✅ یادآور با فرکانس {FREQUENCIES[frequency]} تنظیم شد."
        )

    async def _process_reminder_text(self, text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process reminder text and extract details."""
        try:
            logger.info(f"Processing text: {text}")
            
            # Extract reminder details
            details = self.parser.extract_reminder_details(text)
            if not details:
                raise Exception("Failed to extract reminder details")
            
            time_info = details["time_info"]
            date_info = details["date_info"]
            task = details["task"]
            
            if time_info and date_info:
                # Combine date and time
                reminder_time = date_info.replace(hour=time_info["hour"], minute=time_info["minute"])
                
                # Generate a unique ID for this reminder
                reminder_id = int(time.time())
                
                # Store reminder data temporarily
                context.user_data[f"pending_reminder_{reminder_id}"] = {
                    "text": task,
                    "scheduled_time": reminder_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "frequency": "once"
                }
                
                # Create confirmation buttons
                keyboard = [
                    [
                        InlineKeyboardButton(BUTTON_TEXTS["confirm"], callback_data=f"confirm_{reminder_id}"),
                        InlineKeyboardButton(BUTTON_TEXTS["reject"], callback_data=f"reject_{reminder_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send confirmation message
                await update.message.reply_text(
                    f"آیا می‌خواهید این یادآور را تنظیم کنید؟\n\n"
                    f"📝 متن: {task}\n"
                    f"⏰ زمان: {self._persian_format_datetime(reminder_time)}",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "متأسفانه نتوانستم زمان یادآور را تشخیص دهم. لطفاً به صورت واضح‌تر زمان را مشخص کنید.\n"
                    "مثال: یادآوری کن فردا ساعت ۳ به مادرم زنگ بزنم"
                )
                
        except Exception as e:
            logger.error(f"Error processing reminder text: {e}", exc_info=True)
            await update.message.reply_text(
                "متأسفانه نتوانستم یادآور شما را درک کنم. لطفاً به صورت واضح‌تر بنویسید.\n"
                "مثال: یادآوری کن فردا ساعت ۳ به مادرم زنگ بزنم"
            )

    def _persian_format_datetime(self, dt: datetime.datetime) -> str:
        """Format datetime in Persian style."""
        # Convert to Persian calendar
        persian_date = jdatetime.datetime.fromgregorian(datetime=dt)
        
        # Format the date
        formatted_date = f"{persian_date.day} {self._get_persian_month_name(persian_date.month)} {persian_date.year}"
        
        # Format the time
        hour_12 = dt.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        
        am_pm = "بعد از ظهر" if dt.hour >= 12 else "صبح"
        
        return f"{formatted_date}، ساعت {hour_12}:{dt.minute:02d} {am_pm}"

    def _get_persian_month_name(self, month: int) -> str:
        """Convert month number to Persian month name."""
        month_names = {
            1: "فروردین", 2: "اردیبهشت", 3: "خرداد",
            4: "تیر", 5: "مرداد", 6: "شهریور",
            7: "مهر", 8: "آبان", 9: "آذر",
            10: "دی", 11: "بهمن", 12: "اسفند"
        }
        return month_names.get(month, "فروردین")

    def _add_reminder(self, user_id: int, text: str, scheduled_time: str, frequency: str = "once") -> int:
        """Add a reminder to the database."""
        cursor = self.db_conn.cursor()
        cursor.execute(
            "INSERT INTO reminders (user_id, text, scheduled_time, frequency, next_run) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, scheduled_time, frequency, scheduled_time)
        )
        self.db_conn.commit()
        return cursor.lastrowid

    async def list_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all reminders for a user."""
        user_id = update.message.from_user.id
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT id, text, next_run, frequency FROM reminders WHERE user_id = ? ORDER BY next_run",
            (user_id,)
        )
        reminders = cursor.fetchall()
        
        if not reminders:
            await update.message.reply_text("شما هیچ یادآوری تنظیم نکرده‌اید.")
            return
        
        response = "📅 یادآورهای شما:\n\n"
        for idx, (r_id, text, next_run, frequency) in enumerate(reminders, 1):
            dt = datetime.datetime.fromisoformat(next_run)
            response += f"{idx}. {text} - {self._persian_format_datetime(dt)}"
            if frequency != "once":
                response += f" ({self._format_frequency_persian(frequency)})"
            response += "\n"
            
        await update.message.reply_text(response)

    def _format_frequency_persian(self, frequency: str) -> str:
        """Convert frequency to Persian text."""
        if frequency == "once":
            return "یکبار"
        elif frequency == "daily":
            return "هر روز"
        elif frequency == "weekly":
            return "هر هفته"
        elif frequency == "monthly":
            return "هر ماه"
        else:
            return frequency

    async def delete_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Delete a reminder by index."""
        user_id = update.message.from_user.id
        
        try:
            # Get the reminder index from command arguments
            if not context.args or not context.args[0].isdigit():
                await update.message.reply_text("لطفاً شماره یادآور را وارد کنید. مثال: /delete 2")
                return
                
            reminder_idx = int(context.args[0])
            
            # Get all reminders for this user
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT id, text FROM reminders WHERE user_id = ? ORDER BY next_run",
                (user_id,)
            )
            reminders = cursor.fetchall()
            
            if not reminders or reminder_idx < 1 or reminder_idx > len(reminders):
                await update.message.reply_text("شماره یادآور نامعتبر است.")
                return
                
            # Get the actual reminder ID from the database
            reminder_id, reminder_text = reminders[reminder_idx - 1]
            
            # Delete the reminder
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            self.db_conn.commit()
            
            await update.message.reply_text(f"🗑️ یادآور {reminder_idx} ({reminder_text}) حذف شد!")
            
        except Exception as e:
            logger.error(f"Error deleting reminder: {e}")
            await update.message.reply_text("خطا در حذف یادآور. لطفاً دوباره تلاش کنید.")

    def _run_scheduler(self) -> None:
        """Run the scheduler continuously to check for reminders."""
        while True:
            self._check_reminders()
            time.sleep(30)  # Check every 30 seconds

    def _check_reminders(self) -> None:
        """Check for reminders to send."""
        now = datetime.datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT id, user_id, text, scheduled_time, frequency FROM reminders WHERE next_run <= ?",
            (now,)
        )
        due_reminders = cursor.fetchall()
        
        for reminder_id, user_id, text, scheduled_time, frequency in due_reminders:
            # Send the reminder
            self._send_reminder(user_id, text)
            
            # Update or remove the reminder based on frequency
            if frequency == "once":
                cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            else:
                next_run = self._calculate_next_run(scheduled_time, frequency)
                cursor.execute(
                    "UPDATE reminders SET next_run = ? WHERE id = ?",
                    (next_run, reminder_id)
                )
        
        self.db_conn.commit()

    def _calculate_next_run(self, last_run: str, frequency: str) -> str:
        """Calculate the next run time based on frequency."""
        dt = datetime.datetime.fromisoformat(last_run)
        
        if frequency == "daily":
            next_run = dt + datetime.timedelta(days=1)
        elif frequency == "weekly":
            next_run = dt + datetime.timedelta(weeks=1)
        elif frequency == "monthly":
            # Add a month - handle month end dates
            month = dt.month + 1
            year = dt.year
            if month > 12:
                month = 1
                year += 1
                
            # Handle months with different number of days
            day = min(dt.day, self._days_in_month(year, month))
            next_run = dt.replace(year=year, month=month, day=day)
        else:
            # Default to daily if frequency not recognized
            next_run = dt + datetime.timedelta(days=1)
            
        return next_run.strftime("%Y-%m-%d %H:%M:%S")

    def _days_in_month(self, year: int, month: int) -> int:
        """Calculate the number of days in a month."""
        if month == 2:  # February
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):  # Leap year
                return 29
            return 28
        elif month in [4, 6, 9, 11]:  # April, June, September, November
            return 30
        else:
            return 31

    def _send_reminder(self, user_id: int, text: str) -> None:
        """Send a reminder to the user."""
        try:
            # Use an async function to send the message
            async def send():
                bot = self.application.bot
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 یادآوری: {text}"
                )
            
            # Run the async function
            asyncio.run(send())
            
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")

    async def cleanup_old_files(self):
        """Clean up old temporary files."""
        current_time = time.time()
        if current_time - self.last_cleanup >= self.cleanup_interval:
            try:
                for filename in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, filename)
                    if os.path.getctime(file_path) < current_time - self.cleanup_interval:
                        os.remove(file_path)
                self.last_cleanup = current_time
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    def run(self) -> None:
        """Start the bot with proper cleanup."""
        try:
            self.application.run_polling()
        finally:
            # Cleanup on shutdown
            shutil.rmtree(self.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    reminder_bot = ReminderBot()
    logger.info("Bot started. Press Ctrl+C to stop.")
    reminder_bot.run()
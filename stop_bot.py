
import os
import sys
import subprocess
import win32file
import win32con
import time

def stop_bot():
    try:
        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Kill all Python processes running the bot
        subprocess.run(['taskkill', '/F', '/IM', 'pythonw.exe'], capture_output=True)
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
        
        # Find and reveal the original bot file
        bot_file = os.path.join(current_dir, 'HEMA_TOP.py')
        if os.path.exists(bot_file):
            # Remove hidden attribute
            win32file.SetFileAttributes(bot_file, win32con.FILE_ATTRIBUTE_NORMAL)
            print(f"✅ تم إيقاف البوت وإظهار الملف: {bot_file}")
        else:
            print("❌ لم يتم العثور على ملف البوت")
            
        # Remove startup file if exists
        startup_path = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup', 'WindowsUpdate.bat')
        if os.path.exists(startup_path):
            os.remove(startup_path)
            print("✅ تم حذف ملف بدء التشغيل التلقائي")
            
    except Exception as e:
        print(f"❌ حدث خطأ: {str(e)}")
        
    finally:
        # Wait a moment before closing
        time.sleep(3)
        input("اضغط Enter للخروج...")

if __name__ == "__main__":
    stop_bot() 

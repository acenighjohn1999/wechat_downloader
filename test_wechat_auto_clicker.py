import time
import pyautogui

# Small helpers
def click_at(x, y, delay=0.5):
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()
    time.sleep(delay)

def press_key(key, times=1, delay=0.2):
    for _ in range(times):
        pyautogui.press(key)
        time.sleep(delay)

# Adjust these coordinates for your screen
# Example (1920x1080, WeChat maximized):
CHAT_LIST_START = (200, 150)   # first chat
CHAT_HEIGHT = 70               # vertical distance between chats
CHAT_COUNT = 10                # how many chats to process

IMAGE_AREA = (1000, 900)       # bottom-most image area in chat

time.sleep(3)  # give you time to focus WeChat

for i in range(CHAT_COUNT):
    # 1. Select chat from sidebar
    chat_y = CHAT_LIST_START[1] + i * CHAT_HEIGHT
    click_at(CHAT_LIST_START[0], chat_y)

    # 2. Click last image in the chat
    click_at(*IMAGE_AREA, delay=1)

    # 3. Step backwards through all images
    press_key("left", times=50, delay=0.1)  # adjust number as needed

    # 4. Exit image viewer
    press_key("esc")

    time.sleep(1)

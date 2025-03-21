import requests
import json
import random
import time
from datetime import datetime, timedelta
from openai import OpenAI
import re
import logging
from tkinter import Tk, Label, Button, Text, Entry, END, messagebox, StringVar, ttk
from threading import Thread  # Import Thread explicitly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)

class BotConfig:
    # Default values (will be overridden by user input)
    TOKEN = ""
    ENDPOINT = "https://free.v36.cm/v1/"
    MODEL_NAME = "gpt-4o-mini"
    CHANNEL_LIST = []
    AUTHORIZATION_LIST = []

# Initialize OpenAI Client
client = None

# Global variable to control bot running state
is_running = False

# Conversation history for the AI
conversation_history = []

def is_in_disabled_time() -> bool:
    """Check if the current time falls within the disabled period."""
    now = datetime.now()
    if (now.hour == 12 and now.minute >= 30) or (13 <= now.hour < 14):
        return True
    if (now.hour >= 23 and now.minute >= 30) or (0 <= now.hour < 8):
        return True
    return False

def get_ai_response(messages: list, promote_message: str) -> str:
    """Fetch a response from OpenAI's API with conversation history."""
    global conversation_history

    try:
        # Add the PROMOTE_MESSAGE as a system message to guide the AI
        system_message = {"role": "system", "content": promote_message}

        # Combine the conversation history with the new messages
        full_conversation = [system_message] + conversation_history + [{"role": "user", "content": msg} for msg in messages[:5]]

        # Fetch the AI response
        response = client.chat.completions.create(
            messages=full_conversation,
            temperature=1.0,
            top_p=1.0,
            max_tokens=1000,
            model=BotConfig.MODEL_NAME
        )

        ai_response = response.choices[0].message.content

        # Update the conversation history with the latest interaction
        conversation_history.append({"role": "user", "content": messages[0]})
        conversation_history.append({"role": "assistant", "content": ai_response})

        logging.info('AI response: {}'.format(ai_response))
        return ai_response

    except Exception as e:
        logging.error(f"Error while fetching AI response: {e}")
        return "Building a wave"

def get_last_message(header: dict) -> tuple:
    """Fetch the last messages from a random channel."""
    channel_id = random.choice(BotConfig.CHANNEL_LIST)
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    try:
        res = requests.get(url=url, headers=header)
        res.raise_for_status()
        data = res.json()
        messages = [
            re.sub(r'<@\d+>|<:\d+:\d+>|<a:[a-zA-Z_]+:\d+>', '', message['content'])
            for message in data
        ]
        message_ids = [message['id'] for message in data]
        return messages, message_ids
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching messages: {e}")
        return [], []

def build_message(header: dict, promote_message: str) -> dict:
    """Build the message to send."""
    messages, message_ids = get_last_message(header)
    validated_message = get_ai_response(messages, promote_message)
    final_message = validated_message
    msg = {
        "content": final_message,
        "nonce": f"82329451214{random.randrange(0, 1000)}33232234"
    }
    return msg

def send_message(channel_id: str, header: dict, ui_text: Text, promote_message: str) -> None:
    """Send a message to the specified channel."""
    global is_running
    if not is_running:
        return

    post_url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    try:
        msg = build_message(header, promote_message)
        res = requests.post(url=post_url, headers=header, data=json.dumps(msg))
        res.raise_for_status()
        logging.info(f"Message sent successfully to channel {channel_id}.")
        ui_text.insert(END, f"Message sent successfully to channel {channel_id}.\n")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message to channel {channel_id}: {e}")
        ui_text.insert(END, f"Error sending message to channel {channel_id}: {e}\n")

def send_to_channels(ui_text: Text, stop_time: datetime, promote_message: str, interval_var: StringVar) -> None:
    """Send messages to all channels, respecting the disabled time and stop time."""
    global is_running
    while is_running and datetime.now() < stop_time:
        if is_in_disabled_time():
            ui_text.insert(END, "Current time is in the disabled period, skipping message sending.\n")
            time.sleep(60)
            continue

        try:
            interval = int(interval_var.get().strip())
            if interval <= 0:
                raise ValueError("Interval must be greater than 0.")
        except ValueError:
            ui_text.insert(END, "Invalid interval value. Using default interval of 15 seconds.\n")
            interval = 15

        message_counter = 0
        for authorization in BotConfig.AUTHORIZATION_LIST:
            if not is_running or datetime.now() >= stop_time:
                break

            header = {
                "Authorization": authorization,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }

            for channel_id in BotConfig.CHANNEL_LIST:
                if not is_running or datetime.now() >= stop_time:
                    break

                send_message(channel_id, header, ui_text, promote_message)
                message_counter += 1
                time.sleep(interval)

                if message_counter >= 10:
                    ui_text.insert(END, "Sent 10 messages, taking a 5-minute break.\n")
                    time.sleep(600)
                    message_counter = 0

def update_timer_label(stop_time: datetime, timer_label: Label) -> None:
    """Update the timer label with remaining time."""
    global is_running
    while is_running and datetime.now() < stop_time:
        remaining_time = stop_time - datetime.now()
        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        timer_label.config(text=f"Time Remaining: {hours}h {minutes}m {seconds}s")
        time.sleep(1)
    timer_label.config(text="Time Remaining: 0h 0m 0s")

def start_bot(ui_text: Text, token_var: StringVar, channels_var: StringVar, auth_var: StringVar, model_label: Label, runtime_var: StringVar, timer_label: Label, promote_message_var: StringVar, interval_var: StringVar, start_button: Button, stop_button: Button) -> None:
    """Start the bot with user-provided inputs."""
    global is_running, client, conversation_history
    if is_running:
        messagebox.showwarning("Warning", "Bot is already running.")
        return

    try:
        # Reset conversation history
        conversation_history = []

        # Update BotConfig with user inputs
        BotConfig.TOKEN = token_var.get().strip()
        BotConfig.CHANNEL_LIST = [ch.strip() for ch in channels_var.get().split(",") if ch.strip()]
        BotConfig.AUTHORIZATION_LIST = [auth.strip() for auth in auth_var.get().split(",") if auth.strip()]

        # Validate inputs
        if not BotConfig.TOKEN or not BotConfig.CHANNEL_LIST or not BotConfig.AUTHORIZATION_LIST:
            raise ValueError("Missing required inputs (Token, Channels, or Authorization).")

        # Parse runtime duration
        try:
            runtime_hours = float(runtime_var.get().strip())
            if runtime_hours <= 0:
                raise ValueError("Runtime must be greater than 0.")
        except ValueError:
            raise ValueError("Invalid runtime value. Please enter a positive number.")

        # Get PROMOTE_MESSAGE from user input
        promote_message = promote_message_var.get().strip()
        if not promote_message:
            promote_message = (
                f"You're playing the role of a recent college graduate chatting with someone, and you can't let them find out that you're a bot. "
                f"There's a web3 community called Sahara now, and here's a summary of the chatting situation. You'll want to learn their chatting style, "
                f"and you can add in mild profanity like, “Bullshit, guys. Crap, fuck me, I'm going”. You respond to the last message in the most natural way possible, "
                f"in 6 words or less, without exclamation points."
            )

        # Calculate stop time
        stop_time = datetime.now() + timedelta(hours=runtime_hours)

        # Initialize OpenAI client
        client = OpenAI(base_url=BotConfig.ENDPOINT, api_key=BotConfig.TOKEN)

        # Display current model name
        model_label.config(text=f"Current Model: {BotConfig.MODEL_NAME}")

        # Set bot running state
        is_running = True
        start_button.config(state="disabled")
        stop_button.config(state="normal")

        # Start the bot in a separate thread
        def run():
            ui_text.insert(END, "Bot started.\n")
            send_to_channels(ui_text, stop_time, promote_message, interval_var)
            ui_text.insert(END, "Bot has stopped.\n")
            stop_bot(start_button, stop_button)

        Thread(target=run, daemon=True).start()

        # Update timer label in a separate thread
        Thread(target=lambda: update_timer_label(stop_time, timer_label), daemon=True).start()

    except Exception as e:
        messagebox.showerror("Error", str(e))

def stop_bot(start_button: Button, stop_button: Button) -> None:
    """Stop the bot manually."""
    global is_running
    is_running = False
    start_button.config(state="normal")
    stop_button.config(state="disabled")
    messagebox.showinfo("Info", "Bot has been stopped manually.")

def main() -> None:
    # Create the main window
    root = Tk()
    root.title("Discord Bot Control Panel")
    root.geometry("700x800")
    root.configure(bg="#f0f0f0")  # Light gray background

    # Add a title label
    Label(root, text="Discord Bot Control Panel", font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=10)

    # Input for Token
    Label(root, text="API Token:", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    token_var = StringVar()
    Entry(root, textvariable=token_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Input for Channel List
    Label(root, text="Channel IDs (comma-separated):", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    channels_var = StringVar()
    Entry(root, textvariable=channels_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Input for Authorization List
    Label(root, text="Authorization Tokens (comma-separated):", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    auth_var = StringVar()
    Entry(root, textvariable=auth_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Input for Runtime Duration
    Label(root, text="Runtime Duration (hours):", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    runtime_var = StringVar()
    Entry(root, textvariable=runtime_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Input for Message Interval
    Label(root, text="Message Interval (seconds):", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    interval_var = StringVar(value="15")
    Entry(root, textvariable=interval_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Input for PROMOTE_MESSAGE
    Label(root, text="Promote Message (default provided):", font=("Arial", 12), bg="#f0f0f0").pack(anchor="w", padx=10)
    promote_message_var = StringVar(value=(
        f"You're playing the role of a recent college graduate chatting with someone, and you can't let them find out that you're a bot. "
        f"There's a web3 community called Sahara now, and here's a summary of the chatting situation. You'll want to learn their chatting style, "
        f"and you can add in mild profanity like, “Bullshit, guys. Crap, fuck me, I'm going”. You respond to the last message in the most natural way possible, "
        f"in 6 words or less, without exclamation points."
    ))
    Entry(root, textvariable=promote_message_var, width=50, font=("Arial", 10)).pack(pady=5)

    # Display Model Name
    model_label = Label(root, text=f"Current Model: {BotConfig.MODEL_NAME}", font=("Arial", 12), bg="#f0f0f0")
    model_label.pack(pady=10)

    # Timer label
    timer_label = Label(root, text="Time Remaining: --", font=("Arial", 12), bg="#f0f0f0")
    timer_label.pack(pady=10)

    # Add a text area for logs
    text_area = Text(root, wrap="word", height=10, width=80, font=("Arial", 10), bg="#ffffff", relief="solid", borderwidth=1)
    text_area.pack(pady=10)

    # Add Start and Stop buttons
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)

    start_button = Button(
        button_frame,
        text="Start Bot",
        command=lambda: start_bot(text_area, token_var, channels_var, auth_var, model_label, runtime_var, timer_label, promote_message_var, interval_var, start_button, stop_button),
        width=20,
        height=2,
        font=("Arial", 10),
        bg="#4CAF50",  # Green color
        fg="white"
    )
    start_button.pack(side="left", padx=10)

    stop_button = Button(
        button_frame,
        text="Stop Bot",
        command=lambda: stop_bot(start_button, stop_button),
        width=20,
        height=2,
        font=("Arial", 10),
        bg="#F44336",  # Red color
        fg="white",
        state="disabled"
    )
    stop_button.pack(side="right", padx=10)

    # Run the application
    root.mainloop()

if __name__ == "__main__":
    main()
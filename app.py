import os
import requests
import cv2
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
from gradio_client import Client as GradioClient, file

# Load environment variables from .env file
load_dotenv()

# Telegram bot token and other configurations
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
gradio_client = GradioClient("Nymbo/Virtual-Try-On")

# In-memory storage for tracking sessions
user_sessions = {}

# Initialize the bot updater
updater = Updater(TELEGRAM_API_KEY)

# Command to start interaction
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Welcome to the Virtual Try-On bot! Please send a photo of yourself to start the virtual try-on process.")

# Handler for receiving images
def image_handler(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    photo_file = update.message.photo[-1].get_file()

    # Save the user’s photo to in-memory sessions based on steps
    if user_id not in user_sessions:
        user_sessions[user_id] = {"person_image": photo_file.file_path}
        update.message.reply_text("Great! Now send the image of the garment you want to try on.")
    elif "person_image" in user_sessions[user_id] and "garment_image" not in user_sessions[user_id]:
        user_sessions[user_id]["garment_image"] = photo_file.file_path
        update.message.reply_text("Please wait, processing...")  # Notify the user of processing
        
        # Call Gradio API with images for virtual try-on
        try_on_image_url = send_to_gradio(user_sessions[user_id]["person_image"], user_sessions[user_id]["garment_image"])
        
        if try_on_image_url:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=try_on_image_url)
            update.message.reply_text("Here is your virtual try-on result!")
        else:
            update.message.reply_text("Sorry, something went wrong with the try-on process.")
        
        # Clear session after completion
        del user_sessions[user_id]
    else:
        update.message.reply_text("Please send your image to start the virtual try-on process.")

# Function to interact with the Gradio API
def send_to_gradio(person_image_url, garment_image_url):
    person_image_path = download_image(person_image_url, 'person_image.jpg')
    garment_image_path = download_image(garment_image_url, 'garment_image.jpg')

    if person_image_path and garment_image_path:
        try:
            result = gradio_client.predict(
                dict={"background": file(person_image_path), "layers": [], "composite": None},
                garm_img=file(garment_image_path),
                garment_des="A cool description of the garment",
                is_checked=True,
                is_checked_crop=False,
                denoise_steps=30,
                seed=42,
                api_name="/tryon"
            )

            if result and len(result) > 0:
                try_on_image_path = result[0]
                img = cv2.imread(try_on_image_path)
                target_path_png = 'static/result.png'
                cv2.imwrite(target_path_png, img)
                return target_path_png  # Return the path of the processed image
        except Exception as e:
            print(f"Error interacting with Gradio API: {e}")
            return None
    return None

# Helper function to download an image from Telegram
def download_image(url, filename):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return filename
    except Exception as err:
        print(f"Error downloading image: {err}")
    return None

# Set up command and message handlers
updater.dispatcher.add_handler(CommandHandler("start", start))
updater.dispatcher.add_handler(MessageHandler(Filters.photo, image_handler))

# Start polling
updater.start_polling()
updater.idle()

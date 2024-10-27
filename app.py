import os
import requests
import cv2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
from gradio_client import Client as GradioClient, file
from secret import TELEGRAM_API_KEY

# Load environment variables from .env file
load_dotenv()

# Initialize Gradio Client
gradio_client = GradioClient("Nymbo/Virtual-Try-On")

# In-memory storage for tracking sessions
user_sessions = {}

# Initialize the bot application
app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()

# Command to start interaction
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Welcome to the Virtual Try-On bot! Please send a photo of yourself to start the virtual try-on process.")

# Handler for receiving images
async def image_handler(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    photo_file = await update.message.photo[-1].get_file()

    # Save the user’s photo to in-memory sessions based on steps
    if user_id not in user_sessions:
        user_sessions[user_id] = {"person_image": photo_file.file_path}
        await update.message.reply_text("Great! Now send the image of the garment you want to try on.")
    elif "person_image" in user_sessions[user_id] and "garment_image" not in user_sessions[user_id]:
        user_sessions[user_id]["garment_image"] = photo_file.file_path
        await update.message.reply_text("Please wait, processing...")  # Notify the user of processing
        
        # Call Gradio API with images for virtual try-on
        try_on_image_path = await send_to_gradio(user_sessions[user_id]["person_image"], user_sessions[user_id]["garment_image"])
        
        if try_on_image_path:
            # Open the image file and send it as a file
            with open(try_on_image_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)
            await update.message.reply_text("Here is your virtual try-on result!")
        else:
            await update.message.reply_text("Sorry, something went wrong with the try-on process.")
        
        # Clear session after completion
        del user_sessions[user_id]
    else:
        await update.message.reply_text("Please send your image to start the virtual try-on process.")

# Function to interact with the Gradio API
async def send_to_gradio(person_image_url, garment_image_url):
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
                # Save the output image from Gradio
                output_image_path = 'static/result.png'
                with open(output_image_path, 'wb') as f:
                    f.write(result[0])  # Assuming result[0] contains the image data
                return output_image_path  # Return the path of the processed image
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
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, image_handler))

# Start polling
if __name__ == '__main__':
    app.run_polling()

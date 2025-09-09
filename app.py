from flask import Flask, render_template, request, jsonify, redirect, url_for
import os, base64
from datetime import datetime
import requests
from flask import send_from_directory
import mysql.connector
from mysql.connector import pooling, Error
from config import DB_CONFIG 
from dotenv import load_dotenv
from flask_mail import Mail, Message
from mail_function import send_designer_email
from PIL import Image 
load_dotenv() 

app = Flask(__name__)
app.config.from_pyfile('config.py')

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="photobooth_pool",
        pool_size=5,  
        **DB_CONFIG  
    )
    print("✅ Database connection pool created successfully.")
except Error as e:
    print(f"❌ Error creating database connection pool: {e}")
    connection_pool = None

def get_db_connection():
    if connection_pool:
        try:
            return connection_pool.get_connection()
        except Error as e:
            print(f"❌ Could not get a connection from the pool: {e}")
            return None
    return None

app.secret_key = "fast-app"
os.makedirs("generated", exist_ok=True)
os.makedirs("photos", exist_ok=True)

# Global state
trigger_capture = False
capture_name = None  
capture_user_id = None
capture_user_email = None
latest_generated = None  
latest_generated_path = None 
wrapup = False
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5001/webhook")
API_URL = os.getenv("API_URL", "https://05a2dbf47da0.ngrok-free.app/generate-image")


@app.route("/")
def loading():
    global wrapup
    if wrapup == True:
        email_db_update()
    return render_template("loading.html")


@app.route("/capture")
def capture():
    global trigger_capture, capture_name
    if trigger_capture:
        trigger_capture = False
        return render_template("capture.html", name=capture_name or "User")
    return redirect(url_for("loading"))


@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook now expects id, name, email"""
    global trigger_capture, capture_name, capture_user_id,capture_user_email
    data = request.get_json(silent=True)

    if data and "id" in data and "name" in data and "email" in data:
        trigger_capture = True
        capture_name = data["name"] 
        capture_user_id = data["id"]
        capture_user_email = data["email"]
        print(capture_name)
        print(capture_user_id)
        print(capture_user_email)
        print(capture_user_id + "from webhook")
        print(f"Webhook received for user ID: {capture_user_id}")
        return jsonify(status="success", message="Photo capture triggered")
    
    return jsonify(status="error", message="Invalid payload"), 400

def update_user_flag_in_db(user_id):

    query = "UPDATE users SET flag = FALSE WHERE id = %s"

    connection = get_db_connection()
    if not connection:
        print("Error: Could not connect to the database.")
        return False
        
    try:
        cursor = connection.cursor()
        cursor.execute(query, (user_id,))
        connection.commit()
        print(f"Successfully updated flag for user_id: {user_id}")
        return True
    except Error as e:
        print(f"Error while updating data: {e}")
        return False
    finally:
    
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Database connection returned to the pool.")
            
            
@app.route("/save_photo", methods=["POST"])
def save_photo():
    global latest_generated, capture_user_id, wrapup, latest_generated_path
    try:
        image = request.files["image"]
        filename = f"photo_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        filepath = os.path.join("photos", filename)
        image.save(filepath)
        api_url = API_URL

        with open(filepath, "rb") as img_file:
            files = {"face_image": (filename, img_file, image.mimetype)}
            data = { "guidance_scale": "1.5", "prompt": "a person", "enhance_face_region": "false", "identitynet_strength_ratio": "0.8", "negative_prompt": "", "num_steps": "20", "seed": "0", "style_name": "Spring Festival", "enable_LCM": "true", "adapter_strength_ratio": "0.8" }
            response = requests.post(api_url, data=data, files=files)

        if response.ok and "image" in response.headers.get("Content-Type", ""):
            gen_filename = f"generated_{datetime.now():%Y%m%d_%H%M%S}.png"
            gen_path = os.path.join("generated", gen_filename)
            with open(gen_path, "wb") as f:
                f.write(response.content)

            latest_generated = gen_filename
            print(latest_generated)
            latest_generated_path = gen_path 
            wrapup=True
            return jsonify(status="success", generated_file=gen_filename)
        else:
            return jsonify(status="error", message="API error", details=response.text), response.status_code
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500


FRAME_PATH = os.path.join("static", "frames", "frame.png")

def email_db_update():
    print("email_db_update function called")
    global wrapup, capture_user_id,capture_user_email,capture_name,latest_generated_path
    
    print(capture_user_email)
    print(capture_name)
    print(latest_generated_path)
    # --- MODIFICATION START ---
    
    # 1. Define the path for the new, framed image.
    # if latest_generated_path:
    #     original_filename = os.path.basename(latest_generated_path)
    #     framed_filename = f"framed_{original_filename}"
    #     framed_image_output_path = os.path.join("generated", framed_filename)
    #     FRAME_PATH = os.path.join("static", "frames", "F.png")
    #     # 2. Call the new function to create the framed image.
    #     # my_window = (100, 100, 1572 , 804) # x, y, width, height
    #     # final_image_path_to_send = frame_image_advanced(latest_generated_path, FRAME_PATH, framed_image_output_path, my_window )
        
    #     # my_target_box = (50, 50, 1472, 704)
    #     # final_image_path_to_send = frame_image_onto_solid(
    #     #     photo_path=latest_generated_path,
    #     #     frame_path=FRAME_PATH,
    #     #     output_path=framed_image_output_path,
    #     #     target_box=my_target_box # Use your measured target box
    #     # )
        
    #     fit_image_on_frame(latest_generated_path, FRAME_PATH, framed_image_output_path)
    #     # If framing fails, we can fall back to sending the original image
    #     if not final_image_path_to_send:
    #         print("⚠️ Framing failed. Sending original image instead.")
    #         final_image_path_to_send = latest_generated_path
    # else:
    #     print("❌ No 'latest_generated_path' found. Cannot send email.")
    #     return # Exit if there is no image to process

    # 3. Use the new framed image path to send the email.
    # print(f"User Email: {capture_user_email}")
    # print(f"User Name: {capture_name}")
    # print(f"Image to send: {final_image_path_to_send}")
    
    # send_designer_email(capture_user_email, capture_name, final_image_path_to_send)
    
    # --- MODIFICATION END ---
    
    send_designer_email(capture_user_email, capture_name, latest_generated_path)
    
    if capture_user_id:
        print(f"Attempting to update flag for user ID: {capture_user_id}")
        success = update_user_flag_in_db(capture_user_id)
        if not success:
            print(f"Warning: Failed to update database flag for user_id {capture_user_id}.")
            capture_user_id = None
        else:
            print("Warning: No user ID was available to update in the database.")
            
    send_webhook()
    wrapup = False
    
def send_webhook():
    try:
        webhook_data = {
            'message': 'xxxx'
            }
        print("webhook send----------------------------")
        requests.post(WEBHOOK_URL, json=webhook_data, timeout=3)
    except Exception as e:
        print(f"Webhook error: {e}")

@app.route("/check_trigger")
def check_trigger():
    return jsonify(triggered=trigger_capture)

@app.route("/check_generated")
def check_generated():
    global latest_generated
    if latest_generated:
        filename = latest_generated
        latest_generated = None  # reset after sending once
        return jsonify(new_image=filename)
    return jsonify(new_image=None)

@app.route("/processing")
def loading_screen_b():
    return render_template("processing.html")

@app.route("/generated/<path:filename>")
def serve_generated(filename):
    return send_from_directory("generated", filename)

@app.route('/processing_timeout')
def processing_timeout():
    """Renders the page shown when processing takes too long."""
    send_webhook()
    return render_template('loading.html')

@app.route("/recapture")
def recapture():
    """Sets the trigger to allow retaking a photo and redirects to capture page."""
    global trigger_capture
    trigger_capture = True
    return redirect(url_for("capture"))


mail = Mail(app)

    
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

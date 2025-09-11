import threading
from dotenv import load_dotenv
load_dotenv() 
from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
from datetime import datetime
import requests
from flask import send_from_directory
import mysql.connector
from mysql.connector import pooling, Error
from config import DB_CONFIG 
from flask_mail import Mail, Message
from PIL import Image 
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import cv2  
import numpy as np

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
os.makedirs("framed", exist_ok=True)

# --- ADD THIS ENTIRE BLOCK HERE ---
# This pre-loads the frame and calculates ratios ONCE on startup for max performance.
try:
    FRAME_PATH = os.path.join("static", "frames", "frameM.png")
    FRAME_IMAGE_CV = cv2.imread(FRAME_PATH, cv2.IMREAD_UNCHANGED)
    if FRAME_IMAGE_CV is None:
        raise FileNotFoundError(f"Frame not found at {FRAME_PATH}")
    
    ORIGINAL_FRAME_H, ORIGINAL_FRAME_W, _ = FRAME_IMAGE_CV.shape
    
    LEFT_MARGIN_RATIO = 800 / ORIGINAL_FRAME_W
    TOP_MARGIN_RATIO = 800 / ORIGINAL_FRAME_H
    print("✅ Frame image pre-loaded successfully.")

except Exception as e:
    print(f"❌ FATAL ERROR: Could not load the frame image. App may not function correctly. Error: {e}")
    FRAME_IMAGE_CV = None
# --- END OF BLOCK TO ADD ---

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
    global wrapup,capture_user_id,capture_user_email,capture_name,latest_generated_path
    if wrapup == True:
        print("RESTART------------------------RESTART--------------------")
        thread = threading.Thread(target=email_db_update, args=(capture_user_id,capture_user_email,capture_name,latest_generated_path))
        thread.daemon = True
        thread.start()
        
        # email_db_update()
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
    query = "UPDATE users SET flag = FALSE WHERE id = %s"  # change this as per table name USERS

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
            data = { "guidance_scale": "1.5", 
                    "prompt": "young adult, youthful, clear skin, smooth face, symmetrical features, attractive, photorealistic, detailed, natural, sharp features, well-lit, realistic", 
                    "enhance_face_region": "true", 
                    "identitynet_strength_ratio": "0.8", 
                    "negative_prompt": "old, elderly, aged, wrinkled skin, sagging skin, gray hair, balding, unattractive, ugly, deformed, distorted face, asymmetrical face, mutated, disfigured, poorly drawn face, extra eyes, extra teeth, malformed, grotesque, unrealistic face, bad anatomy, low quality", 
                    "num_steps": "20", 
                    "seed": "0", 
                    "style_name": "Snow", 
                    "enable_LCM": "true", 
                    "adapter_strength_ratio": "0.8" }
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
    
    

#-------------------------------------------MASTER FUNCTION------------------------------------
def email_db_update(capture_user_id, capture_user_email, capture_name, latest_generated_path):
    print("email_db_update function called")
    global wrapup

    # --- Stage 1: Image merge and DB update ---
    def merge_worker():
        framed_filename = f"framed_{datetime.now():%Y%m%d_%H%M%S}.jpeg"
        framed_path = os.path.join("framed", framed_filename)
        output_path =  output_path = create_framed_image(
            latest_generated_path, 
            framed_path, 
            # output_size=(1920, 1280), # or None to use original size
            output_size=None,
            jpeg_quality=80
        )
        return output_path

    stage1_results = {}

    def db_worker():
        if capture_user_id:
            print(f"Attempting to update flag for user ID: {capture_user_id}")
            success = update_user_flag_in_db(capture_user_id)
            if not success:
                print(f"Warning: Failed to update database flag for user_id {capture_user_id}.")
            else:
                print("DONE : database updated")

    # Start Stage 1 threads
    merge_thread = threading.Thread(target=lambda: stage1_results.update({"outout_path": merge_worker()}))
    db_thread = threading.Thread(target=db_worker)

    merge_thread.start()
    db_thread.start()

    merge_thread.join()
    db_thread.join()

    # --- Stage 2: Webhook + Email (email fire-and-forget) ---
    outout_path = stage1_results["outout_path"]

    def email_worker():
        try:
            send_designer_email(capture_user_email, capture_name, outout_path)
            print("✅ Email sent in background")
        except Exception as e:
            print(f"⚠️ Email sending failed: {e}")

    def webhook_worker():
        try:
            send_webhook()
            print("✅ Webhook sent")
        except Exception as e:
            print(f"⚠️ Webhook failed: {e}")

    # Start Stage 2 threads
    threading.Thread(target=email_worker, daemon=True).start()  # fire-and-forget
    webhook_thread = threading.Thread(target=webhook_worker)
    webhook_thread.start()

    # Wait only for webhook to finish
    webhook_thread.join()

    # Mark wrapup after Stage 2 starts (email may still be running)
    wrapup = False
    print("✅ wrapup set to False (email still sending in background)")


#-------------------------------------FRAME FUNCTION (OPTIMIZED)-----------------------------------

def create_framed_image(photo_path, output_path, output_size=None, jpeg_quality=90):
    """
    The fastest way to frame a single photo with full control over size and quality.
    """
    if FRAME_IMAGE_CV is None:
        print("Error: Frame image is not loaded. Cannot process photo.")
        return None

    try:
        if output_size:
            target_w, target_h = output_size
            frame_resized = cv2.resize(FRAME_IMAGE_CV, (target_w, target_h), interpolation=cv2.INTER_AREA)
        else:
            frame_resized = FRAME_IMAGE_CV.copy()
        
        frame_h, frame_w, _ = frame_resized.shape

        left_margin = int(frame_w * LEFT_MARGIN_RATIO)
        top_margin = int(frame_h * TOP_MARGIN_RATIO)
        inner_w = frame_w - (2 * left_margin)
        inner_h = frame_h - (2 * top_margin)

        if inner_w <= 0 or inner_h <= 0:
            return None

        photo = cv2.imread(photo_path, cv2.IMREAD_UNCHANGED)
        if photo.shape[2] == 3:
            photo = cv2.cvtColor(photo, cv2.COLOR_BGR2BGRA)
        photo_resized = cv2.resize(photo, (inner_w, inner_h), interpolation=cv2.INTER_AREA)

        y1, y2 = top_margin, top_margin + inner_h
        x1, x2 = left_margin, left_margin + inner_w
        
        alpha = photo_resized[:, :, 3] / 255.0
        inv_alpha = 1.0 - alpha
        
        for c in range(0, 3):
            frame_resized[y1:y2, x1:x2, c] = (alpha * photo_resized[:, :, c] +
                                              inv_alpha * frame_resized[y1:y2, x1:x2, c])

        final_image_bgr = cv2.cvtColor(frame_resized, cv2.COLOR_BGRA2BGR)
        cv2.imwrite(output_path, final_image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        
        print(f"✅ Framed image saved as {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Failed to process {photo_path}. Error: {e}")
        return None

#----------------------------------------EMAIL FUNCTION----------------------------------------------
mail = Mail(app)
def send_designer_email(recipient_email, recipient_name, image_path):
    print("email functon--------------")
    print(recipient_email)
    print(recipient_name)
    print(image_path)
    print("email functon--------------")
    subject = f"A Special Message for {recipient_name}! 💌"

    # Define the HTML body for the email. This is your "designer frame".
    # You can use f-strings to personalize it with the user's name or other data.
    html_body = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Arial', sans-serif; background-color: #f4f4f4; color: #333; }}
          .container {{ max-width: 600px; margin: 20px auto; padding: 20px; background-color: #ffffff; border: 1px solid #ddd; border-radius: 8px; }}
          h1 {{ color: #4a4a4a; }}
          p {{ font-size: 16px; line-height: 1.5; }}
          .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Hello, {recipient_name}!</h1>
          <p>We've created something special just for you. Please see the attached image for your personalized design.</p>
          <p>We hope you love it!</p>
          <div class="footer">
            <p>Sent with ❤️ from Your App</p>
          </div>
        </div>
      </body>
    </html>
    """

    try:
        # Create a Message object
        with app.app_context():
            msg = Message(
                subject=subject,
                recipients=[recipient_email],
                html=html_body
            )

        # Attach the image
        # The 'with' statement ensures the file is properly closed after reading
            with app.open_resource(image_path) as fp:
                # The attach method needs: filename, content_type, and the file data
                msg.attach(
                    filename=os.path.basename(image_path),
                    content_type='image/jpeg', # Or 'image/jpeg' for .jpg files
                    data=fp.read()
                )

            # Send the email
            mail.send(msg)
            print(f"Email sent successfully to {recipient_email}")
            return True

    except Exception as e:
        # Print the error for debugging purposes
        print(f"Error sending email: {e}")
        return False

#----------------------------------------SEND WEEBHOOK FUNCTION---------------------------------------------
def send_webhook():
    try:
        webhook_data = {
            'message': 'xxxx'
            }
        print("webhook send----------------------------")
        requests.post(WEBHOOK_URL, json=webhook_data, timeout=3)
    except Exception as e:
        print(f"Webhook error: {e}")
#-----------------------------------------------ROUTES--------------------------------------------------------

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


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

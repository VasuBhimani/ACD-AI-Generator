import os
from flask import Flask, app
from flask_mail import Mail, Message
app = Flask(__name__)
app.config.from_pyfile('config.py')

mail = Mail(app)
def send_designer_email(recipient_email, recipient_name, image_path):
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
                content_type='image/png', # Or 'image/jpeg' for .jpg files
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
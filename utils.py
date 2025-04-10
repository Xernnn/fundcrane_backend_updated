# utils.py or auth.py
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, url_for
from flask_mail import Message
from app.__init__ import mail # Import your mail instance
from app.config import Config

def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    return serializer.dumps(email, salt='email-verification-salt') # Use a salt!

def verify_verification_token(token, max_age=None):
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    if max_age is None:
        max_age = current_app.config.get('EMAIL_VERIFICATION_TOKEN_MAX_AGE', 3600)
    try:
        email = serializer.loads(
            token,
            salt='email-verification-salt',
            max_age=max_age
        )
        return email
    except Exception as e:
        current_app.logger.warning(f"Email verification token error: {e}")
        return None

def send_verification_email(user_email):
    token = generate_verification_token(user_email)
    # Use _external=True for absolute URL
    verification_url = url_for('user_authentication.verify_email', token=token, _external=True)
    subject = "Please verify your email address"
    html_body = f"""
    <p>Thank you for registering! Please click the link below to verify your email address:</p>
    <p><a href="{verification_url}">Verify Email</a></p>
    <p>If you did not request this, please ignore this email.</p>
    <p>This link will expire in {current_app.config.get('EMAIL_VERIFICATION_TOKEN_MAX_AGE', 3600)//3600} hour(s).</p>
    """
    msg = Message(subject, recipients=[user_email], html=html_body)
    try:
        mail.send(msg)
        current_app.logger.info(f"Verification email sent to {user_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email to {user_email}: {e}")
        return False
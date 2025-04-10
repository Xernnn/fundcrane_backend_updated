from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, Blueprint, abort, session, current_app
from app.services.postgresql import *
from app.config import Config
from datetime import datetime
from utils import send_verification_email,verify_verification_token

user_authentication_bp = Blueprint('user_authentication',__name__)
secret_key = Config.SECRET_KEY
 
# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('jwt_token')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, str(secret_key), algorithms=["HS256"])
            conn = connect_db()
            query = f"SELECT * FROM users1 WHERE public_id='{data['public_id']}';"
            with conn.cursor() as cursor:
                cursor.execute(query)
                current_user = cursor.fetchone()
                conn.commit()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated
# Generate a new invite link
def generate_invite_link():
    invite_code = str(uuid.uuid4())
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO invites (invite_code, used, created_at) VALUES (%s, FALSE, %s) RETURNING invite_code",
        (invite_code, datetime.now())
    )
    conn.commit()
    cur.close()
    conn.close()
    return f"http://localhost:5000/invite/{invite_code}"

@user_authentication_bp.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = connect_db()
        query = f"SELECT * FROM users1 WHERE email='{email}';"
        with conn.cursor() as cursor:
            cursor.execute(query)
            user = cursor.fetchone()
            conn.commit()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        if not user['is_verified']:
            return jsonify({"msg": "Account not verified. Please check your email."}), 403 # Forbidden

        token = jwt.encode({'public_id': str(user['public_id']), 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, 
                           str(secret_key), algorithm="HS256")

        response = make_response(user)
        response.set_cookie('jwt_token', token, httponly=True, secure=True, samesite='Strict')
        if conn:
            conn.close()

        return response

    return 'Login page here'

@user_authentication_bp.route('/signup', methods=['POST'])
def register():
    try:
        # Extract data safely
        invite_code = request.form.get('inviteToken')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([invite_code, name, email, password]):
            return jsonify({'error': 'All fields are required.'}), 400

        conn = connect_db()

        with conn.cursor() as cursor:
            # Check invite code
            cursor.execute("SELECT used FROM invites WHERE invite_code = %s", (invite_code,))
            invite = cursor.fetchone()

            if not invite:
                return jsonify({'error': 'Invite code not found.'}), 400
            if invite['used']:
                return jsonify({'error': 'Invite code has already been used.'}), 400

            # Check for existing user
            cursor.execute("SELECT id FROM users1 WHERE email = %s;", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                return jsonify({'error': 'User with this email already exists. Please log in.'}), 400

            # Create user but DO NOT mark as verified yet
            hashed_password = generate_password_hash(password)
            public_id = str(uuid.uuid4())

            cursor.execute(
                "INSERT INTO users1 (public_id, name, email, password, is_verified) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (public_id, name, email, hashed_password, False)
            )
            user_id = cursor.fetchone()['id']

            # Mark invite as used
            cursor.execute(
                "UPDATE invites SET used = TRUE, used_by = %s WHERE invite_code = %s",
                (user_id, invite_code)
            )

            conn.commit()

            email_sent = False
            try:
                email_sent = send_verification_email(email)
                if not email_sent:
                     current_app.logger.warning(f"Failed to send verification email to {email} for user ID {user_id}, but user is registered.")
            except Exception as email_error:
                # Log the email error, but don't rollback the user creation
                current_app.logger.error(f"Error sending verification email to {email} for user ID {user_id}: {email_error}", exc_info=True)


        return make_response(jsonify({'message': 'Signup successful'}), 201)

    except Exception as e:
        # If any exception occurred BEFORE commit, rollback is implicit on close/error
        # If it happens AFTER commit, the data is already saved.
        if conn:
            try:
                 # Explicitly rollback if an error occurs before commit was reached
                 # This might not be strictly necessary if close() handles it, but it's clearer
                 conn.rollback()
                 current_app.logger.info("Transaction rolled back due to exception.")
            except Exception as rb_ex:
                 current_app.logger.error(f"Error during rollback: {rb_ex}", exc_info=True)

        current_app.logger.error(f"Registration failed: {e}", exc_info=True) # Log the full traceback
        return make_response(jsonify({'error': 'An internal error occurred during registration.'})), 500

    finally:
        if conn:
            conn.close()

@user_authentication_bp.route('/verify_email/<token>', methods = ['GET'])
def verify_email(token):
    email = verify_verification_token(token)
    if not email:
        return jsonify({"msg": "Verification link is invalid or has expired."}), 400

    conn = connect_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users1 WHERE email = %s", (email,))
        user = cursor.fetchone()

    if not user:
        # Should not happen if token is valid, but handle defensively
        return jsonify({"msg": "User not found."}), 404

    if user['is_verified']:
        return jsonify({"msg": "Account already verified."}), 200

    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE users1 SET is_verified = TRUE WHERE email = %s",
            (email,)
        )
        conn.commit()

    try:
        return redirect('https://kzmqk5fn43zw40y0hmk7.lite.vusercontent.net/verify-email/success')
    except Exception as e:
        return jsonify({"msg": "An error occurred during verification. Please try again later."}), 500

@user_authentication_bp.route('/success')
@token_required
def success(current_user):
    return f"Welcome {current_user[2]}! You are logged in."

@user_authentication_bp.route('/generate-invite', methods = ['POST'])
def generate_invite():
    # Add authentication here
    link = generate_invite_link()
    return {"invite_link": link}
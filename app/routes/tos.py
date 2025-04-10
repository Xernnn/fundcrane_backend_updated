import os
import tos
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from app.config import Config
import tempfile

app = Flask(__name__)

# Configure upload settings
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# TOS configuration
TOS_ENDPOINT = "tos-ap-southeast-1.bytepluses.com"
TOS_REGION = "ap-southeast"
TOS_BUCKET = "legal-doc-storage"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if file was included in request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # Check if filename is empty
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if file type is allowed
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    filename = secure_filename(file.filename)
    
    # Save the file temporarily
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        file.save(temp.name)
        temp_path = temp.name
    
    # Upload to TOS
    try:
        # Get credentials from environment variables
        ak = Config.TOS_ACCESS_KEY
        sk = Config.TOS_SECRET_KEY
        
        if not ak or not sk:
            os.remove(temp_path)
            return jsonify({'error': 'TOS credentials not configured'}), 500
        
        # Create TOS client
        client = tos.TosClientV2(ak, sk, TOS_ENDPOINT, TOS_REGION)
        
        # Upload file to bucket
        client.put_object_from_file(TOS_BUCKET, filename, temp_path)
        
        # Delete the temporary file
        os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'filename': filename,
            'bucket': TOS_BUCKET
        }), 200
        
    except tos.exceptions.TosClientError as e:
        os.remove(temp_path)
        return jsonify({
            'error': 'TOS client error',
            'message': e.message,
            'cause': e.cause
        }), 400
        
    except tos.exceptions.TosServerError as e:
        os.remove(temp_path)
        return jsonify({
            'error': 'TOS server error',
            'code': e.code,
            'request_id': e.request_id,
            'message': e.message,
            'http_code': e.status_code
        }), 500
        
    except Exception as e:
        os.remove(temp_path)
        return jsonify({
            'error': 'Unknown error',
            'message': str(e)
        }), 500
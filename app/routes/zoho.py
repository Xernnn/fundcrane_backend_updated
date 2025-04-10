from flask import Blueprint, request, make_response, jsonify
import requests
import tempfile
import json
from app.services.mongo import get_fields_and_url
from app.config import Config

documents_bp = Blueprint('documents', __name__)
ZOHO_OAUTH_TOKEN = Config.ZOHO_OAUTH_TOKEN

@documents_bp.route('/create-sign-doc-url', methods=['POST'])
def create_sign_doc_url():
    try:
        recipient_name = request.form.get('recipient_name')
        recipient_email = request.form.get('recipient_email') 
        doc_type = request.form.get('doc_type')

        headers = {
            'Authorization': f'Zoho-oauthtoken {ZOHO_OAUTH_TOKEN}'
        }

        doc_name,doc_fields,doc_url = get_fields_and_url(doc_type)

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            with requests.get(doc_url, stream=True) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                # Extract filename from URL or headers if available
                filename = (
                    doc_url.split('/')[-1]  # Get last part of URL
                    or r.headers.get('Content-Disposition', '').split('filename=')[-1].strip('"\'')  # From headers
                    or 'document.pdf'  # Fallback
                )

            with open(tmp.name, 'rb') as file:
                # file = request.files.get('file')
                if not file:
                    return make_response(jsonify({'error': 'Invalid document url'}), 400)

                sending_doc_data = {
                    "requests": {
                        "request_name": doc_name,
                        "is_sequential": True,
                        "actions": [
                            {
                                "action_type": "SIGN",
                                "recipient_email": "your_valid_zohosign_user@example.com", 
                                "recipient_name": "Alex James",
                                "signing_order": 0,
                                "verify_recipient": False,
                            },
                        ],
                    }
                }

                files = {
                    'file': (filename, file),
                    'data': (None, json.dumps(sending_doc_data))
                }

                sending_doc_url = 'https://sign.zoho.com/api/v1/requests'
                try:
                    sending_doc_response = requests.post(sending_doc_url, headers=headers, files=files)
                    sending_doc_return_data = sending_doc_response.json()

                    action_id = sending_doc_return_data['requests']['actions'][0]['action_id']
                    document_id = sending_doc_return_data['requests']['document_fields'][0]['document_id']
                    request_id = sending_doc_return_data['requests']['request_id']
                except Exception as e:
                    return make_response(jsonify(sending_doc_response.json()), 500)

        for field in doc_fields:
            field.update({'document_id': document_id})

        submit_data = {
            'requests': {
                'actions': [{
                    'action_id': action_id,
                    'recipient_name': recipient_name,
                    "recipient_email": recipient_email,
                    'in_person_name': recipient_name,
                    'action_type': 'SIGN',
                    'is_embedded': True,
                    'fields': doc_fields
                }]
            }
        }

        try:
            update_doc_response = requests.put(
                f'https://sign.zoho.com/api/v1/requests/{request_id}',
                headers= headers,
                json= submit_data,
            )
        except Exception as e:
            return make_response(jsonify(update_doc_response.json()), 500)

        try:
            submit_doc_response = requests.post(
                f'https://sign.zoho.com/api/v1/requests/{request_id}/submit',
                headers= headers,
                json= submit_data,
            )
        except Exception as e:
            return make_response(jsonify(submit_doc_response.json()), 500)

        # get_embedded_link_headers = {
        #     f'Authorization': 'Bearer {ZOHO_OAUTH_TOKEN}',
        #     'Content-Type': 'application/json'
        # }

        host_name = '' # For embedded iframe

        get_embedded_link_response = requests.post(
            f'https://sign.zoho.com/api/v1/requests/{request_id}/actions/{action_id}/embedtoken',
            headers=headers,
            json = host_name
        )
        embed_response = get_embedded_link_response.json()
        sign_url = embed_response.get('sign_url')

        return make_response(jsonify({'url': f'{sign_url}'}))

    except Exception as e:
        return make_response(jsonify({'error': str(e)}), 500)
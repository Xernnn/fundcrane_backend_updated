import pymongo
import urllib.parse
from app.config import Config

def get_fields_and_url(doc_type: str):
    password = urllib.parse.quote_plus(Config.MONGO_PASSWORD)
    db_url = f"mongodb://{Config.MONGO_USERNAME}:{password}@{Config.MONGO_URL}/template"

    try:
        client = pymongo.MongoClient(db_url)
        db = client['template']
        collection = db['template']
        found_template = collection.find_one({'type': doc_type})
        return found_template['name'], found_template['fields'], found_template['url']
    except pymongo.errors.ConnectionFailure as e:
        print("MongoDB connection failed:", e)
        raise
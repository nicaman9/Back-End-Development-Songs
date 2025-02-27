from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa; F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# client = MongoClient(
#     f"mongodb://{app.config['MONGO_USERNAME']}:{app.config['MONGO_PASSWORD']}@localhost")
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service == None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    # abort(500, 'Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"


print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

######################################################################
# Health Check Endpoint
######################################################################
@app.route("/health", methods=["GET"])
def health():
    """Health check route to monitor the app's status."""
    return jsonify({"status": "OK"}), 200

######################################################################
# Count Endpoint
######################################################################

@app.route("/count", methods=["GET"])
def count():
    """Return the count of documents in the songs collection"""
    try:
        count = db.songs.count_documents({})
        return jsonify({"count": count}), 200
    except Exception as e:
        app.logger.error(f"Error counting documents: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

######################################################################
# Get All Songs Endpoint
######################################################################

@app.route("/song", methods=["GET"])
def songs():
    """Retrieve all songs from the database"""
    try:
        songs_data = list(db.songs.find({}))  # Get all songs from MongoDB
        for song in songs_data:
            song["_id"] = str(song["_id"])  # Convert ObjectId to string
        return jsonify({"songs": songs_data}), 200  # Return the list of songs
    except Exception as e:
        app.logger.error(f"Error retrieving songs: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

######################################################################
# POST Endpoint to Create a Song
######################################################################

@app.route("/song", methods=["POST"])
def create_song():
    """Create a new song in the database, or return an error if the song already exists"""
    try:
        # Extract song data from request body
        song_data = request.get_json()
        song_id = song_data.get("id")

        # Check if a song with the same ID already exists in the database
        existing_song = db.songs.find_one({"id": song_id})

        if existing_song:
            # Return 302 status if the song already exists
            return jsonify({"Message": f"song with id {song_id} already present"}), 302

        # Insert the new song into the database
        result = db.songs.insert_one(song_data)

        # Return success message with the inserted song's ID
        return jsonify({"inserted id": str(result.inserted_id)}), 201

    except Exception as e:
        app.logger.error(f"Error creating song: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

######################################################################
# PUT Endpoint to Update a Song
######################################################################

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """Update an existing song in the database"""
    try:
        # Extract updated song data from the request body
        song_data = request.get_json()

        # Check if song data exists
        if not song_data:
            return jsonify({"message": "No data provided"}), 400

        # Find the existing song by its id
        existing_song = db.songs.find_one({"id": id})

        if not existing_song:
            # If the song is not found, return 404 status
            return jsonify({"message": "song not found"}), 404

        # Check if the incoming data is the same as the existing song data
        if existing_song["lyrics"] == song_data.get("lyrics") and existing_song["title"] == song_data.get("title"):
            return jsonify({"message": "song found, but nothing updated"}), 200

        # Update the song in the database with the provided data
        updated_song = db.songs.update_one(
            {"id": id},  # Match song by its id
            {"$set": song_data}  # Use $set to update the song's fields
        )

        if updated_song.matched_count == 0:
            return jsonify({"message": "song found, but nothing updated"}), 200

        # Fetch the updated song data
        updated_song_data = db.songs.find_one({"id": id})

        # Convert the MongoDB document to JSON format, ensuring ObjectId is serializable
        updated_song_data = json_util.dumps(updated_song_data)
        
        # Return the updated song data
        return updated_song_data, 200

    except Exception as e:
        app.logger.error(f"Error updating song with id {id}: {str(e)}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

######################################################################
# Delete Song
######################################################################
@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    """Delete a song from the database"""
    try:
        # Attempt to delete the song from the database using the provided id
        result = db.songs.delete_one({"id": id})

        if result.deleted_count == 0:
            # If no song was deleted, return 404 with a message
            return jsonify({"message": "song not found"}), 404

        # If the song was deleted successfully, return HTTP 204 No Content
        return '', 204  # Empty body with a 204 status code

    except Exception as e:
        app.logger.error(f"Error deleting song with id {id}: {str(e)}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

import logging
import os

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)

CORS(app, resources={r"/*": {"origins": "*"}})


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/process-document", methods=["POST"])
def process_document_route():
    try:
        if "file" not in request.files:
            return jsonify({"botResponse": "No file uploaded."}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"botResponse": "Empty filename."}), 400

        if not allowed_file(file.filename):
            return jsonify({"botResponse": "Only PDF files are supported."}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, filename)
        file.save(file_path)

        logger.info("File saved to: %s", file_path)

        return jsonify({
            "botResponse": "PDF uploaded successfully.",
            "pdfUrl": f"/uploads/{filename}"
        }), 200

    except Exception as e:
        logger.exception("Failed to process document")
        return jsonify({"botResponse": f"Server error: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=8000, host="0.0.0.0")
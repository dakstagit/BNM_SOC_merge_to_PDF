from flask import Flask, request, jsonify, send_file
from PIL import Image
from PyPDF2 import PdfMerger
import io
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

TEMP_DIR = "/tmp/bnm_merge"
os.makedirs(TEMP_DIR, exist_ok=True)


def image_bytes_to_pdf_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    pdf_buffer = io.BytesIO()
    img.save(pdf_buffer, format="PDF")
    pdf_buffer.seek(0)
    return pdf_buffer.read()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True}), 200


@app.route("/merge-soc", methods=["POST"])
def merge_soc():
    try:
        payload = request.get_json(force=True)
        files = payload.get("files", [])

        if isinstance(files, dict):
            files = [files]

        if not files:
            return jsonify({"success": False, "error": "No files received"}), 400

        merger = PdfMerger()
        temp_paths = []

        try:
            for i, file_obj in enumerate(files, start=1):
                if not isinstance(file_obj, dict):
                    return jsonify({"success": False, "error": f"Invalid file object at index {i}"}), 400

                name = secure_filename(file_obj.get("name", f"file_{i}"))
                mime = (file_obj.get("mime") or "").lower()
                raw_data = file_obj.get("data")

                if raw_data is None:
                    return jsonify({"success": False, "error": f"Missing data for file {name}"}), 400

                # Make Buffer object
                if isinstance(raw_data, dict) and raw_data.get("type") == "Buffer" and isinstance(raw_data.get("data"), list):
                    file_bytes = bytes(raw_data["data"])

                # Raw integer array
                elif isinstance(raw_data, list):
                    file_bytes = bytes(raw_data)

                else:
                    return jsonify({"success": False, "error": f"Unsupported data format for file {name}"}), 400

                unique_prefix = str(uuid.uuid4())

                if mime == "application/pdf" or name.lower().endswith(".pdf"):
                    pdf_path = os.path.join(TEMP_DIR, f"{unique_prefix}_{name}")
                    with open(pdf_path, "wb") as f:
                        f.write(file_bytes)
                    merger.append(pdf_path)
                    temp_paths.append(pdf_path)
                else:
                    try:
                        pdf_bytes = image_bytes_to_pdf_bytes(file_bytes)
                    except Exception:
                        return jsonify({"success": False, "error": f"Could not convert file to PDF: {name}"}), 400

                    pdf_name = os.path.splitext(name)[0] + ".pdf"
                    pdf_path = os.path.join(TEMP_DIR, f"{unique_prefix}_{pdf_name}")
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    merger.append(pdf_path)
                    temp_paths.append(pdf_path)

            merged_filename = f"{uuid.uuid4()}_merged_soc.pdf"
            merged_path = os.path.join(TEMP_DIR, merged_filename)

            with open(merged_path, "wb") as f:
                merger.write(f)

            merger.close()

            return send_file(
                merged_path,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="merged_soc.pdf"
            )

        finally:
            for path in temp_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

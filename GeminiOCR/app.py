from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import json
from datetime import datetime
import sys
import pandas as pd

# Import functions from main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import extract_text_from_image, configure_enhanced_prompt, get_response_schema

app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'GeminiOCR/uploads'
OUTPUT_FOLDER = 'GeminiOCR/output/json'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    invoice_type = request.form.get('invoice_type', 'printing')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        
        try:
            # Get API key from environment
            API_KEY = "AIzaSyDnUHmWDSsrh3X6wImAH4UOgRV1kLUA41E"
            
            # Process image using existing functions
            enhanced_prompt = configure_enhanced_prompt(invoice_type)
            response_schema = get_response_schema(invoice_type)
            extracted_text = extract_text_from_image(
                upload_path, enhanced_prompt, response_schema, API_KEY
            )
            
            # Save results
            output_filename = f"{invoice_type}_{timestamp}.json"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            try:
                json_data = json.loads(extracted_text)
                with open(output_path, 'w', encoding='utf-8') as json_file:
                    json.dump(json_data, json_file, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                with open(output_path, 'w', encoding='utf-8') as json_file:
                    json.dump({"raw_text": extracted_text}, json_file, indent=2, ensure_ascii=False)
            
            return jsonify({
                'success': True,
                'filename': output_filename,
                'results': json.loads(extracted_text) if isinstance(extracted_text, str) else extracted_text
            })
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


@app.route('/download-excel/<filename>')
def download_excel(filename):
    json_path = os.path.join(OUTPUT_FOLDER, filename)
    try:
        # Read the JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        df = pd.json_normalize(data)
        
        # Create Excel file
        excel_filename = filename.replace('.json', '.xlsx')
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        df.to_excel(excel_path, index=False)
        
        return send_file(excel_path, as_attachment=True, download_name=excel_filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, ssl_context='adhoc', debug=True)
import google.generativeai as genai
import os
import PIL.Image
from PIL import ImageEnhance, ImageFilter
import cv2
import numpy as np
import re
from pdf2image import convert_from_path
import tempfile
import json
from datetime import datetime
import pandas as pd

def preprocess_image(image_path):
    """
    Enhance image to improve handwritten text detection.
    """
    # Open the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not open image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply adaptive thresholding to enhance handwritten text
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Dilate to connect nearby text components
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # Find contours to identify potential handwritten regions
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create a mask for handwritten-like regions
    mask = np.zeros_like(gray)
    for contour in contours:
        # Filter contours by size and shape to target handwritten-like content
        area = cv2.contourArea(contour)
        if 100 < area < 10000:  # Adjust these thresholds based on your images
            cv2.drawContours(mask, [contour], -1, 255, -1)

    # Enhance the original image in handwritten regions
    enhanced = image.copy()
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    enhanced_gray[mask > 0] = cv2.equalizeHist(enhanced_gray)[mask > 0]

    # Convert back to RGB
    enhanced = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

    # Save processed image
    processed_path = image_path.replace(".jpg", "_processed.jpg")
    cv2.imwrite(processed_path, enhanced)

    return processed_path


def configure_enhanced_prompt(invoice_type):
    """
    Configure an enhanced prompt based on the invoice type.

    Args:
        invoice_type: The type of invoice (printing or invoice)

    Returns:
        The prompt text to use for OCR
    """
    try:
        prompt_file = f"prompt/{invoice_type}_invoice"
        with open(prompt_file, "r", encoding="utf-8") as file:
            prompt = file.read()
        return prompt
    except Exception as e:
        print(f"Error reading prompt file for {invoice_type}: {e}")
        # Fallback to printing_invoice if available
        try:
            with open(
                "prompt/printing_invoice", "r", encoding="utf-8"
            ) as file:
                prompt = file.read()
            return prompt
        except Exception:
            print("Could not read any prompt files!")
            return ""


def get_response_schema(invoice_type):
    """
    Read and parse a JSON schema file.

    Args:
        json_path: Path to the JSON schema file

    Returns:
        A dictionary containing the parsed JSON schema
    """
    try:
        json_path = f"schema/{invoice_type}_invoice.json"
        with open(json_path, "r", encoding="utf-8") as file:
            schema = json.load(file)
        return schema
    except FileNotFoundError:
        print(f"Schema file not found: {json_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in schema file {json_path}: {e}")
        return None
    except Exception as e:
        print(f"Error reading schema file {json_path}: {e}")
        return None

def extract_text_from_image(image_path, enhanced_prompt,response_schema, api_key):
    """
    Extract text from image using the enhanced pipeline.
    """
    # Preprocess the image to enhance handwritten text
    # processed_image_path = preprocess_image(image_path)
    #processed_image = PIL.Image.open(processed_image_path)
    processed_image= PIL.Image.open(image_path)

    # Configure Gemini API
    genai.configure(api_key=api_key)
    
    # Configure the model
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-preview-04-17",
        ##model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.3,  # Lower temperature for more deterministic OCR results
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        },
    )

    # Make API request with proper structure for response schema
    try:
        response = model.generate_content(
            contents=[enhanced_prompt, processed_image],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        # Return the formatted JSON response
        return response.text
    except Exception as e:
        print(f"Error generating content: {e}")
        # Try a fallback approach without the schema if there's an error
        try:
            fallback_response = model.generate_content(
                contents=[enhanced_prompt, processed_image],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
            return fallback_response.text
        except Exception as f_e:
            print(f"Fallback also failed: {f_e}")
            return f"Error: {e}"



def main():
    # Get API key from environment variable
    API_KEY = "AIzaSyDnUHmWDSsrh3X6wImAH4UOgRV1kLUA41E"  ##os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        print("Please set your GEMINI_API_KEY environment variable")
        return

    try:
        shop_json = json.loads(open("output/json/shop_20250519_082646.json", "r", encoding="utf-8").read())
       

        #loop through shop_json
        rows=[]
        for index, row in enumerate(shop_json):
            issue_info = row['issue_info']
            shop_address = issue_info.get('shop_address', 'N/A')
            shop_code = issue_info.get('shop_code', 'N/A')
            shop_telephone = issue_info.get('shop_telephone', 'N/A')
            shop_name = issue_info.get('brand', 'N/A')
            issue_datetime = issue_info.get('issue_datetime', 'N/A')
            pos_terminal = issue_info.get('pos_terminal', 'N/A')
            issue_number = issue_info.get('issue_number', 'N/A')
            brand = issue_info.get('brand', 'N/A')
            payment = row.get('payment', 'N/A')
            remark = row.get('remark', 'N/A')
            subtotal = row.get('subtotal', 'N/A')
            total_amount = row.get('total_amount', 'N/A')
            discount = row.get('discount', 'N/A')
            details = row.get('details', 'N/A')
            for detail in details:
                item_name = detail.get('item_name', 'N/A')
                quantity = detail.get('quantity', 'N/A')
                unit_price = detail.get('unit_price', 'N/A')
                amount = detail.get('amount', 'N/A')
                row=[item_name, quantity, unit_price, amount, shop_address, shop_code, shop_telephone, shop_name, issue_datetime, pos_terminal, issue_number, brand, payment, remark, subtotal, total_amount, discount]
                rows.append(row)
    
        # for every line in details, get the item_name, quantity, unit_price, amount
        for line in df['details']:
            item_name=line['item_name']
            quantity=line['quantity']
            unit_price=line['unit_price']
            amount=line['amount']
            
            df_line = pd.DataFrame({
                'item_name': [item_name], 
                'quantity': [quantity],
             'unit_price': [unit_price],
              'amount': [amount], 
              'shop_address': [shop_address], 
              'shop_code': [shop_code], 
              'shop_telephone': [shop_telephone], 
              'shop_name': [shop_name], 
              'issue_datetime': [issue_datetime], 
              'pos_terminal': [pos_terminal], 
              'issue_number': [issue_number], 
              'brand': [brand],
              'payment': [payment],
              'remark': [remark],
              'subtotal': [subtotal], 
              'total_amount': [total_amount],
              'discount': [discount]
              })
            
        
        
        # # Create output directory if it doesn't exist
        # os.makedirs("GeminiOCR/output/json", exist_ok=True)
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # invoice_type = input("Enter invoice type (printing/shop): ").lower()
        # if invoice_type == "printing":
        #     image_path = "GeminiOCR/finance_invoice/printing_invoice.jpg"
        #     enhanced_prompt = configure_enhanced_prompt(invoice_type)
        #     response_schema = get_response_schema(invoice_type)
        #     extracted_text = extract_text_from_image(
        #         image_path, enhanced_prompt, response_schema,API_KEY
        #     )
        #     # Generate output filename
        #     output_filename = f"GeminiOCR/output/json/printing_invoice_result_{timestamp}.json"
        # elif invoice_type == "shop":
        #     img_number = input("Enter image number: ")
        #     image_path = f"GeminiOCR/shop_invoice/{img_number}.jpeg"
        #     enhanced_prompt = configure_enhanced_prompt(invoice_type)
        #     response_schema = get_response_schema(invoice_type)
        #     extracted_text = extract_text_from_image(
        #         image_path, enhanced_prompt,response_schema,API_KEY
        #     )
        #     # Generate output filename
        #     output_filename = f"GeminiOCR/output/json/shop_invoice_{img_number}_result_{timestamp}.json"
        
        # # Save extracted text to JSON file
        # try:
        #     # Parse the extracted text as JSON
        #     json_data = json.loads(extracted_text)
        #     with open(output_filename, 'w', encoding='utf-8') as json_file:
        #         json.dump(json_data, json_file, indent=2, ensure_ascii=False)
        #     print(f"Results saved to {output_filename}")
        # except json.JSONDecodeError:
        #     # If the extracted text is not valid JSON, save it as a plain text value
        #     with open(output_filename, 'w', encoding='utf-8') as json_file:
        #         json.dump({"raw_text": extracted_text}, json_file, indent=2, ensure_ascii=False)
        #     print(f"Results saved to {output_filename} as raw text")

    except Exception as e:
        print(f"Error: {e}")




if __name__ == "__main__":
    main()

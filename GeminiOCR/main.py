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
        prompt_file = f"GeminiOCR/prompt/{invoice_type}_invoice"
        with open(prompt_file, "r", encoding="utf-8") as file:
            prompt = file.read()
        return prompt
    except Exception as e:
        print(f"Error reading prompt file for {invoice_type}: {e}")
        # Fallback to printing_invoice if available
        try:
            with open(
                "GeminiOCR/prompt/printing_invoice", "r", encoding="utf-8"
            ) as file:
                prompt = file.read()
            return prompt
        except Exception:
            print("Could not read any prompt files!")
            return ""


def get_response_schema(json_path):
    """
    Read and parse a JSON schema file.

    Args:
        json_path: Path to the JSON schema file

    Returns:
        A dictionary containing the parsed JSON schema
    """
    try:
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

def extract_text_from_image(image_path, enhanced_prompt, api_key):
    """
    Extract text from image using the enhanced pipeline.
    """
    # Preprocess the image to enhance handwritten text
    processed_image_path = preprocess_image(image_path)
    #processed_image = PIL.Image.open(processed_image_path)
    processed_image= PIL.Image.open(image_path)

    # Configure Gemini API
    genai.configure(api_key=api_key)
    
    # Get the schema from file
    response_schema = get_response_schema("GeminiOCR/schema/printing_invoice.json")
    
    # Configure the model
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-preview-04-17",
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
        invoice_type = input("Enter invoice type (printing/invoice): ").lower()
        if invoice_type == "printing":
            image_path = "GeminiOCR/finance_invoice/printing_invoice.jpg"
            enhanced_prompt = configure_enhanced_prompt(invoice_type)
            extracted_text = extract_text_from_image(
                image_path, enhanced_prompt, API_KEY
            )
        elif invoice_type == "invoice":
            img_number = input("Enter image number: ")
            image_path = f"GeminiOCR/shop_invoice/{img_number}.jpg"
            enhanced_prompt = configure_enhanced_prompt(invoice_type)
            extracted_text = extract_text_from_image(
                image_path, enhanced_prompt, API_KEY
            )

        print("\nExtracted Text:")
        print("------------------------")
        print(extracted_text)
        print("------------------------")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

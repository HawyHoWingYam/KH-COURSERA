from google import genai
import os
import PIL.Image
from PIL import ImageEnhance, ImageFilter
import cv2
import numpy as np
import re


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
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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


def configure_enhanced_prompt():
    """
    Configure an enhanced prompt specifically for Chinese handwriting recognition.
    """
    prompt = """
Objective: Perform ultra-precise OCR focusing on Chinese handwritten text in receipt images.

1. Chinese Handwriting Analysis Strategy:
   * Apply multiple recognition passes specifically for handwritten Chinese content
   * Analyze character components (radicals) independently before full character recognition
   * Use contextual positioning of handwriting within receipt structure
   * Consider common receipt annotation patterns (totals, discounts, notes)

2. Chinese Character Recognition Enhancement:
   * For each detected handwritten Chinese character:
     - Analyze stroke count, order, and direction based on visible patterns
     - Consider possible character completion for partially visible strokes
     - Apply knowledge of common handwriting simplifications used in practice
     * Pay special attention to numerals and related characters

3. Confidence and Ambiguity Handling:
   * Present multiple character possibilities for ambiguous handwriting
   * Use knowledge of receipt context to disambiguate characters
   * When uncertain between similar characters, consider semantic meaning within receipt context
   * For numbers, verify against printed totals if possible

4. Output Format Requirements:
   * Present detected handwritten Chinese content at the beginning of your response
   * For each handwritten section detected, provide:
     - The exact characters detected
     - The likely meaning/purpose in the receipt context
     - Confidence level (High/Medium/Low)
   * Then include the complete OCR results for the entire receipt with spatial relationships

5. Special Context Awareness:
   * Recognize that handwritten annotations likely relate to:
     - Payment information
     - Discount calculations
     - Verification marks
     - Quantity modifications
     - Personal notes
   * Use this context to improve character recognition accuracy
"""
    return prompt



def extract_text_from_image(image_path, api_key):
    """
    Extract text from image using the enhanced pipeline.
    """
    # Preprocess the image to enhance handwritten text
    processed_image_path = preprocess_image(image_path)
    processed_image = PIL.Image.open(processed_image_path)

    # Configure Gemini API
    client = genai.Client(api_key=api_key)
    generate_content_config = {
        "temperature": 2,  # Lower temperature for more deterministic results
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
        # "response_mime_type": "text/plain"
    }

    # Use enhanced prompt focused on Chinese handwriting
    enhanced_prompt = configure_enhanced_prompt()

    # Make API request
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[enhanced_prompt, processed_image],
        config=generate_content_config
    )

    return response.text


def main():
    API_KEY = "AIzaSyBm9JxHKs72YAL5zl4eaEVIqj_CijDObFE"
    if not API_KEY:
        print("Please set your GEMINI_API_KEY environment variable")
        return

    try:
        # Get image path
        image_path = "GeminiOCR/img/02.jpg"

        # Extract text from the image using enhanced pipeline
        extracted_text = extract_text_from_image(image_path, API_KEY)

        # Print the extracted text
        print("\nExtracted Text:")
        print("------------------------")
        print(extracted_text)
        print("------------------------")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

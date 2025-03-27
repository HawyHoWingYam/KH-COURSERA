from google import genai
from google.genai import types
import os
import pathlib
from IPython.display import display, Markdown
import PIL.Image
import base64
import requests
from io import BytesIO


def configure_genai(api_key):
    """Configure the Gemini API with your API key."""
    genai.configure(api_key=api_key)
    # Create the model
    return {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }


def extract_text_from_image(image, api_key):
    client = genai.Client(api_key=api_key)
    generate_content_config = configure_genai(api_key)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=["Please extract all the text from the image", image],
        config=generate_content_config
    )

    return response.text


def main():
    # Replace with your actual API key
    # API_KEY = os.environ.get("GEMINI_API_KEY")
    API_KEY = "AIzaSyBm9JxHKs72YAL5zl4eaEVIqj_CijDObFE"
    if not API_KEY:
        print("Please set your GEMINI_API_KEY environment variable")
        return

    # Example usage with local file
    try:
        # Get image path from user
        image = PIL.Image.open("GeminiOCR/img/01.jpg")
        # Extract text from the image
        extracted_text = extract_text_from_image(image, API_KEY)

        # Print the extracted text
        print("\nExtracted Text:")
        print("------------------------")
        print(extracted_text)
        print("------------------------")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

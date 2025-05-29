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
    Enhance image to improve text detection.
    """
    # Open the image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not open image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply adaptive thresholding to enhance text
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Dilate to connect nearby text components
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # Find contours to identify potential text regions
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create a mask for text regions
    mask = np.zeros_like(gray)
    for contour in contours:
        # Filter contours by size and shape to target text content
        area = cv2.contourArea(contour)
        if 100 < area < 10000:  # Adjust these thresholds based on your images
            cv2.drawContours(mask, [contour], -1, 255, -1)

    # Enhance the original image in text regions
    enhanced = image.copy()
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    enhanced_gray[mask > 0] = cv2.equalizeHist(enhanced_gray)[mask > 0]

    # Convert back to RGB
    enhanced = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

    # Save processed image
    processed_path = image_path.replace(".jpg", "_processed.jpg")
    cv2.imwrite(processed_path, enhanced)

    return processed_path


def configure_prompt(doc_type, provider_name):
    """
    Configure a prompt based on the document type and provider.

    Args:
        doc_type: The type of document (e.g., invoice, receipt)
        provider_name: The provider/company name

    Returns:
        The prompt text to use for OCR
    """
    try:
        # Look for provider-specific prompt
        prompt_file = os.path.join(
            os.getcwd(),
            "document_type",
            doc_type,
            provider_name,
            "prompt",
            f"{provider_name}.txt",
        )
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as file:
                prompt = file.read()
            return prompt

        # Fallback to generic document type prompt if available
        generic_prompt = os.path.join(
            os.getcwd(), "document_type", doc_type, "prompt", f"{doc_type}.txt"
        )
        if os.path.exists(generic_prompt):
            with open(generic_prompt, "r", encoding="utf-8") as file:
                prompt = file.read()
            return prompt

        print(f"No prompt found for {doc_type}/{provider_name}")
        return ""
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        return ""


def load_config():
    """
    Load configuration from config.json
    """
    try:
        with open(
            os.path.join(os.getcwd(), "env", "config.json"),
            "r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return None


def get_response_schema(doc_type, provider_name):
    """
    Read and parse a JSON schema file.

    Args:
        doc_type: The type of document (e.g., invoice, receipt)
        provider_name: The provider/company name

    Returns:
        A dictionary containing the parsed JSON schema
    """
    try:
        # Look for provider-specific schema
        schema_file = os.path.join(
            os.getcwd(),
            "document_type",
            doc_type,
            provider_name,
            "schema",
            f"{provider_name}.json",
        )
        if os.path.exists(schema_file):
            with open(schema_file, "r", encoding="utf-8") as file:
                schema = json.load(file)
            return schema

        # Fallback to generic document type schema
        generic_schema = os.path.join(
            os.getcwd(), "document_type", doc_type, "schema", f"{doc_type}.json"
        )
        if os.path.exists(generic_schema):
            with open(generic_schema, "r", encoding="utf-8") as file:
                schema = json.load(file)
            return schema

        print(f"Schema file not found for {doc_type}/{provider_name}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in schema file: {e}")
        return None
    except Exception as e:
        print(f"Error reading schema file: {e}")
        return None


def extract_text_from_image(
    image_path, enhanced_prompt, response_schema, api_key, model_name
):
    """
    Extract text from image using the enhanced pipeline.
    """
    # Preprocess the image to enhance text
    # processed_image_path = preprocess_image(image_path)
    # processed_image = PIL.Image.open(processed_image_path)
    processed_image = PIL.Image.open(image_path)

    # Configure Gemini API
    genai.configure(api_key=api_key)

    # Configure the model
    model = genai.GenerativeModel(
        model_name=model_name,
        ##model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.3,  # Lower temperature for more deterministic OCR results
            "top_p": 0.95,
            "top_k": 40,
            # "max_output_tokens": 8192,
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
        print(response.usage_metadata)
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


def extract_text_from_pdf(
    pdf_path, enhanced_prompt, response_schema, api_key, model_name
):
    """
    Extract text directly from PDF using Gemini API.
    """
    # Configure Gemini API
    genai.configure(api_key=api_key)

    # Load PDF as bytes
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    # Configure the model
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            # "max_output_tokens": 8192,
        },
    )

    # Make API request with PDF
    try:
        response = model.generate_content(
            contents=[
                enhanced_prompt,
                {"mime_type": "application/pdf", "data": pdf_data},
            ],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        print(response.usage_metadata)
        # Return the formatted JSON response
        return response.text
    except Exception as e:
        print(f"Error generating content from PDF: {e}")
        # Try a fallback approach without the schema if there's an error
        try:
            fallback_response = model.generate_content(
                contents=[
                    enhanced_prompt,
                    {"mime_type": "application/pdf", "data": pdf_data},
                ],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
            return fallback_response.text
        except Exception as f_e:
            print(f"PDF processing fallback also failed: {f_e}")
            return f"Error: {e}"


def main():
    try:
        with open(
            os.path.join(os.getcwd(), "env", "config.json"), "r", encoding="utf-8"
        ) as file:
            config = json.load(file)
            API_KEY = config["api_key"]

        if not API_KEY:
            print("Please set your GEMINI_API_KEY in config.json")
            return

        try:
            # Load configuration
            config = load_config()
            if not config:
                print("Failed to load configuration")
                return

            # Get available document types
            doc_types = [
                d
                for d in os.listdir(os.path.join(os.getcwd(), "document_type"))
                if os.path.isdir(os.path.join(os.getcwd(), "document_type", d))
            ]

            print("Available document types:")
            for i, doc_type in enumerate(doc_types, 1):
                print(f"{i}. {doc_type}")

            # Select document type
            while True:
                try:
                    choice = int(input(f"Select document type (enter number): "))
                    if 1 <= choice <= len(doc_types):
                        selected_doc_type = doc_types[choice - 1]
                        break
                    print(f"Please enter a number between 1 and {len(doc_types)}.")
                except ValueError:
                    print("Please enter a valid number.")

            # Step 1: Ask how many documents to process
            while True:
                try:
                    num_docs = int(
                        input(
                            f"How many {selected_doc_type} documents do you want to process? "
                        )
                    )
                    if num_docs > 0:
                        break
                    print("Please enter a positive number.")
                except ValueError:
                    print("Please enter a valid number.")

            # Step 2: Show provider list for the selected document type
            providers = [
                d
                for d in os.listdir(
                    os.path.join(os.getcwd(), "document_type", selected_doc_type)
                )
                if os.path.isdir(
                    os.path.join(os.getcwd(), "document_type", selected_doc_type, d)
                )
            ]

            print(f"Available {selected_doc_type} providers:")
            for i, provider in enumerate(providers, 1):
                print(f"{i}. {provider}")

            selected_providers = []
            for i in range(num_docs):
                while True:
                    try:
                        choice = int(
                            input(
                                f"Select provider for {selected_doc_type} #{i+1} (enter number): "
                            )
                        )
                        if 1 <= choice <= len(providers):
                            selected_providers.append(providers[choice - 1])
                            break
                        print(f"Please enter a number between 1 and {len(providers)}.")
                    except ValueError:
                        print("Please enter a valid number.")

            # Step 3: Process each document
            for i, provider in enumerate(selected_providers):
                # Ask for file name with file extension
                file_name = input(
                    f"Enter the file name for {provider} {selected_doc_type} with file type (e.g. document_01.jpg): "
                )

                # Construct file path
                file_path = os.path.join(
                    os.getcwd(),
                    "document_type",
                    selected_doc_type,
                    provider,
                    "upload",
                    file_name,
                )

                # Check if file exists
                if not os.path.exists(file_path):
                    print(f"File {file_path} does not exist. Skipping.")
                    continue

                # Get prompt and schema
                prompt = configure_prompt(selected_doc_type, provider)
                schema = get_response_schema(selected_doc_type, provider)

                if not prompt:
                    print(f"No prompt found for {provider}. Skipping.")
                    continue

                if not schema:
                    print(f"No schema found for {provider}. Skipping.")
                    continue

                # Process the document
                print(f"Processing {provider} {selected_doc_type}: {file_name}...")
                extracted_text = extract_text_from_image(
                    file_path, prompt, schema, API_KEY
                )

                # Create output directory if it doesn't exist
                output_dir = os.path.join(
                    os.getcwd(), "document_type", selected_doc_type, provider, "output"
                )
                os.makedirs(output_dir, exist_ok=True)

                # Generate output filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = os.path.join(
                    output_dir, f"{provider}_{timestamp}.json"
                )

                # Save extracted text to JSON file
                try:
                    # Parse the extracted text as JSON
                    json_data = json.loads(extracted_text)
                    with open(output_filename, "w", encoding="utf-8") as json_file:
                        json.dump(json_data, json_file, indent=2, ensure_ascii=False)
                    print(f"Results saved to {output_filename}")
                except json.JSONDecodeError:
                    # If the extracted text is not valid JSON, save it as a plain text value
                    with open(output_filename, "w", encoding="utf-8") as json_file:
                        json.dump(
                            {"raw_text": extracted_text},
                            json_file,
                            indent=2,
                            ensure_ascii=False,
                        )
                    print(f"Results saved to {output_filename} as raw text")

        except Exception as e:
            print(f"Error: {e}")

    except Exception as e:
        print(f"Error loading config: {e}")


if __name__ == "__main__":
    main()

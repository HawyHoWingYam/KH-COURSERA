import pandas as pd
import json
import os
from typing import Dict, List, Any, Union


def extract_text_value(value: Any) -> Any:
    """Extract text value from objects with {source, text} structure."""
    if (
        isinstance(value, dict)
        and "text" in value
        and isinstance(value["text"], (str, int, float))
    ):
        return value["text"]
    return value


def flatten_dict(d: Dict, parent_key: str = "", sep: str = "_") -> Dict:
    """Recursively flatten a nested dictionary, handling special text extraction patterns."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        # Handle text extraction pattern
        extracted_value = extract_text_value(v)
        if extracted_value != v:
            items.append((new_key, extracted_value))
            continue

        if isinstance(v, dict):
            # Recursive flatten for nested dictionaries
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            # Skip lists of dicts - they'll be handled separately as tables
            continue
        else:
            items.append((new_key, v))
    return dict(items)


def format_key_for_display(key: str) -> str:
    """Format a key for display in Excel."""
    # Convert snake_case or camelCase to Title Case With Spaces
    words = []
    current_word = ""

    for char in key:
        if char == "_":
            if current_word:
                words.append(current_word)
                current_word = ""
        elif char.isupper() and current_word and not current_word[-1].isupper():
            words.append(current_word)
            current_word = char
        else:
            current_word += char

    if current_word:
        words.append(current_word)

    return " ".join(word.capitalize() for word in words)


def normalize_table_data(table_data: List[Dict]) -> pd.DataFrame:
    """Convert table data to pandas DataFrame with normalized structure."""
    # First pass: extract text values from objects
    normalized_rows = []

    for item in table_data:
        normalized_row = {}
        for key, value in item.items():
            # Extract text value if it's a {source, text} object
            extracted_value = extract_text_value(value)

            if extracted_value != value and not isinstance(extracted_value, dict):
                # If text was extracted, use it directly
                normalized_row[key] = extracted_value
            elif isinstance(value, dict):
                # If it's a dictionary, flatten it
                flattened = flatten_dict(value, key)
                normalized_row.update(flattened)
            else:
                # For simple values
                normalized_row[key] = value

        normalized_rows.append(normalized_row)

    # Convert to DataFrame
    df = pd.DataFrame(normalized_rows)

    # Format column names
    if not df.empty:
        df.columns = [format_key_for_display(col) for col in df.columns]

    return df


def json_to_excel(
    json_datas: Union[Dict, List], output_path: str, doc_type_code: str = None
) -> str:
    # Create a single DataFrame from the data

    main_df = None
    for json_data in json_datas:
        sub_df = None
        for key, value in json_data.items():
            if (
                isinstance(value, list)
                and value
                and all(isinstance(x, dict) for x in value)
            ):
                # Found a table, use this as the main structure
                table_df = normalize_table_data(value)
                if not table_df.empty:
                    sub_df = table_df
                    break

        # If no tables were found, create an empty DataFrame
        if sub_df is None:
            sub_df = pd.DataFrame()

        # Inject metadata as columns
        for key, value in json_data.items():
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                # Skip tables
                continue

            # Handle simple values and text extraction
            if isinstance(value, dict):
                extracted_value = extract_text_value(value)
                if extracted_value != value and not isinstance(extracted_value, dict):
                    # Simple text extraction
                    col_name = format_key_for_display(key)
                    sub_df[col_name] = extracted_value
                else:
                    # Flatten nested dictionaries
                    flattened = flatten_dict(value)
                    for sub_key, sub_value in flattened.items():
                        full_key = f"{key}_{sub_key}" if sub_key else key
                        col_name = format_key_for_display(full_key)
                        sub_df[col_name] = sub_value
            else:
                # Simple metadata field
                col_name = format_key_for_display(key)
                sub_df[col_name] = value

        if sub_df is not None:
            if main_df is None:
                main_df = sub_df
            else:
                main_df = pd.concat([main_df, sub_df], ignore_index=True)

    # Write to Excel
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sheet_name = doc_type_code[:30] if doc_type_code else "Data"

        if main_df.empty:
            # If we have no data, create a simple placeholder
            main_df = pd.DataFrame(
                {"No Data": ["No structured data found in the input JSON"]}
            )

        # Write main dataframe
        main_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Auto-adjust column widths
        worksheet = writer.sheets[sheet_name]

        # Apply auto-filter to all columns
        worksheet.auto_filter.ref = worksheet.dimensions

        # Auto-adjust column widths
        for idx, col in enumerate(main_df.columns):
            # Calculate max length
            max_len = (
                max(
                    main_df[col].astype(str).map(len).max() if len(main_df) > 0 else 0,
                    len(str(col)),
                )
                + 2
            )  # adding a little extra space

            # Convert column index to letter (A, B, C, etc.)
            col_idx = idx
            col_letter = ""
            while True:
                col_letter = chr(65 + (col_idx % 26)) + col_letter
                col_idx = col_idx // 26 - 1
                if col_idx < 0:
                    break

            worksheet.column_dimensions[col_letter].width = min(
                max_len, 50
            )  # Cap at 50

    return output_path

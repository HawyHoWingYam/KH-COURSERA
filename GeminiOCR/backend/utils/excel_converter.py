import pandas as pd
import json
import os
import logging
from typing import Dict, List, Any, Union

# Set up logging
logger = logging.getLogger(__name__)


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


def sanitize_sheet_name(name: str) -> str:
    """
    Sanitize a string to be used as an Excel sheet name.
    Excel sheet names cannot contain: \ / * ? [ ] : '
    And must be 31 characters or less.
    """
    if not name:
        return "Data"
    
    # Remove invalid characters
    invalid_chars = ['\\', '/', '*', '?', '[', ']', ':', "'", '"']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '')
    
    # Replace multiple underscores with single underscore
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure it's not empty after sanitization
    if not sanitized:
        sanitized = "Data"
    
    # Limit to 31 characters (Excel limit)
    if len(sanitized) > 31:
        sanitized = sanitized[:31].rstrip('_')
    
    return sanitized


def json_to_excel(
    json_datas: Union[Dict, List], output_path: str, doc_type_code: str = None
) -> str:
    # 確保json_datas是列表
    if isinstance(json_datas, dict):
        json_datas = [json_datas]
    
    # 創建主DataFrame
    main_df = None
    
    for json_data in json_datas:
       
        # 處理單個對象的情況 - 將整個對象視為一行數據
        if isinstance(json_data, dict):
            # 扁平化嵌套字典
            flat_data = {}
            for key, value in json_data.items():
                if isinstance(value, dict):
                    # 處理嵌套字典
                    nested_flat = flatten_dict(value, key)
                    flat_data.update(nested_flat)
                elif isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    # 嘗試解析JSON字符串
                    try:
                        json_value = json.loads(value)
                        if isinstance(json_value, dict):
                            nested_flat = flatten_dict(json_value, key)
                            flat_data.update(nested_flat)
                        else:
                            flat_data[key] = value
                    except:
                        flat_data[key] = value
                else:
                    # 一般值
                    flat_data[key] = value
            
            # 創建單行DataFrame
            row_df = pd.DataFrame([flat_data])
            
            # 合併到主DataFrame
            if main_df is None:
                main_df = row_df
            else:
                main_df = pd.concat([main_df, row_df], ignore_index=True)
        
        # 原有的表格處理邏輯
        sub_df = None
        for key, value in json_data.items():
            if (
                isinstance(value, list)
                and value
                and all(isinstance(x, dict) for x in value)
            ):
                # 找到表格結構
                table_df = normalize_table_data(value)
                if not table_df.empty:
                    sub_df = table_df
                    break
        
        # 如果找到表格結構，合併到主DataFrame
        if sub_df is not None and not sub_df.empty:
            if main_df is None:
                main_df = sub_df
            else:
                main_df = pd.concat([main_df, sub_df], ignore_index=True)
    
    # 寫入Excel的代碼保持不變
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            sheet_name = sanitize_sheet_name(doc_type_code) if doc_type_code else "Data"
            logger.info(f"Creating Excel sheet with name: '{sheet_name}' (sanitized from: '{doc_type_code}')")

            if main_df is None or main_df.empty:
                # 如果沒有數據，創建一個簡單的佔位符
                main_df = pd.DataFrame(
                    {"No Data": ["No structured data found in the input JSON"]}
                )
                logger.warning("No structured data found, creating placeholder DataFrame")

            # 寫入主DataFrame
            try:
                main_df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"Successfully wrote data to Excel sheet '{sheet_name}'")
            except Exception as excel_write_error:
                logger.error(f"Error writing to Excel sheet '{sheet_name}': {str(excel_write_error)}")
                # Try with a fallback sheet name
                fallback_sheet_name = "Data"
                logger.info(f"Attempting to write with fallback sheet name: '{fallback_sheet_name}'")
                main_df.to_excel(writer, sheet_name=fallback_sheet_name, index=False)

            # Auto-adjust column widths
            try:
                # Use the actual sheet name that was written
                actual_sheet_name = sheet_name if sheet_name in writer.sheets else "Data"
                worksheet = writer.sheets[actual_sheet_name]

                # Apply auto-filter to all columns
                if worksheet.dimensions:
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
                
                logger.info(f"Successfully applied formatting to Excel sheet")
                
            except Exception as format_error:
                logger.warning(f"Error applying Excel formatting: {str(format_error)}")
                # Continue without formatting - file is still usable

    except Exception as e:
        logger.error(f"Critical error creating Excel file: {str(e)}")
        # Create a minimal Excel file as fallback
        try:
            fallback_df = pd.DataFrame({
                "Error": [f"Excel conversion failed: {str(e)}"],
                "Original_Data": [str(json_datas)[:500] + "..." if len(str(json_datas)) > 500 else str(json_datas)]
            })
            fallback_df.to_excel(output_path, sheet_name="Error", index=False)
            logger.info("Created fallback Excel file with error information")
        except Exception as fallback_error:
            logger.error(f"Failed to create fallback Excel file: {str(fallback_error)}")
            raise e  # Re-raise the original error if fallback also fails

    return output_path

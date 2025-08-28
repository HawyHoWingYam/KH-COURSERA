import pandas as pd
import json
import os
import logging
from typing import Dict, List, Any, Union

# --- 日誌設定 (Setup Logging) ---
# 建立一個 logger，用於在程式執行時輸出資訊
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def flatten_json_recursive(data: Any, parent_key: str = '', sep: str = '.') -> List[Dict[str, Any]]:
    """
    遞迴地將複雜的巢狀 JSON (字典和列表) 轉換為扁平化的記錄列表。
    每一筆記錄都代表 Excel 中的一列。

    Args:
        data (Any): 要處理的 JSON 資料 (可以是字典或列表)。
        parent_key (str): 用於追蹤巢狀結構的父鍵。
        sep (str): 用於連接父鍵和子鍵的分隔符。

    Returns:
        List[Dict[str, Any]]: 一個扁平化的字典列表，準備好轉換為 DataFrame。
    """
    
    # 用於存放最終扁平化結果的列表
    flattened_records = []

    # --- 情況 1: 輸入的資料是字典 (dict) ---
    if isinstance(data, dict):
        # 將字典中的鍵值對分為兩類：
        # 1. simple_items: 值是簡單類型 (字串、數字等) 的項目
        # 2. nested_list_items: 值是列表 (list) 的項目，這部分需要展開
        simple_items = {}
        nested_list_items = {}

        for k, v in data.items():
            # 建立新的鍵名，例如 'statement_details.number'
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            # 如果值是列表且包含字典，則視為需要展開的巢狀列表
            if isinstance(v, list) and v and all(isinstance(i, dict) for i in v):
                nested_list_items[new_key] = v
            # 否則，視為簡單的鍵值對
            else:
                simple_items[new_key] = v

        # 如果沒有需要展開的巢狀列表
        if not nested_list_items:
            flattened_records.append(simple_items)
        else:
            # 這是核心的「展開」邏輯
            # 取得第一個需要展開的列表
            list_key, list_to_explode = list(nested_list_items.items())[0]
            
            # 取得其他尚未處理的巢狀列表
            remaining_nested_lists = {k: v for i, (k, v) in enumerate(nested_list_items.items()) if i > 0}

            # 遍歷要展開的列表中的每一個項目
            for item in list_to_explode:
                # 建立一個新的基礎記錄，包含父層級的簡單鍵值對
                new_record_base = simple_items.copy()
                
                # 將列表中的項目 (它本身是一個字典) 與剩餘的巢狀列表合併
                # 這樣可以遞迴地處理多層巢狀列表
                combined_item = {**item, **remaining_nested_lists}

                # 遞迴呼叫函式，處理這個合併後的項目
                # 將父層級的鍵名傳入，以維持正確的層級關係
                # 例如，處理 'charge_description' 時，父鍵是 'statement_details'
                sub_records = flatten_json_recursive(combined_item, parent_key=parent_key, sep=sep)
                
                # 將父層級的簡單資料，與遞迴展開後的子記錄合併
                for sub_record in sub_records:
                    final_record = {**new_record_base, **sub_record}
                    flattened_records.append(final_record)

    # --- 情況 2: 輸入的資料是列表 (list) ---
    elif isinstance(data, list):
        # 如果是列表，則遍歷其中的每一個項目，並分別進行遞迴處理
        for item in data:
            flattened_records.extend(flatten_json_recursive(item, parent_key, sep))

    return flattened_records

def sanitize_sheet_name(name: str) -> str:
    """
    清理字串，使其符合 Excel 工作表名稱的規範。
    - 不能包含 \ / * ? [ ] : ' " 等字元
    - 長度不能超過 31 個字元
    """
    if not name:
        return "Data"
    
    invalid_chars = ['\\', '/', '*', '?', '[', ']', ':', "'", '"']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '')
    
    sanitized = sanitized.strip('_')
    
    if not sanitized:
        sanitized = "Data"
    
    return sanitized[:31]

def json_to_excel(json_data: Union[Dict, List], output_path: str, doc_type_code: str = "Sheet1") -> str:
    """
    將 JSON 資料轉換為極度扁平化的 Excel 檔案。

    Args:
        json_data (Union[Dict, List]): 輸入的 JSON 資料。
        output_path (str): Excel 檔案的儲存路徑。
        doc_type_code (str): Excel 工作表的名稱。

    Returns:
        str: 輸出檔案的路徑。
    """
    logger.info("開始將 JSON 轉換為扁平化記錄...")
    
    # 呼叫核心遞迴函式，將 JSON 轉換為扁平化的字典列表
    flattened_data = flatten_json_recursive(json_data)
    
    if not flattened_data:
        logger.warning("在 JSON 中找不到可處理的資料，將建立一個空的 Excel 檔案。")
        df = pd.DataFrame({"Message": ["No data found in the JSON input."]})
    else:
        # 將扁平化的記錄列表轉換為 pandas DataFrame
        df = pd.DataFrame(flattened_data)
        logger.info(f"資料轉換完成，共產生 {len(df)} 筆記錄。")

    # --- 將 DataFrame 寫入 Excel 檔案 ---
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            sheet_name = sanitize_sheet_name(doc_type_code)
            logger.info(f"正在寫入資料到工作表: '{sheet_name}'...")
            
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # --- 自動調整欄位寬度與套用篩選 ---
            worksheet = writer.sheets[sheet_name]
            worksheet.auto_filter.ref = worksheet.dimensions

            for idx, col in enumerate(df.columns):
                series = df[col]
                max_len = max(
                    series.astype(str).map(len).max(),
                    len(str(series.name))
                ) + 2
                
                # 將欄位索引轉換為字母 (A, B, C...)
                col_letter = chr(65 + idx) if idx < 26 else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
                worksheet.column_dimensions[col_letter].width = min(max_len, 60) # 寬度上限為 60

        logger.info(f"成功建立 Excel 檔案: {output_path}")

    except Exception as e:
        logger.error(f"建立 Excel 檔案時發生嚴重錯誤: {str(e)}")
        raise

    return output_path

# --- 主程式執行區塊 ---
if __name__ == '__main__':
    # --- 範例使用 ---
    # 1. 讀取您的 results.json 檔案
    try:
        # 假設有一個名為 'results.json' 的檔案在同一個資料夾
        input_filename = 'results.json'
        with open(input_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"成功讀取 {input_filename} 檔案。")
        
        # 2. 設定輸出檔案的路徑
        # 自動產生輸出檔名，例如 'results_converted.xlsx'
        base_name = os.path.splitext(input_filename)[0]
        output_filename = f'{base_name}_converted.xlsx'
        
        # 3. 執行轉換
        json_to_excel(data, output_filename, doc_type_code="Sheet1")

    except FileNotFoundError:
        logger.error(f"錯誤: '{input_filename}' 檔案不存在。請確認檔案是否在正確的路徑下。")
    except json.JSONDecodeError:
        logger.error(f"錯誤: '{input_filename}' 內容不是有效的 JSON 格式。")
    except Exception as e:
        logger.error(f"處理過程中發生未預期的錯誤: {e}")

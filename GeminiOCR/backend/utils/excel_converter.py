import pandas as pd
import json
import os
import logging
import itertools
from typing import Dict, List, Any, Union, Tuple

# --- 日誌設定 (Setup Logging) ---
# 建立一個 logger，用於在程式執行時輸出資訊
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def flatten_json_recursive(
    data: Any, parent_key: str = "", sep: str = "."
) -> List[Dict[str, Any]]:
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
            remaining_nested_lists = {
                k: v for i, (k, v) in enumerate(nested_list_items.items()) if i > 0
            }

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
                sub_records = flatten_json_recursive(
                    combined_item, parent_key=parent_key, sep=sep
                )

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

    invalid_chars = ["\\", "/", "*", "?", "[", "]", ":", "'", '"']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, "")

    sanitized = sanitized.strip("_")

    if not sanitized:
        sanitized = "Data"

    return sanitized[:31]


def json_to_excel(
    json_data: Union[Dict, List], output_path: str, doc_type_code: str = "Sheet1"
) -> str:
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
                max_len = (
                    max(series.astype(str).map(len).max(), len(str(series.name))) + 2
                )

                # 將欄位索引轉換為字母 (A, B, C...)
                col_letter = (
                    chr(65 + idx)
                    if idx < 26
                    else chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
                )
                worksheet.column_dimensions[col_letter].width = min(
                    max_len, 60
                )  # 寬度上限為 60

        logger.info(f"成功建立 Excel 檔案: {output_path}")

    except Exception as e:
        logger.error(f"建立 Excel 檔案時發生嚴重錯誤: {str(e)}")
        raise

    return output_path


# --- 新增：通用深度扁平化函式 (Universal Deep Flattening Functions) ---

def find_all_arrays(data: Any, path: str = "") -> List[Tuple[str, List]]:
    """
    遞迴地找出所有的陣列及其路徑位置。
    
    Args:
        data: 要分析的資料
        path: 當前路徑
        
    Returns:
        List of tuples containing (path, array_data)
    """
    arrays = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            if isinstance(value, list) and value:
                # 檢查是否為包含字典的陣列（需要展開的陣列）
                if all(isinstance(item, dict) for item in value):
                    arrays.append((new_path, value))
                # 遞迴檢查陣列中的每個元素
                for i, item in enumerate(value):
                    item_path = f"{new_path}[{i}]"
                    arrays.extend(find_all_arrays(item, item_path))
            else:
                arrays.extend(find_all_arrays(value, new_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            item_path = f"{path}[{i}]" if path else f"[{i}]"
            arrays.extend(find_all_arrays(item, item_path))
    
    return arrays


def extract_primitives(data: Any, path: str = "") -> Dict[str, Any]:
    """
    提取所有原始值（非陣列、非物件）及其路徑。
    
    Args:
        data: 要分析的資料
        path: 當前路徑
        
    Returns:
        Dictionary mapping paths to primitive values
    """
    primitives = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            if isinstance(value, (str, int, float, bool)) or value is None:
                primitives[new_path] = value
            elif isinstance(value, dict):
                primitives.update(extract_primitives(value, new_path))
            # 忽略陣列，它們會被單獨處理
    elif isinstance(data, (str, int, float, bool)) or data is None:
        primitives[path] = data
    
    return primitives


def generate_array_combinations(arrays_info: List[Tuple[str, List]]) -> List[Dict[str, Any]]:
    """
    為所有陣列生成笛卡爾積組合。
    
    Args:
        arrays_info: 陣列資訊列表 [(路徑, 陣列資料)]
        
    Returns:
        所有可能組合的列表
    """
    if not arrays_info:
        return [{}]
    
    combinations = []
    
    # 準備所有陣列的索引範圍
    array_ranges = []
    for path, array_data in arrays_info:
        array_ranges.append([(path, i, item) for i, item in enumerate(array_data)])
    
    # 生成笛卡爾積
    for combination in itertools.product(*array_ranges):
        combo_data = {}
        for path, index, item in combination:
            # 提取該陣列項目的所有原始值
            item_primitives = extract_primitives(item, path)
            combo_data.update(item_primitives)
        combinations.append(combo_data)
    
    return combinations


def deep_flatten_json_universal(data: Any, parent_key: str = "", sep: str = ".") -> List[Dict[str, Any]]:
    """
    通用深度扁平化函式，將任何巢狀 JSON 結構完全展開到最深層級。
    
    這個函式會遞迴地展開所有陣列，確保每一行代表最深層級的一個項目。
    與原始演算法不同的是，這個版本會持續深入到最深層級。
    
    Args:
        data: 輸入的 JSON 資料
        parent_key: 父級鍵名（用於維持層次結構）
        sep: 路徑分隔符
        
    Returns:
        完全扁平化的記錄列表
    """
    flattened_records = []
    
    # 如果輸入是陣列，遞迴處理每個項目
    if isinstance(data, list):
        for item in data:
            flattened_records.extend(deep_flatten_json_universal(item, parent_key, sep))
        return flattened_records
    
    # 如果不是字典，直接返回原始值
    if not isinstance(data, dict):
        return [{parent_key: data}] if parent_key else [{"value": data}]
    
    # 分離簡單值和需要展開的項目
    simple_items = {}
    expandable_items = {}
    
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, list) and v:
            # 檢查是否為包含字典的陣列（需要展開的陣列）
            if all(isinstance(i, dict) for i in v):
                expandable_items[new_key] = v
            else:
                # 包含原始值的陣列，直接當作簡單值處理
                simple_items[new_key] = v
        elif isinstance(v, dict):
            # 嵌套字典，展開其內容
            expandable_items[new_key] = [v]  # 將字典包裝成單項目陣列，方便統一處理
        else:
            # 原始值
            simple_items[new_key] = v
    
    # 如果沒有需要展開的項目，返回簡單值
    if not expandable_items:
        return [simple_items]
    
    # 處理展開邏輯 - 類似原始演算法，但確保到達最深層級
    # 選擇第一個需要展開的項目
    first_key, first_array = list(expandable_items.items())[0]
    remaining_expandable = {k: v for i, (k, v) in enumerate(expandable_items.items()) if i > 0}
    
    # 為第一個陣列的每個項目建立記錄
    for item in first_array:
        # 建立基礎記錄（包含簡單值）
        base_record = simple_items.copy()
        
        # 將目前項目與剩餘的展開項目結合
        combined_item = {**item, **remaining_expandable}
        
        # 遞迴處理結合後的項目
        sub_records = deep_flatten_json_universal(combined_item, parent_key, sep)
        
        # 將基礎記錄與子記錄結合
        for sub_record in sub_records:
            final_record = {**base_record, **sub_record}
            flattened_records.append(final_record)
    
    return flattened_records


def ultra_deep_flatten_json(data: Any, parent_key: str = "", sep: str = ".", max_depth: int = 20) -> List[Dict[str, Any]]:
    """
    Ultra-comprehensive JSON flattening with explicit path-based naming and depth control.
    
    This function ensures EVERY nested object and array is completely flattened with 
    full path traceability in column names.
    
    Args:
        data: Input JSON data
        parent_key: Parent key for maintaining hierarchy
        sep: Path separator for column naming
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        List of completely flattened records with explicit path-based column names
    """
    if max_depth <= 0:
        logger.warning(f"Maximum recursion depth reached, truncating further expansion")
        return [{"_truncated_path": parent_key, "_value": str(data)[:100]}]
    
    flattened_records = []
    
    # Handle arrays
    if isinstance(data, list):
        if not data:  # Empty array
            return [{f"{parent_key}_empty_array": True}] if parent_key else [{"empty_array": True}]
        
        for idx, item in enumerate(data):
            array_key = f"{parent_key}[{idx}]" if parent_key else f"item[{idx}]"
            sub_records = ultra_deep_flatten_json(item, array_key, sep, max_depth - 1)
            flattened_records.extend(sub_records)
        return flattened_records
    
    # Handle non-dict primitives
    if not isinstance(data, dict):
        key = parent_key if parent_key else "value"
        return [{key: data}]
    
    # Handle empty dict
    if not data:
        return [{f"{parent_key}_empty_object": True}] if parent_key else [{"empty_object": True}]
    
    # Separate primitive values from complex structures
    primitives = {}
    complex_structures = {}
    
    for key, value in data.items():
        full_key = f"{parent_key}{sep}{key}" if parent_key else key
        
        if isinstance(value, (str, int, float, bool, type(None))):
            primitives[full_key] = value
        elif isinstance(value, list):
            if not value:  # Empty list
                primitives[f"{full_key}_empty_list"] = True
            elif all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                # List of primitives - convert to string or keep as list
                primitives[f"{full_key}_list"] = value
            else:
                # List containing complex objects
                complex_structures[full_key] = value
        elif isinstance(value, dict):
            if not value:  # Empty dict
                primitives[f"{full_key}_empty_dict"] = True
            else:
                complex_structures[full_key] = value
        else:
            # Handle other types (e.g., custom objects)
            primitives[f"{full_key}_other"] = str(value)
    
    # If no complex structures, return primitives
    if not complex_structures:
        return [primitives]
    
    # Handle complex structures using Cartesian product approach
    # This ensures ALL combinations are captured
    structure_combinations = []
    
    for struct_key, struct_value in complex_structures.items():
        struct_records = ultra_deep_flatten_json(struct_value, struct_key, sep, max_depth - 1)
        structure_combinations.append(struct_records)
    
    # Generate Cartesian product of all structure combinations
    if structure_combinations:
        # Use itertools.product for Cartesian product
        import itertools
        for combination in itertools.product(*structure_combinations):
            # Merge all records in this combination
            merged_record = primitives.copy()
            for record in combination:
                merged_record.update(record)
            flattened_records.append(merged_record)
    else:
        flattened_records.append(primitives)
    
    return flattened_records


def json_to_csv(
    json_data: Union[Dict, List], output_path: str, doc_type_code: str = "data"
) -> str:
    """
    將 JSON 資料轉換為完全扁平化的 CSV 檔案。
    
    Args:
        json_data: 輸入的 JSON 資料
        output_path: CSV 檔案的儲存路徑
        doc_type_code: 用於日誌的文件類型代碼
        
    Returns:
        輸出檔案的路徑
    """
    logger.info("開始將 JSON 轉換為深度扁平化 CSV...")
    
    # 使用新的通用深度扁平化函式
    flattened_data = deep_flatten_json_universal(json_data)
    
    if not flattened_data:
        logger.warning("在 JSON 中找不到可處理的資料，將建立一個空的 CSV 檔案。")
        df = pd.DataFrame({"Message": ["No data found in the JSON input."]})
    else:
        # 將扁平化的記錄列表轉換為 pandas DataFrame
        df = pd.DataFrame(flattened_data)
        logger.info(f"資料轉換完成，共產生 {len(df)} 筆記錄，{len(df.columns)} 個欄位。")
        logger.info(f"欄位名稱: {list(df.columns)}")
    
    try:
        # 將 DataFrame 寫入 CSV 檔案
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"成功建立 CSV 檔案: {output_path}")
        
    except Exception as e:
        logger.error(f"建立 CSV 檔案時發生錯誤: {str(e)}")
        raise
    
    return output_path


def json_to_csv_ultra_flat(
    json_data: Union[Dict, List], output_path: str, doc_type_code: str = "data"
) -> str:
    """
    將 JSON 資料轉換為極度扁平化的 CSV 檔案，使用 ultra_deep_flatten_json 函式。
    提供完整的路徑追蹤和最大化的資料展開。
    
    Args:
        json_data: 輸入的 JSON 資料
        output_path: CSV 檔案的儲存路徑
        doc_type_code: 用於日誌的文件類型代碼
        
    Returns:
        輸出檔案的路徑
    """
    logger.info("開始將 JSON 轉換為極度扁平化 CSV (Ultra-flat mode)...")
    
    # 使用極度扁平化函式
    flattened_data = ultra_deep_flatten_json(json_data)
    
    if not flattened_data:
        logger.warning("在 JSON 中找不到可處理的資料，將建立一個空的 CSV 檔案。")
        df = pd.DataFrame({"Message": ["No data found in the JSON input."]})
    else:
        # 將扁平化的記錄列表轉換為 pandas DataFrame
        df = pd.DataFrame(flattened_data)
        logger.info(f"極度扁平化完成，共產生 {len(df)} 筆記錄，{len(df.columns)} 個欄位。")
        logger.info(f"前15個欄位名稱: {list(df.columns)[:15]}")
        
        # 檢查是否有未展開的巢狀資料
        nested_columns = []
        for col in df.columns:
            sample_val = df[col].iloc[0] if len(df) > 0 else None
            if isinstance(sample_val, (dict, list)):
                nested_columns.append(col)
        
        if nested_columns:
            logger.warning(f"警告：仍有 {len(nested_columns)} 個欄位包含巢狀資料: {nested_columns[:5]}")
        else:
            logger.info("✅ 所有資料已完全扁平化")
    
    try:
        # 將 DataFrame 寫入 CSV 檔案
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"成功建立極度扁平化 CSV 檔案: {output_path}")
        
    except Exception as e:
        logger.error(f"建立 CSV 檔案時發生錯誤: {str(e)}")
        raise
    
    return output_path


# --- 主程式執行區塊 ---
if __name__ == "__main__":
    # --- 範例使用 ---
    # 1. 讀取您的 results.json 檔案
    try:
        # 假設有一個名為 'results.json' 的檔案在同一個資料夾
        input_filename = "results.json"
        with open(input_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"成功讀取 {input_filename} 檔案。")

        # 2. 設定輸出檔案的路徑
        # 自動產生輸出檔名，例如 'results_converted.xlsx'
        base_name = os.path.splitext(input_filename)[0]
        output_filename = f"{base_name}_converted.xlsx"

        # 3. 執行轉換
        json_to_excel(data, output_filename, doc_type_code="Sheet1")

    except FileNotFoundError:
        logger.error(
            f"錯誤: '{input_filename}' 檔案不存在。請確認檔案是否在正確的路徑下。"
        )
    except json.JSONDecodeError:
        logger.error(f"錯誤: '{input_filename}' 內容不是有效的 JSON 格式。")
    except Exception as e:
        logger.error(f"處理過程中發生未預期的錯誤: {e}")

# 前端修改指南 - Item 文件管理系统

**文件**: `GeminiOCR/frontend/src/app/orders/[id]/page.tsx`

## 1. 修改接口定义

### OrderItem 接口（第28-46行）
需要添加新的字段：
```typescript
interface OrderItem {
  // ... 现有字段 ...
  file_count: number;  // 现在只计算附件
  primary_file: {      // 新增
    file_id: number;
    filename: string;
    file_size: number;
    file_type: string;
    uploaded_at: string;
  } | null;
  attachments: Array<{  // 新增
    file_id: number;
    filename: string;
    file_size: number;
    file_type: string;
    upload_order: number;
    uploaded_at: string;
  }>;
  attachment_count: number;  // 新增
  // ... 其他字段 ...
}
```

## 2. 移除 Add Mode UI

### 步骤 2.1: 删除状态变量（第83-84行）
**删除这两行**:
```typescript
const [modalMode, setModalMode] = useState<'upload' | 'month'>('upload');
const [modalAwbMonth, setModalAwbMonth] = useState('');
```

### 步骤 2.2: 删除 addOrderItemWithMonthAttach 方法（第249-313行）
**完全删除这个方法**

### 步骤 2.3: 修改 addOrderItem 方法（第199-247行）
**替换整个方法为**:
```typescript
const addOrderItem = async () => {
  if (!selectedCompany || !selectedDocType) {
    setError('Please select both company and document type');
    return;
  }

  setIsAddingItem(true);
  try {
    const response = await fetch(`/api/orders/${orderId}/items`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        company_id: selectedCompany,
        doc_type_id: selectedDocType,
        item_name: itemName || undefined
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to add item');
    }

    // Reset form and close modal
    setSelectedCompany(null);
    setSelectedDocType(null);
    setItemName('');
    setShowAddItemModal(false);

    // Reload order to show new item
    loadOrder();
  } catch (error) {
    console.error('Error adding item:', error);
    setError('Failed to add item');
  } finally {
    setIsAddingItem(false);
  }
};
```

### 步骤 2.4: 移除 Modal 中的 Mode Toggle 和 Month Fields（第1572-1651行）
**完全删除**:
- Lines 1572-1610: Mode Toggle 按钮
- Lines 1629-1651: Month Attach Mode Fields

替换为简单的 Item Name 输入：
```typescript
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Item Name (Optional)
  </label>
  <input
    type="text"
    value={itemName}
    onChange={(e) => setItemName(e.target.value)}
    placeholder="Leave empty for auto-generated name"
    className="w-full border border-gray-300 rounded px-3 py-2"
  />
</div>
```

## 3. 添加主文件部分到 Item 卡片

### 位置: 第1190-1290行（item 卡片内部）

**替换第1191-1231行（当前的文件列表部分）为**:

```typescript
{/* Primary File Section */}
{item.primary_file ? (
  <div className="border-b pb-3 mb-3">
    <h4 className="font-medium text-gray-700 mb-2">📄 Primary File</h4>
    <div className="flex justify-between items-center bg-blue-50 p-2 rounded">
      <div className="flex-1">
        <p className="text-sm font-medium">{item.primary_file.filename}</p>
        <p className="text-xs text-gray-500">{(item.primary_file.file_size / 1024).toFixed(1)}KB</p>
      </div>
      <div className="flex gap-2">
        {item.status === 'COMPLETED' && item.ocr_result_json_path && (
          <button
            onClick={() => downloadItemResult(item.item_id, 'json', item.item_name)}
            disabled={downloadingFiles[`${item.item_id}-json`]}
            className="bg-blue-100 hover:bg-blue-200 disabled:bg-gray-200 text-blue-700 disabled:text-gray-500 px-2 py-1 rounded text-xs font-medium"
            title="Download primary file JSON"
          >
            {downloadingFiles[`${item.item_id}-json`] ? '...' : '📄 JSON'}
          </button>
        )}
        {canEdit && (
          <>
            <button
              onClick={() => {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.pdf,.jpg,.jpeg,.png';
                input.onchange = (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (file) uploadPrimaryFile(item.item_id, file);
                };
                input.click();
              }}
              className="text-blue-600 hover:text-blue-800 px-2 py-1 text-xs font-medium"
              title="Replace primary file"
            >
              🔄 Replace
            </button>
            <button
              onClick={() => {
                if (window.confirm('Delete primary file?')) {
                  deletePrimaryFile(item.item_id);
                }
              }}
              className="text-red-600 hover:text-red-800 px-2 py-1 text-xs font-medium"
              title="Delete primary file"
            >
              🗑️ Delete
            </button>
          </>
        )}
      </div>
    </div>
  </div>
) : (
  canEdit && (
    <div className="border-b pb-3 mb-3">
      <h4 className="font-medium text-gray-700 mb-2">📄 Primary File</h4>
      <button
        onClick={() => {
          const input = document.createElement('input');
          input.type = 'file';
          input.accept = '.pdf,.jpg,.jpeg,.png';
          input.onchange = (e) => {
            const file = (e.target as HTMLInputElement).files?.[0];
            if (file) uploadPrimaryFile(item.item_id, file);
          };
          input.click();
        }}
        className="bg-blue-100 hover:bg-blue-200 text-blue-700 py-2 px-3 rounded text-sm font-medium"
      >
        📤 Upload Primary File
      </button>
    </div>
  )
)}

{/* Attachments Section */}
<div>
  <h4 className="font-medium text-gray-700 mb-2">📎 Attachments ({item.attachment_count})</h4>
  {item.attachments && item.attachments.length > 0 ? (
    <div className="border rounded-lg p-3 bg-gray-50 mb-3">
      <button
        onClick={() => setExpandedItemFiles(prev => ({
          ...prev,
          [item.item_id]: !prev[item.item_id]
        }))}
        className="flex items-center gap-2 font-medium text-gray-700 hover:text-gray-900 w-full text-left"
      >
        <span>{expandedItemFiles[item.item_id] ? '▼' : '▶'}</span>
        <span>📎 Attached Files ({item.attachments.length})</span>
      </button>
      {expandedItemFiles[item.item_id] && (
        <div className="text-xs text-gray-600 space-y-1 mt-2 pl-4">
          {item.attachments.map((file: any) => {
            const deleteKey = `${item.item_id}-${file.file_id}`;
            return (
              <div key={file.file_id} className="flex items-center justify-between py-1 hover:bg-white hover:px-2 hover:rounded transition">
                <div className="truncate flex-1">
                  <span className="text-green-600">📎</span> {file.filename} ({(file.file_size / 1024).toFixed(1)}KB)
                </div>
                <div className="flex gap-1">
                  {item.status === 'COMPLETED' && (
                    <button
                      onClick={() => downloadAttachmentJson(item.item_id, file.file_id)}
                      disabled={downloadingFiles[`${item.item_id}-${file.file_id}-json`]}
                      className="text-blue-600 hover:text-blue-800 disabled:text-gray-400 text-xs font-medium"
                      title="Download attachment JSON"
                    >
                      {downloadingFiles[`${item.item_id}-${file.file_id}-json`] ? '...' : '📄'}
                    </button>
                  )}
                  {canEdit && (
                    <button
                      onClick={() => deleteFile(item.item_id, file.file_id, file.filename)}
                      disabled={deletingFiles[deleteKey]}
                      className="ml-1 text-red-600 hover:text-red-800 disabled:text-gray-400 text-xs font-medium"
                      title={`Delete ${file.filename}`}
                    >
                      {deletingFiles[deleteKey] ? '...' : '✕'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  ) : (
    <div className="text-gray-400 text-sm mb-3">No attachments yet</div>
  )}
</div>
```

## 4. 添加新的前端函数

### 在第315-344行后添加这些新函数:

```typescript
// Upload primary file
const uploadPrimaryFile = async (itemId: number, file: File) => {
  setUploadingFiles(prev => ({ ...prev, [itemId]: true }));

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`/api/orders/${orderId}/items/${itemId}/primary-file`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Failed to upload primary file');
    }

    // Reload order to show updated files
    loadOrder();
  } catch (error) {
    console.error('Error uploading primary file:', error);
    setError('Failed to upload primary file');
  } finally {
    setUploadingFiles(prev => ({ ...prev, [itemId]: false }));
  }
};

// Delete primary file
const deletePrimaryFile = async (itemId: number) => {
  setUploadingFiles(prev => ({ ...prev, [itemId]: true }));

  try {
    const response = await fetch(`/api/orders/${orderId}/items/${itemId}/primary-file`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete primary file');
    }

    // Reload order to show updated files
    loadOrder();
  } catch (error) {
    console.error('Error deleting primary file:', error);
    setError('Failed to delete primary file');
  } finally {
    setUploadingFiles(prev => ({ ...prev, [itemId]: false }));
  }
};

// Download attachment JSON
const downloadAttachmentJson = async (itemId: number, fileId: number) => {
  const downloadKey = `${itemId}-${fileId}-json`;
  setDownloadingFiles(prev => ({ ...prev, [downloadKey]: true }));

  try {
    const response = await fetch(`/api/orders/${orderId}/items/${itemId}/files/${fileId}/download/json`);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to download attachment JSON');
    }

    const data = await response.json();

    // Create download link
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data.json_data, null, 2)));
    element.setAttribute('download', `item_${itemId}_file_${fileId}_result.json`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  } catch (error) {
    console.error('Error downloading attachment JSON:', error);
    setError(error instanceof Error ? error.message : 'Failed to download attachment JSON');
  } finally {
    setDownloadingFiles(prev => ({ ...prev, [downloadKey]: false }));
  }
};
```

## 5. 修改 uploadFilesToItem 函数

### 第315-344行
更新 docstring 和注释：
```typescript
const uploadFilesToItem = async (itemId: number, files: FileList) => {
  // This now uploads ATTACHMENTS only, not primary file
  // Use uploadPrimaryFile for primary file uploads
```

## 总结

完成以上修改后，前端将：
1. ✅ 移除 Add Mode 选择界面
2. ✅ 显示分离的 Primary File 和 Attachments
3. ✅ 允许上传/替换/删除主文件
4. ✅ 支持逐附件下载 JSON 结果
5. ✅ 保留"从月份附加"功能在 item 卡片内

**测试步骤**:
1. 创建 item → 应该没有 mode 选择
2. 上传主文件 → 应显示在"Primary File"部分
3. 上传附件 → 应显示在"Attachments"部分
4. 处理完成后 → 应能下载主文件 JSON 和每个附件 JSON

# Item 文件管理系统 - 实施状态

## ✅ 已完成 (8/12)

### 数据库层
- ✅ **models.py**: 添加 `primary_file_id` 列到 `OcrOrderItem`（line 342）
- ✅ **migration**: 创建 Alembic 迁移文件 `001_add_primary_file_id_to_order_items.py`

### 后端 API 端点
- ✅ **POST /orders/{id}/items/{id}/primary-file**: 上传/替换主文件（line 3198）
- ✅ **DELETE /orders/{id}/items/{id}/primary-file**: 删除主文件（line 3297）
- ✅ **GET /orders/{id}/items/{id}/files/{id}/download/json**: 下载附件JSON（line 3399）
- ✅ **POST /orders/{id}/items/{id}/files**: 调整为仅处理附件（line 3470）

### 后端响应结构调整
- ✅ **GET /orders/{id}**: 返回分离的 primary_file + attachments（line 2783）
- ✅ **GET /orders/{id}/items/{id}/files**: 返回分离的结构（line 3579）

### 处理逻辑（OrderProcessor）
- ✅ **_get_ordered_file_links()**: 辅助方法，优先级返回主文件（line 618）
- ✅ **_generate_item_csv_with_default_mapping()**: CSV生成方法（line 646）

---

## ⏳ 待完成 (4/12)

### 1. Processing: 整合CSV映射到 _save_item_results

**位置**: `GeminiOCR/backend/utils/order_processor.py:932`

**必要改动**:
在 `_save_item_results` 方法中，需要：
1. 调用新的 `_generate_item_csv_with_default_mapping()` 替代原有的 `json_to_csv()`
2. 将映射CSV作为 `item.ocr_result_csv_path`

**伪代码**:
```python
async def _save_item_results(self, item_id: int, ...):
    # 现有的文件级结果保存逻辑...

    # 改动：使用新的映射CSV生成
    primary_result = results[0] if results else None  # 或从primary_file提取
    attachment_results = results[1:] if len(results) > 1 else []

    csv_path = await self._generate_item_csv_with_default_mapping(
        item_id, primary_result, attachment_results
    )
```

### 2. Frontend: 移除 Add Mode UI

**文件**: `GeminiOCR/frontend/src/app/orders/[id]/page.tsx`

**移除项目**:
- Line 249: `addOrderItemWithMonthAttach` 方法
- Line 1569, 1593, 1607, 1629: Modal mode UI 元素
- State: `modalMode` 状态变量

**保留项目**:
- "Attach from Month" 按钮（在item卡片内）
- Item创建只创建空item

### 3. Frontend: 添加主文件部分

**文件**: `GeminiOCR/frontend/src/app/orders/[id]/page.tsx`

**修改位置**: Item卡片（line ~1180）

**新增UI部分**:
```jsx
// 主文件部分
{item.primary_file ? (
  <div className="border-b pb-3 mb-3">
    <h4>📄 主文件 (Primary)</h4>
    <div className="flex justify-between items-center">
      <div>
        <p>{item.primary_file.filename}</p>
        <p className="text-sm text-gray-500">{formatFileSize(item.primary_file.file_size)}</p>
      </div>
      <div className="space-x-2">
        <button onClick={() => downloadJson(item.item_id)} className="text-blue-600">📄 JSON</button>
        <button onClick={() => deletePrimaryFile(item.item_id)} className="text-red-600">🗑️</button>
      </div>
    </div>
  </div>
) : (
  <div className="border-b pb-3 mb-3">
    <h4>📄 主文件 (Primary)</h4>
    <input type="file" onChange={(e) => uploadPrimaryFile(item.item_id, e.target.files[0])} />
  </div>
)}

// 附件部分
<div>
  <h4>📎 附件 ({item.attachment_count})</h4>
  {item.attachments.map((file) => (
    <div key={file.file_id} className="flex justify-between items-center p-2 bg-gray-50">
      <span>{file.filename}</span>
      <div className="space-x-2">
        <button onClick={() => downloadAttachmentJson(item.item_id, file.file_id)} className="text-blue-600">📄 JSON</button>
        <button onClick={() => deleteAttachment(item.item_id, file.file_id)} className="text-red-600">🗑️</button>
      </div>
    </div>
  ))}
  <button onClick={() => document.getElementById(`attachInput_${item.item_id}`).click()}>
    📎 上传附件
  </button>
  <input id={`attachInput_${item.item_id}`} type="file" multiple onChange={(e) => uploadAttachments(item.item_id, e.target.files)} style={{display: 'none'}} />
</div>
```

### 4. Frontend: 添加前端函数

**文件**: `GeminiOCR/frontend/src/app/orders/[id]/page.tsx`

**新增函数**:
```typescript
// 主文件上传
async function uploadPrimaryFile(orderId: number, itemId: number, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`/api/orders/${orderId}/items/${itemId}/primary-file`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

// 主文件删除
async function deletePrimaryFile(orderId: number, itemId: number) {
  return await fetch(`/api/orders/${orderId}/items/${itemId}/primary-file`, {
    method: 'DELETE'
  });
}

// 附件JSON下载
async function downloadAttachmentJson(orderId: number, itemId: number, fileId: number) {
  const res = await fetch(`/api/orders/${orderId}/items/${itemId}/files/${fileId}/download/json`);
  const data = await res.json();
  // 下载JSON或显示
}

// 上传附件
async function uploadAttachments(orderId: number, itemId: number, files: FileList) {
  const formData = new FormData();
  for (let file of files) {
    formData.append('files', file);
  }
  return await fetch(`/api/orders/${orderId}/items/${itemId}/files`, {
    method: 'POST',
    body: formData
  });
}
```

---

## 实施步骤

### 步骤1: 数据库迁移
```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend
python -m alembic upgrade head
```

### 步骤2: 测试后端API
```bash
# 创建item → 上传主文件 → 附加月度文件（或上传附件）
curl -X POST http://localhost:8000/orders/1/items/1/primary-file -F "file=@test.pdf"
curl http://localhost:8000/orders/1/items/1/files
```

### 步骤3: 完成处理逻辑整合（需要手动）
编辑 `order_processor.py` 的 `_save_item_results` 方法

### 步骤4: 前端修改
编辑 `orders/[id]/page.tsx` 实现UI和函数

---

## API 总结

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/orders/{id}/items/{id}/primary-file` | 上传主文件 |
| DELETE | `/orders/{id}/items/{id}/primary-file` | 删除主文件 |
| GET | `/orders/{id}/items/{id}/files/{id}/download/json` | 下载附件JSON |
| POST | `/orders/{id}/items/{id}/files` | 上传附件（多文件） |
| GET | `/orders/{id}/items/{id}/files` | 列出分离的primary_file + attachments |
| GET | `/orders/{id}` | 获取订单（包含分离的文件列表） |

---

## 数据流

```
用户流程:
1. 创建 Order
2. 创建 Item (无文件)
3. 上传主文件 → POST /primary-file → 设置 item.primary_file_id
4. 上传附件 → POST /files → 增加 item.file_count
5. 附加月度文件（可选）→ POST /awb/attach-month
6. 触发OCR处理
   - 主文件优先处理 → item_{id}_primary.json
   - 附件逐个处理 → file_{id}_result.json
   - CSV映射生成 → item_{id}_mapped.csv
7. 下载结果:
   - JSON: GET /download/json (主文件)
   - 附件JSON: GET /files/{id}/download/json
   - CSV: 从item的ocr_result_csv_path
```

---

## S3 结果组织

```
results/orders/
  {item_id//1000}/
    items/
      {item_id}/
        item_{item_id}_primary.json          # 主文件JSON
        item_{item_id}_mapped.csv            # 映射后的CSV
        files/
          file_{file_id}_result.json         # 附件JSON
        item_{item_id}_file_results.json     # 文件结果manifest
```

---

## 待处理注意事项

1. **默认Mapping Keys**: 需要通过管理端配置（已在 `/admin/configs` 实现）
2. **向后兼容性**: 现有的无主文件items仍可处理（仅用附件生成CSV）
3. **文件清理**: 替换主文件时会清理旧的JSON和CSV
4. **权限检查**: 所有API端点都需要验证order状态为DRAFT

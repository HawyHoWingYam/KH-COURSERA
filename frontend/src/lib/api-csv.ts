export interface CsvHeadersResponse {
  item_id: number;
  headers: string[];
  total_headers: number;
}

export interface MergedCsvResponse {
  headers: string[];
  total_records: number;
  export_url?: string;
}

/**
 * Fetch CSV headers from primary item JSON result
 */
export async function fetchCsvHeaders(
  orderId: number,
  itemId: number
): Promise<CsvHeadersResponse> {
  const response = await fetch(`/api/orders/${orderId}/items/${itemId}/primary/csv/headers`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch CSV headers');
  }

  return response.json();
}

/**
 * Download merged CSV from primary and attachment files
 */
export async function downloadMergedCsv(
  orderId: number,
  itemId: number,
  joinKey: string,
  setErrorMessage?: (message: string) => void
): Promise<void> {
  const formData = new FormData();
  formData.append('join_key', joinKey);

  const response = await fetch(`/api/orders/${orderId}/items/${itemId}/merge/csv`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to merge CSV');
  }

  // Check if merged CSV was saved to database
  const mergedSaved = response.headers.get('X-Merged-Saved');
  if (mergedSaved === 'true' && setErrorMessage) {
    // Show success toast message
    setErrorMessage('✅ 已保存到訂單，可以直接啟動 mapping 流程');
    setTimeout(() => setErrorMessage(''), 5000);
  }

  // Get filename from response headers
  const contentDisposition = response.headers.get('content-disposition');
  let filename = `order_${orderId}_item_${itemId}_merged_by_${joinKey}.csv`;

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }

  // Create download link
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Download attachment CSV result
 */
export async function downloadAttachmentCsv(
  orderId: number,
  itemId: number,
  fileId: number
): Promise<void> {
  const response = await fetch(`/api/orders/${orderId}/items/${itemId}/files/${fileId}/download/csv`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to download attachment CSV');
  }

  // Get filename from response headers
  const contentDisposition = response.headers.get('content-disposition');
  let filename = `item_${itemId}_file_${fileId}_result.csv`;

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }

  // Create download link
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Get available join keys from CSV headers
 */
export function getAvailableJoinKeys(headers: string[]): string[] {
  return headers.filter(header =>
    header.toLowerCase().includes('id') ||
    header.toLowerCase().includes('key') ||
    header.toLowerCase().includes('name') ||
    header.toLowerCase().includes('code') ||
    header.toLowerCase().includes('ref') ||
    header.toLowerCase().includes('number') ||
    header.toLowerCase().includes('invoice')
  );
}
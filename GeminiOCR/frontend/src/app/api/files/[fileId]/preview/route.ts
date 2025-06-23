import { NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs/promises';
import * as XLSX from 'xlsx';

// The route that handles file preview requests
export async function GET(
  request: Request,
  context: { params: { fileId: string } }
) {
  const { fileId } = context.params;
  try {
    // Use await when accessing params
    const fileIdParam = await fileId;
    const fileId = parseInt(fileIdParam);
    
    if (isNaN(fileId)) {
      return NextResponse.json(
        { error: 'Invalid file ID' },
        { status: 400 }
      );
    }
    
    console.log(`Processing preview request for file ID: ${fileId}`);
    
    // Get the actual file information from your backend
    const response = await fetch(`${process.env.API_BASE_URL || 'http://localhost:8000'}/files/${fileId}`);
    
    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to get file information: ${response.statusText}` },
        { status: response.status }
      );
    }
    
    const fileInfo = await response.json();
    console.log(`File info:`, fileInfo);
    
    // Now fetch the actual file content from your backend download endpoint
    const fileResponse = await fetch(`${process.env.API_BASE_URL || 'http://localhost:8000'}/download/${fileId}`);
    
    if (!fileResponse.ok) {
      return NextResponse.json(
        { error: `Failed to download file: ${fileResponse.statusText}` },
        { status: fileResponse.status }
      );
    }

    // Process the file based on type
    if (fileInfo.file_name.endsWith('.json')) {
      // For JSON files, just pass through the response
      const jsonData = await fileResponse.json();
      return NextResponse.json(jsonData);
    }
    
    if (fileInfo.file_name.endsWith('.xlsx') || fileInfo.file_name.endsWith('.xls')) {
      // For Excel files, need to convert to a table format
      const arrayBuffer = await fileResponse.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[sheetName];
      
      // Convert to JSON
      const data = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
      
      // Separate headers and rows
      const headers = data[0] || [];
      const rows = data.slice(1);
      
      return NextResponse.json({ headers, rows });
    }
    
    return NextResponse.json(
      { error: 'Preview not available for this file type' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Error generating preview:', error);
    return NextResponse.json(
      { error: `Failed to generate preview: ${error instanceof Error ? error.message : 'Unknown error'}` },
      { status: 500 }
    );
  }
}


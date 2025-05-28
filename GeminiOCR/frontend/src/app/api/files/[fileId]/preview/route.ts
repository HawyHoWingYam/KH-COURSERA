import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import * as XLSX from 'xlsx';
import path from 'path';
import fs from 'fs/promises';

// Define interfaces for database results
interface FileRecord {
  file_id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  file_type: string;
}

export async function GET(
  request: Request,
  { params }: { params: { fileId: string } }
) {
  try {
    const fileId = parseInt(params.fileId);
    
    if (isNaN(fileId)) {
      return NextResponse.json(
        { error: 'Invalid file ID' },
        { status: 400 }
      );
    }
    
    console.log(`Processing preview request for file ID: ${fileId}`);
    
    // This is the path to the actual invoice directory we saw in your file structure
    // Update this to point to your real backend directory
    const baseDir = path.join(process.cwd(), '..', 'backend', 'uploads', 'hana', 'invoice', '27');
    
    // Simple logic to determine which file to serve based on the ID
    // In production, you would query a database to get the actual file path
    const filename = fileId % 2 === 0 ? 'results.json' : 'results.xlsx';
    const filePath = path.join(baseDir, filename);
    
    console.log(`Attempting to read file at: ${filePath}`);
    
    // Check if file exists
    try {
      await fs.access(filePath);
      console.log(`File found at: ${filePath}`);
    } catch (e) {
      console.error(`File not found at: ${filePath}`);
      return NextResponse.json({ error: `File not found: ${filePath}` }, { status: 404 });
    }
    
    // Process the file based on type
    if (filename.endsWith('.json')) {
      const fileContent = await readFile(filePath, 'utf-8');
      const jsonData = JSON.parse(fileContent);
      return NextResponse.json(jsonData);
    }
    
    if (filename.endsWith('.xlsx') || filename.endsWith('.xls')) {
      const fileContent = await readFile(filePath);
      const workbook = XLSX.read(fileContent, { type: 'buffer' });
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


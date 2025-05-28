import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import * as XLSX from 'xlsx';
import path from 'path';
import fs from 'fs/promises';
import { Pool } from 'pg';

// Set up PostgreSQL connection pool
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:admin@localhost:5432/document_processing_platform',
});

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
    
    // Query database to get file information
    let fileRecord: FileRecord | null = null;
    
    try {
      // Get file path from database
      const client = await pool.connect();
      try {
        const result = await client.query(
          `SELECT f.file_id, f.file_name, f.file_path, f.file_size, f.file_type
           FROM files f
           WHERE f.file_id = $1`,
          [fileId]
        );
        
        if (result.rows.length > 0) {
          fileRecord = result.rows[0] as FileRecord;
        }
      } finally {
        client.release();
      }
    } catch (dbError) {
      console.error('Database error:', dbError);
      return NextResponse.json(
        { error: 'Failed to query database' },
        { status: 500 }
      );
    }
    
    if (!fileRecord) {
      console.error(`File record not found for ID: ${fileId}`);
      return NextResponse.json(
        { error: 'File record not found in database' },
        { status: 404 }
      );
    }
    
    console.log(`File record found: ${JSON.stringify(fileRecord)}`);
    
    // Construct the full path to the file
    // Adjust the path joining based on your actual file storage structure
    const filePath = path.join(process.cwd(), '..', 'backend', fileRecord.file_path);
    
    console.log(`Attempting to read file at: ${filePath}`);
    
    // Check if file exists
    try {
      await fs.access(filePath);
      console.log(`File found at: ${filePath}`);
    } catch (e) {
      console.error(`File not found at: ${filePath}`);
      return NextResponse.json(
        { error: `File not found at path: ${filePath}` },
        { status: 404 }
      );
    }
    
    // Process the file based on type
    if (fileRecord.file_name.endsWith('.json')) {
      const fileContent = await readFile(filePath, 'utf-8');
      const jsonData = JSON.parse(fileContent);
      return NextResponse.json(jsonData);
    }
    
    if (fileRecord.file_name.endsWith('.xlsx') || fileRecord.file_name.endsWith('.xls')) {
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


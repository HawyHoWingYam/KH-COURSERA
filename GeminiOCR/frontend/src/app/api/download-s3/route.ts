import { NextRequest, NextResponse } from 'next/server';

// S3 download proxy route - reuses existing proxy pattern from file preview
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const s3Path = searchParams.get('s3_path');
    
    if (!s3Path) {
      return NextResponse.json(
        { error: 'S3 path parameter is required' },
        { status: 400 }
      );
    }
    
    console.log(`Proxying S3 download request for: ${s3Path}`);
    
    // Proxy request to backend using the same pattern as file preview
    const backendUrl = `${process.env.API_BASE_URL || 'http://localhost:8000'}/download-s3?s3_path=${encodeURIComponent(s3Path)}`;
    
    const response = await fetch(backendUrl);
    
    if (!response.ok) {
      console.error(`Backend download failed: ${response.status} ${response.statusText}`);
      return NextResponse.json(
        { error: `Download failed: ${response.statusText}` },
        { status: response.status }
      );
    }
    
    // Get the response headers for file metadata
    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    const contentDisposition = response.headers.get('content-disposition');
    const contentLength = response.headers.get('content-length');
    
    // Stream the file content back to the client
    const fileStream = response.body;
    
    if (!fileStream) {
      return NextResponse.json(
        { error: 'No file content received from backend' },
        { status: 500 }
      );
    }
    
    // Create response with proper headers for file download
    const headers = new Headers();
    headers.set('Content-Type', contentType);
    
    if (contentDisposition) {
      headers.set('Content-Disposition', contentDisposition);
    }
    
    if (contentLength) {
      headers.set('Content-Length', contentLength);
    }
    
    // Add CORS headers for external access
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET');
    
    return new NextResponse(fileStream, {
      headers,
    });
    
  } catch (error) {
    console.error('Error proxying S3 download:', error);
    return NextResponse.json(
      { error: `Download proxy failed: ${error instanceof Error ? error.message : 'Unknown error'}` },
      { status: 500 }
    );
  }
}
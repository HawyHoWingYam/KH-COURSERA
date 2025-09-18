import { NextRequest, NextResponse } from 'next/server';

// S3 presigned URL proxy route - for better download performance
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const s3Path = searchParams.get('s3_path');
    const expiresIn = searchParams.get('expires_in') || '3600';
    
    if (!s3Path) {
      return NextResponse.json(
        { error: 'S3 path parameter is required' },
        { status: 400 }
      );
    }
    
    console.log(`Proxying S3 presigned URL request for: ${s3Path}`);
    
    // Proxy request to backend for presigned URL generation
    const backendUrl = `${process.env.API_BASE_URL || 'http://localhost:8000'}/download-s3-url?s3_path=${encodeURIComponent(s3Path)}&expires_in=${expiresIn}`;
    
    const response = await fetch(backendUrl);
    
    if (!response.ok) {
      console.error(`Backend presigned URL failed: ${response.status} ${response.statusText}`);
      return NextResponse.json(
        { error: `Presigned URL generation failed: ${response.statusText}` },
        { status: response.status }
      );
    }
    
    // Return the presigned URL data to frontend
    const data = await response.json();
    
    return NextResponse.json(data, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
      },
    });
    
  } catch (error) {
    console.error('Error proxying S3 presigned URL:', error);
    return NextResponse.json(
      { error: `Presigned URL proxy failed: ${error instanceof Error ? error.message : 'Unknown error'}` },
      { status: 500 }
    );
  }
}
'use client';

import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen">
      <div className="bg-white shadow-md rounded-lg p-6 max-w-2xl mx-auto mt-10">
        <h1 className="text-2xl font-bold mb-6">Document OCR Portal</h1>
        <p className="mb-4">
          Upload and process documents using Google Gemini AI for accurate text extraction and data processing.
        </p>

        <div className="flex flex-col gap-4 mt-8">
          <Link
            href="/upload"
            className="bg-blue-600 text-white py-3 px-6 rounded-lg text-center font-medium hover:bg-blue-700 transition-colors"
          >
            Upload New Document
          </Link>

          <Link
            href="/jobs"
            className="bg-slate-200 text-slate-800 py-3 px-6 rounded-lg text-center font-medium hover:bg-slate-300 transition-colors"
          >
            View Processing Jobs
          </Link>
        </div>
      </div>
    </div>
  );
}
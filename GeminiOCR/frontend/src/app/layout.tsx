import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ['latin'] })


export const metadata: Metadata = {
  title: 'Document OCR Portal',
  description: 'OCR processing using Google Gemini AI',
}


export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        {/* Preconnect for Google Fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        
        {/* Preload critical fonts */}
        <link 
          rel="preload" 
          href="https://fonts.gstatic.com/s/lato/v24/S6uyw4BMUTPHjx4wXiWtFCc.woff2" 
          as="font" 
          type="font/woff2" 
          crossOrigin="anonymous" 
        />
      </head>
      <body className={inter.className}>
        <nav className="bg-slate-800 text-white p-4">
          <div className="container mx-auto flex justify-between items-center">
            <h1 className="text-xl font-bold">Document OCR Portal</h1>
          </div>
        </nav>
        <main className="container mx-auto p-4">
          {children}
        </main>
      </body>
    </html>
  )
}
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from '@/contexts/auth-context';
import UserProfileMenu from '@/components/UserProfileMenu';

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
      <body className={inter.className}>
        <AuthProvider>
          <div className="min-h-screen flex flex-col">
            {/* Header with user profile */}
            <header className="bg-white border-b border-gray-200 py-4 px-6">
              <div className="container mx-auto flex justify-between items-center">
                <div>
                  <a href="/" className="text-xl font-bold text-blue-600">
                    Document OCR Portal
                  </a>
                </div>
                <UserProfileMenu />
              </div>
            </header>
            
            {/* Main content */}
            <main className="flex-1">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  )
}
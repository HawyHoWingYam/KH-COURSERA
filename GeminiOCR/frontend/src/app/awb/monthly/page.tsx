'use client'

import { useState, ChangeEvent, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface FormData {
  company_id: string
  month: string
  summary_pdf: File | null
  employees_csv: File | null
}

export default function AWBMonthlyPage() {
  const router = useRouter()
  const [formData, setFormData] = useState<FormData>({
    company_id: '',
    month: '',
    summary_pdf: null,
    employees_csv: null,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, files } = e.target
    if (files && files.length > 0) {
      setFormData((prev) => ({
        ...prev,
        [name]: files[0],
      }))
    }
  }

  const validateForm = (): string | null => {
    if (!formData.company_id) {
      return 'Company is required'
    }
    if (!formData.month || !formData.month.match(/^\d{4}-\d{2}$/)) {
      return 'Month must be in YYYY-MM format'
    }
    if (!formData.summary_pdf) {
      return 'Summary PDF is required'
    }
    if (formData.summary_pdf.type !== 'application/pdf') {
      return 'Summary file must be a PDF'
    }
    if (!formData.employees_csv) {
      return 'Employee CSV is required'
    }
    if (formData.employees_csv.type !== 'text/csv' && !formData.employees_csv.name.endsWith('.csv')) {
      return 'Employee file must be a CSV'
    }
    return null
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }

    setIsLoading(true)

    try {
      const formDataObj = new FormData()
      formDataObj.append('company_id', formData.company_id)
      formDataObj.append('month', formData.month)
      if (formData.summary_pdf) {
        formDataObj.append('summary_pdf', formData.summary_pdf)
      }
      if (formData.employees_csv) {
        formDataObj.append('employees_csv', formData.employees_csv)
      }

      const response = await fetch('/api/awb/process-monthly', {
        method: 'POST',
        body: formDataObj,
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to start AWB processing')
      }

      setSuccess(`Processing started! Redirecting to batch job ${result.batch_id}...`)

      // Redirect to batch job details page
      setTimeout(() => {
        router.push(`/batch-jobs/${result.batch_id}`)
      }, 2000)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process AWB files'
      setError(errorMessage)
      console.error('Error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader className="space-y-2">
            <CardTitle className="text-3xl">AWB Monthly Processing</CardTitle>
            <CardDescription>
              Process monthly Air Waybill files with OCR and automated matching
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Error Alert */}
              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  <strong>❌ Error:</strong> {error}
                </div>
              )}

              {/* Success Alert */}
              {success && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
                  <strong>✅ Success:</strong> {success}
                </div>
              )}

              {/* Company Selection */}
              <div className="space-y-2">
                <label htmlFor="company_id" className="block text-sm font-medium text-slate-700">
                  Company <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  id="company_id"
                  name="company_id"
                  value={formData.company_id}
                  onChange={handleInputChange}
                  placeholder="Enter company ID"
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading}
                />
              </div>

              {/* Month Selection */}
              <div className="space-y-2">
                <label htmlFor="month" className="block text-sm font-medium text-slate-700">
                  Month <span className="text-red-500">*</span>
                </label>
                <input
                  type="month"
                  id="month"
                  name="month"
                  value={formData.month}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading}
                />
                <p className="text-xs text-slate-500">Format: YYYY-MM (e.g., 2025-10)</p>
              </div>

              {/* Summary PDF Upload */}
              <div className="space-y-2">
                <label htmlFor="summary_pdf" className="block text-sm font-medium text-slate-700">
                  Summary PDF <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="file"
                    id="summary_pdf"
                    name="summary_pdf"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isLoading}
                  />
                  {formData.summary_pdf && (
                    <p className="text-sm text-green-600 mt-1">✓ {formData.summary_pdf.name}</p>
                  )}
                </div>
                <p className="text-xs text-slate-500">Monthly summary bill PDF file</p>
              </div>

              {/* Employees CSV Upload */}
              <div className="space-y-2">
                <label htmlFor="employees_csv" className="block text-sm font-medium text-slate-700">
                  Employee Mapping CSV <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="file"
                    id="employees_csv"
                    name="employees_csv"
                    accept=".csv"
                    onChange={handleFileChange}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isLoading}
                  />
                  {formData.employees_csv && (
                    <p className="text-sm text-green-600 mt-1">✓ {formData.employees_csv.name}</p>
                  )}
                </div>
                <p className="text-xs text-slate-500">CSV with columns: name, department</p>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? '⏳ Processing...' : '🚀 Start Processing'}
              </button>

              {/* Info Box */}
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-slate-700">
                <strong>ℹ️ Processing will:</strong>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Extract order data from AWB PDFs using OCR</li>
                  <li>Match costs from the summary bill</li>
                  <li>Associate employees with departments</li>
                  <li>Generate Excel/CSV reports</li>
                </ul>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Help Section */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg">📖 Help & Support</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600 space-y-3">
            <div>
              <strong>CSV Format:</strong>
              <pre className="bg-slate-100 p-3 rounded mt-1 text-xs overflow-auto">
                {`name,department
John Doe,Sales
Jane Smith,Marketing
Bob Johnson,Finance`}
              </pre>
            </div>
            <p>
              After submission, you'll be redirected to the batch job details page where you can track progress and download results (JSON, Excel, CSV).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

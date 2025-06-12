'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '@/lib/api';
import AdminLayout from '@/components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';

// Define types
type UsageData = {
  date?: string;
  month?: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
};

export default function ApiUsagePage() {
  const [activeTab, setActiveTab] = useState('daily');
  const [dailyUsage, setDailyUsage] = useState<UsageData[]>([]);
  const [monthlyUsage, setMonthlyUsage] = useState<UsageData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Format number with commas
  const formatNumber = (num: number) => {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  };

  // Calculate totals
  const calculateTotals = (data: UsageData[]) => {
    return data.reduce(
      (acc, curr) => {
        return {
          inputTokens: acc.inputTokens + (curr.input_tokens || 0),
          outputTokens: acc.outputTokens + (curr.output_tokens || 0),
          totalTokens: acc.totalTokens + (curr.total_tokens || 0),
          requestCount: acc.requestCount + (curr.request_count || 0),
        };
      },
      { inputTokens: 0, outputTokens: 0, totalTokens: 0, requestCount: 0 }
    );
  };

  useEffect(() => {
    const fetchDailyUsage = async () => {
      try {
        const data = await fetchApi<UsageData[]>('/admin/usage/daily');
        setDailyUsage(data);
      } catch (err) {
        console.error('Error fetching daily usage:', err);
        setError('Failed to load daily usage data');
      }
    };

    const fetchMonthlyUsage = async () => {
      try {
        const data = await fetchApi<UsageData[]>('/admin/usage/monthly');
        setMonthlyUsage(data);
      } catch (err) {
        console.error('Error fetching monthly usage:', err);
        setError('Failed to load monthly usage data');
      }
    };

    const loadData = async () => {
      setIsLoading(true);
      setError('');
      await Promise.all([fetchDailyUsage(), fetchMonthlyUsage()]);
      setIsLoading(false);
    };

    loadData();
  }, []);

  // Get totals for current view
  const totals = activeTab === 'daily' 
    ? calculateTotals(dailyUsage)
    : calculateTotals(monthlyUsage);

  return (
    <AdminLayout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Gemini API Usage Analytics</h1>
        
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : error ? (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-500">Total Requests</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{formatNumber(totals.requestCount)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-500">Input Tokens</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{formatNumber(totals.inputTokens)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-500">Output Tokens</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{formatNumber(totals.outputTokens)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-500">Total Tokens</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{formatNumber(totals.totalTokens)}</p>
                </CardContent>
              </Card>
            </div>

            {/* Tabs for switching between daily and monthly views */}
            <Tabs defaultValue="daily" value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger value="daily">Daily Usage (30 Days)</TabsTrigger>
                <TabsTrigger value="monthly">Monthly Usage (12 Months)</TabsTrigger>
              </TabsList>
              
              <TabsContent value="daily">
                <Card>
                  <CardHeader>
                    <CardTitle>Daily API Token Usage</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-96">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dailyUsage}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="input_tokens" stroke="#8884d8" name="Input Tokens" />
                          <Line type="monotone" dataKey="output_tokens" stroke="#82ca9d" name="Output Tokens" />
                          <Line type="monotone" dataKey="total_tokens" stroke="#ff7300" name="Total Tokens" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              
              <TabsContent value="monthly">
                <Card>
                  <CardHeader>
                    <CardTitle>Monthly API Token Usage</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-96">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={monthlyUsage}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="month" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="input_tokens" fill="#8884d8" name="Input Tokens" />
                          <Bar dataKey="output_tokens" fill="#82ca9d" name="Output Tokens" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </AdminLayout>
  );
} 
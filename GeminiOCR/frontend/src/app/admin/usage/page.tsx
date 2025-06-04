'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '@/lib/api';
import AdminLayout from '@/components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { DatePicker } from '@/components/ui/date-picker';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { format } from 'date-fns';

// Define types
type UsageData = {
  date?: string;
  month?: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
  model?: string;
};

type ModelOption = {
  value: string;
  label: string;
};

export default function ApiUsagePage() {
  const [activeTab, setActiveTab] = useState('daily');
  const [dailyUsage, setDailyUsage] = useState<UsageData[]>([]);
  const [monthlyUsage, setMonthlyUsage] = useState<UsageData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  // New state for filters
  const [startDate, setStartDate] = useState<Date | undefined>(
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) // 30 days ago
  );
  const [endDate, setEndDate] = useState<Date | undefined>(new Date());
  const [selectedModel, setSelectedModel] = useState<string>('all');
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([
    { value: 'all', label: 'All Models' }
  ]);
  
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

  // Fetch available models
  const fetchModels = async () => {
    try {
      const models = await fetchApi<string[]>('/admin/models');
      const options = [
        { value: 'all', label: 'All Models' },
        ...models.map(model => ({ value: model, label: model }))
      ];
      setModelOptions(options);
    } catch (err) {
      console.error('Error fetching models:', err);
    }
  };

  // Fetch usage data with filters
  const fetchUsageData = async () => {
    setIsLoading(true);
    setError('');

    try {
      // Format dates for API
      const formattedStartDate = startDate ? format(startDate, 'yyyy-MM-dd') : '';
      const formattedEndDate = endDate ? format(endDate, 'yyyy-MM-dd') : '';
      
      // Build query params
      const params = new URLSearchParams();
      if (formattedStartDate) params.append('start_date', formattedStartDate);
      if (formattedEndDate) params.append('end_date', formattedEndDate);
      if (selectedModel !== 'all') params.append('model', selectedModel);

      // Fetch daily data
      const daily = await fetchApi<UsageData[]>(`/admin/usage/daily?${params.toString()}`);
      setDailyUsage(daily);

      // Fetch monthly data
      const monthly = await fetchApi<UsageData[]>(`/admin/usage/monthly?${params.toString()}`);
      setMonthlyUsage(monthly);
    } catch (err) {
      console.error('Error fetching usage data:', err);
      setError('Failed to load usage data');
    } finally {
      setIsLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchModels();
    fetchUsageData();
  }, []);

  // Get totals for current view
  const totals = activeTab === 'daily' 
    ? calculateTotals(dailyUsage)
    : calculateTotals(monthlyUsage);

  return (
    <AdminLayout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Gemini API Usage Analytics</h1>
        
        {/* Filter Controls */}
        <div className="mb-6 p-4 bg-white rounded-lg shadow grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <DatePicker
              date={startDate}
              setDate={setStartDate}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <DatePicker
              date={endDate}
              setDate={setEndDate}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
            <Select value={selectedModel} onValueChange={setSelectedModel}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button onClick={fetchUsageData} className="w-full">
              Apply Filters
            </Button>
          </div>
        </div>
        
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
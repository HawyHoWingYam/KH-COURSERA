'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '@/lib/api';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertTriangle, Info } from 'lucide-react';

type Setting = {
  key: string;
  value: string;
  description: string;
  updated_at: string | null;
};

type Model = {
  id: string;
  name: string;
};

export default function ConfigPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('api');
  const [editValues, setEditValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await fetchApi<Setting[]>('/admin/settings');
        setSettings(data);
      } catch (error) {
        console.error('Error fetching settings:', error);
        toast.error('Failed to load settings');
      }
    };

    const fetchModels = async () => {
      try {
        const data = await fetchApi<Model[]>('/admin/settings/models');
        setModels(data);
      } catch (error) {
        console.error('Error fetching models:', error);
      }
    };

    const loadData = async () => {
      setIsLoading(true);
      await Promise.all([fetchSettings(), fetchModels()]);
      setIsLoading(false);
    };

    loadData();
  }, []);

  const updateSetting = async (key: string, value: string) => {
    setIsSaving(true);
    try {
      await fetchApi(`/admin/settings/${key}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ value }),
      });

      // Update local state
      setSettings(settings.map(s => 
        s.key === key ? { ...s, value } : s
      ));
      
      toast.success(`${key} updated successfully`);
    } catch (error) {
      console.error(`Error updating ${key}:`, error);
      toast.error(`Failed to update ${key}`);
    } finally {
      setIsSaving(false);
    }
  };

  // Helper to get a setting value by key
  const getSetting = (key: string): string => {
    if (key in editValues) {
      return editValues[key];
    }
    const setting = settings.find(s => s.key === key);
    return setting ? setting.value : '';
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">System Configuration</h1>
      
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="api">API Settings</TabsTrigger>
          <TabsTrigger value="model">Model Parameters</TabsTrigger>
        </TabsList>
        
        <TabsContent value="api">
          <Card>
            <CardHeader>
              <CardTitle>API Configuration</CardTitle>
              <CardDescription>
                Configure your Google Gemini API settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* API Key */}
              <div className="space-y-2">
                <Label htmlFor="gemini_api_key">
                  Gemini API Key
                  <span className="text-red-500 ml-1">*</span>
                </Label>
                <div className="flex space-x-2">
                  <Input
                    id="gemini_api_key"
                    type="password"
                    value={getSetting('gemini_api_key')}
                    onChange={(e) => {
                      setEditValues({...editValues, gemini_api_key: e.target.value});
                    }}
                    placeholder="Enter your Gemini API key"
                  />
                  <Button 
                    onClick={() => {
                      updateSetting('gemini_api_key', editValues.gemini_api_key || getSetting('gemini_api_key'));
                    }}
                    disabled={isSaving}
                  >
                    Save
                  </Button>
                </div>
                <p className="text-sm text-gray-500">
                  Your API key is stored securely and used for all Gemini API calls.
                </p>
              </div>
              
              {/* Model Selection */}
              <div className="space-y-2">
                <Label htmlFor="default_model">Default Model</Label>
                <div className="flex space-x-2">
                  <Select 
                    value={getSetting('default_model')} 
                    onValueChange={(value) => updateSetting('default_model', value)}
                  >
                    <SelectTrigger id="default_model" className="w-full">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <p className="text-sm text-gray-500">
                  The default model to use for all API calls.
                </p>
              </div>
              
              {/* Max Context Length */}
              <div className="space-y-2">
                <Label htmlFor="max_context_length">
                  Max Context Length
                </Label>
                <div className="flex space-x-2">
                  <Input
                    id="max_context_length"
                    type="number"
                    value={getSetting('max_context_length')}
                    onChange={(e) => {
                      // Store in editValues for immediate UI update
                      setEditValues({...editValues, max_context_length: e.target.value});
                      // Also update the setting in the backend immediately
                      updateSetting('max_context_length', e.target.value);
                    }}
                  />
                </div>
                <p className="text-sm text-gray-500">
                  Maximum number of tokens to use for context in API calls. Higher values may increase accuracy but also cost.
                </p>
              </div>
            </CardContent>
            <CardFooter className="bg-amber-50 border-t">
              <div className="flex items-center text-amber-800 text-sm">
                <AlertTriangle className="h-4 w-4 mr-2" />
                Changes to API settings will affect all future document processing jobs.
              </div>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="model">
          <Card>
            <CardHeader>
              <CardTitle>Model Parameters</CardTitle>
              <CardDescription>
                Fine-tune the generation parameters for the Gemini API
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Temperature */}
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label htmlFor="temperature">Temperature: {getSetting('temperature')}</Label>
                </div>
                <div className="flex items-center space-x-4">
                  <span className="text-sm">0.0</span>
                  <Slider
                    id="temperature"
                    min={0}
                    max={1}
                    step={0.1}
                    value={[parseFloat(getSetting('temperature') || '0.3')]}
                    onValueChange={(values) => {
                      updateSetting('temperature', values[0].toString());
                    }}
                    className="flex-1"
                  />
                  <span className="text-sm">1.0</span>
                </div>
                <p className="text-sm text-gray-500">
                  Controls randomness. Lower values are more deterministic, higher values more creative.
                </p>
              </div>
              
              {/* Top-p */}
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label htmlFor="top_p">Top-p: {getSetting('top_p')}</Label>
                </div>
                <div className="flex items-center space-x-4">
                  <span className="text-sm">0.0</span>
                  <Slider
                    id="top_p"
                    min={0}
                    max={1}
                    step={0.05}
                    value={[parseFloat(getSetting('top_p') || '0.95')]}
                    onValueChange={(values) => {
                      updateSetting('top_p', values[0].toString());
                    }}
                    className="flex-1"
                  />
                  <span className="text-sm">1.0</span>
                </div>
                <p className="text-sm text-gray-500">
                  Controls diversity via nucleus sampling. 1.0 considers all tokens.
                </p>
              </div>
              
              {/* Top-k */}
              <div className="space-y-2">
                <Label htmlFor="top_k">Top-k</Label>
                <div className="flex space-x-2">
                  <Input
                    id="top_k"
                    type="number"
                    value={getSetting('top_k')}
                    onChange={(e) => {
                      setSettings(settings.map(s => 
                        s.key === 'top_k' ? { ...s, value: e.target.value } : s
                      ));
                    }}
                  />
                  <Button 
                    onClick={() => updateSetting('top_k', getSetting('top_k'))}
                    disabled={isSaving}
                  >
                    Save
                  </Button>
                </div>
                <p className="text-sm text-gray-500">
                  Controls diversity by limiting to top k tokens. Higher values increase diversity.
                </p>
              </div>
            </CardContent>
            <CardFooter className="bg-blue-50 border-t">
              <div className="flex items-center text-blue-800 text-sm">
                <Info className="h-4 w-4 mr-2" />
                These settings control the behavior of the Gemini model. Adjusting them can impact the accuracy and consistency of document processing.
              </div>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 
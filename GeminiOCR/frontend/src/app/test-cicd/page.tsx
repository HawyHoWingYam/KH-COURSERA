'use client';

import React from 'react';

interface TestInfo {
  feature: string;
  timestamp: string;
  repositories: {
    sandbox: string;
    production: string;
  };
  testStages: {
    [key: string]: string;
  };
  expectedTags: {
    [key: string]: string[];
  };
}

export default function CICDTestPage() {
  const testInfo: TestInfo = {
    feature: 'cicd-dual-repo-test',
    timestamp: new Date().toISOString(),
    repositories: {
      sandbox: 'karasho62/hya-ocr-sandbox',
      production: 'karasho62/hya-ocr-production'
    },
    testStages: {
      stage1: 'Feature Development - Build & Test Only',
      stage2: 'UAT Staging - Deploy to Sandbox',
      stage3: 'Production Release - Deploy to Production',
      stage4: 'Version Release - Create GitHub Release'
    },
    expectedTags: {
      develop: ['backend-develop', 'frontend-develop'],
      main: ['backend-latest', 'frontend-latest'],
      version: ['backend-v1.3.1', 'frontend-v1.3.1']
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          🧪 CI/CD 双仓库架构测试
        </h1>
        
        <div className="bg-white shadow-lg rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            测试信息
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="font-medium text-gray-600">功能名称:</span>
              <span className="ml-2 text-gray-900">{testInfo.feature}</span>
            </div>
            <div>
              <span className="font-medium text-gray-600">测试时间:</span>
              <span className="ml-2 text-gray-900">
                {new Date(testInfo.timestamp).toLocaleString('zh-CN')}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white shadow-lg rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            🐳 仓库配置
          </h2>
          <div className="space-y-3">
            <div className="flex items-center">
              <span className="w-24 font-medium text-gray-600">Sandbox:</span>
              <code className="bg-gray-100 px-3 py-1 rounded text-sm">
                {testInfo.repositories.sandbox}
              </code>
              <span className="ml-2 text-sm text-green-600">
                开发/测试环境
              </span>
            </div>
            <div className="flex items-center">
              <span className="w-24 font-medium text-gray-600">Production:</span>
              <code className="bg-gray-100 px-3 py-1 rounded text-sm">
                {testInfo.repositories.production}
              </code>
              <span className="ml-2 text-sm text-blue-600">
                生产环境
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white shadow-lg rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            🎯 测试阶段
          </h2>
          <div className="space-y-4">
            {Object.entries(testInfo.testStages).map(([stage, description], index) => (
              <div key={stage} className="flex items-start">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div className="ml-3">
                  <p className="text-gray-900 font-medium">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white shadow-lg rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            🏷️ 期望的镜像标签
          </h2>
          <div className="space-y-4">
            {Object.entries(testInfo.expectedTags).map(([branch, tags]) => (
              <div key={branch}>
                <h3 className="font-medium text-gray-700 mb-2 capitalize">
                  {branch} 分支:
                </h3>
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="bg-gray-100 text-gray-800 px-3 py-1 rounded-full text-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <span className="text-green-600 text-xl">✅</span>
            </div>
            <div className="ml-3">
              <p className="text-sm text-green-800">
                CI/CD 双仓库架构配置验证通过，准备开始完整测试流程！
              </p>
              <p className="text-xs text-green-600 mt-1">
                触发完整流水线：构建 → 测试 → 扫描 → 集成测试 → 发布
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
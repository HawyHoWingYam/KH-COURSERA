#!/usr/bin/env python3
"""
Test Runner for Prompt/Schema S3 Migration
测试运行器 - 用于运行prompt和schema S3迁移的测试

使用方法:
    python run_tests.py                    # 运行所有测试
    python run_tests.py --unit             # 只运行单元测试
    python run_tests.py --integration      # 只运行集成测试
    python run_tests.py --coverage         # 运行测试并生成覆盖率报告
    python run_tests.py --parallel         # 并行运行测试
    python run_tests.py --watch            # 监听文件变化自动运行测试
"""

import argparse
import subprocess
import sys
from pathlib import Path
import os

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(cmd: list, description: str = None):
    """运行命令并处理结果"""
    if description:
        print(f"\n🔄 {description}")
        print("=" * 50)
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print(f"✅ {description or 'Command'} completed successfully")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or 'Command'} failed with exit code {e.returncode}")
        return e.returncode
    except KeyboardInterrupt:
        print(f"\n⚠️ {description or 'Command'} interrupted by user")
        return 1


def install_test_dependencies():
    """安装测试依赖"""
    test_requirements = project_root / "tests" / "requirements-test.txt"
    
    if test_requirements.exists():
        return run_command([
            sys.executable, "-m", "pip", "install", "-r", str(test_requirements)
        ], "Installing test dependencies")
    else:
        print("⚠️ Test requirements file not found, skipping dependency installation")
        return 0


def run_unit_tests():
    """运行单元测试"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_prompt_schema_s3_migration.py",
        "-v",
        "-m", "not integration",
        "--tb=short"
    ]
    return run_command(cmd, "Running unit tests")


def run_integration_tests():
    """运行集成测试"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_prompt_schema_s3_migration.py",
        "-v",
        "-m", "integration",
        "--tb=short"
    ]
    return run_command(cmd, "Running integration tests")


def run_all_tests():
    """运行所有测试"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_prompt_schema_s3_migration.py",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Running all tests")


def run_tests_with_coverage():
    """运行测试并生成覆盖率报告"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_prompt_schema_s3_migration.py",
        "-v",
        "--cov=utils.s3_storage",
        "--cov=utils.prompt_schema_manager", 
        "--cov-report=term-missing",
        "--cov-report=html:tests/htmlcov",
        "--tb=short"
    ]
    
    result = run_command(cmd, "Running tests with coverage")
    
    if result == 0:
        coverage_report = project_root / "tests" / "htmlcov" / "index.html"
        if coverage_report.exists():
            print(f"\n📊 Coverage report generated: {coverage_report}")
            print("   Open this file in a browser to view detailed coverage")
    
    return result


def run_tests_parallel():
    """并行运行测试"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_prompt_schema_s3_migration.py",
        "-v",
        "-n", "auto",  # 自动检测CPU核心数
        "--tb=short"
    ]
    return run_command(cmd, "Running tests in parallel")


def watch_tests():
    """监听文件变化自动运行测试"""
    try:
        import pytest_watch
    except ImportError:
        print("❌ pytest-watch not installed. Installing...")
        install_result = run_command([
            sys.executable, "-m", "pip", "install", "pytest-watch"
        ])
        if install_result != 0:
            return install_result
    
    cmd = [
        "ptw",  # pytest-watch 命令
        "tests/test_prompt_schema_s3_migration.py",
        "utils/",
        "--",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Watching files for test execution")


def run_specific_test_class(class_name: str):
    """运行特定的测试类"""
    cmd = [
        sys.executable, "-m", "pytest", 
        f"tests/test_prompt_schema_s3_migration.py::{class_name}",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, f"Running test class: {class_name}")


def run_specific_test_method(method_name: str):
    """运行特定的测试方法"""
    cmd = [
        sys.executable, "-m", "pytest", 
        f"tests/test_prompt_schema_s3_migration.py",
        "-k", method_name,
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, f"Running test method: {method_name}")


def validate_environment():
    """验证测试环境"""
    print("🔍 Validating test environment...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    # 检查项目结构
    required_paths = [
        project_root / "GeminiOCR" / "backend" / "utils" / "s3_storage.py",
        project_root / "GeminiOCR" / "backend" / "utils" / "prompt_schema_manager.py",
        project_root / "tests" / "test_prompt_schema_s3_migration.py"
    ]
    
    for path in required_paths:
        if not path.exists():
            print(f"❌ Required file not found: {path}")
            return False
    
    print("✅ Environment validation passed")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for Prompt/Schema S3 Migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--watch", action="store_true", help="Watch files and auto-run tests")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    parser.add_argument("--class", dest="test_class", help="Run specific test class")
    parser.add_argument("--method", dest="test_method", help="Run specific test method")
    parser.add_argument("--validate", action="store_true", help="Validate test environment only")
    
    args = parser.parse_args()
    
    # 验证环境
    if not validate_environment():
        return 1
    
    if args.validate:
        return 0
    
    # 安装依赖
    if args.install_deps:
        result = install_test_dependencies()
        if result != 0:
            return result
    
    # 运行特定测试
    if args.test_class:
        return run_specific_test_class(args.test_class)
    
    if args.test_method:
        return run_specific_test_method(args.test_method)
    
    # 根据参数运行测试
    if args.unit:
        return run_unit_tests()
    elif args.integration:
        return run_integration_tests()
    elif args.coverage:
        return run_tests_with_coverage()
    elif args.parallel:
        return run_tests_parallel()
    elif args.watch:
        return watch_tests()
    else:
        # 默认运行所有测试
        return run_all_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
#!/usr/bin/env python3
"""
跨境卖家 MCP 服务器 - 中文启动助手
Cross-Border Seller MCP Server - Chinese Launcher
"""

import os
import subprocess
import sys
from pathlib import Path


def print_banner():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          跨境卖家 MCP 服务器 - 启动助手                       ║")
    print("║         Cross-Border Seller MCP Server - Launcher             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

def check_env_file():
    """检查 .env 文件是否存在"""
    env_file = Path(".env")
    env_cn_example = Path(".env.cn.example")
    env_example = Path(".env.example")

    if not env_file.exists():
        print("⚠️  警告: .env 文件不存在!")
        print()

        if env_cn_example.exists():
            print("📝 找到中文配置模板 (.env.cn.example)")
            choice = input("是否复制模板为 .env? (y/n, 默认 y): ").strip().lower()

            if choice in ("y", "yes", ""):
                import shutil
                shutil.copy(env_cn_example, ".env")
                print("✅ 已创建 .env 文件")
                print()
                print("📋 下一步: 请编辑 .env 文件，填入您的 API 密钥")
                print()
                return False
        elif env_example.exists():
            print("📝 找到英文配置模板 (.env.example)")
            choice = input("是否复制模板为 .env? (y/n, 默认 y): ").strip().lower()

            if choice in ("y", "yes", ""):
                import shutil
                shutil.copy(env_example, ".env")
                print("✅ 已创建 .env 文件")
                print()
                print("📋 下一步: 请编辑 .env 文件，填入您的 API 密钥")
                print()
                return False
    else:
        print("✅ .env 文件已存在")
        return True

def check_dependencies():
    """检查依赖是否已安装"""
    print()
    print("📦 检查依赖...")

    try:
        import dotenv
        import httpx
        import mcp
        import pydantic
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"⚠️  缺少依赖: {e}")
        print()
        choice = input("是否自动安装依赖? (y/n, 默认 y): ").strip().lower()

        if choice in ("y", "yes", ""):
            print()
            print("正在安装依赖...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print()
            print("✅ 依赖安装完成!")
            return True
        else:
            print("请先运行: pip install -r requirements.txt")
            return False

def run_tests():
    """运行测试"""
    print()
    choice = input("是否运行测试确认环境正常? (y/n, 默认 n): ").strip().lower()

    if choice in ("y", "yes"):
        print()
        print("🧪 运行测试...")
        print()
        result = subprocess.run([sys.executable, "test_server.py"])
        return result.returncode == 0
    return True

def show_license_info():
    """显示许可证信息"""
    from dotenv import load_dotenv
    load_dotenv()
    license_key = os.getenv("LICENSE_KEY", "")

    print()
    print("📜 许可证信息:")
    if license_key == "FREE_DEMO_12345":
        print("   当前: 免费版 (Free)")
        print("   可用: 基础库存、订单管理")
        print("   升级: ¥99/月 获取价格和评论功能")
    elif license_key == "PRO_DEMO_99999":
        print("   当前: 专业版 (Pro)")
        print("   可用: 价格同步、竞品查询、评论查看")
        print("   升级: ¥299/月 获取完整评论警报功能")
    elif license_key == "BUSINESS_DEMO_88888":
        print("   当前: 商业版 (Business)")
        print("   可用: 所有功能、优先支持")
    elif not license_key:
        print("   当前: 免费版 (Free, 未设置)")
    else:
        print("   当前: 自定义密钥")
    print()
    print("   价格方案查看: PRICING_GUIDE_CN.md")

def show_menu():
    """显示菜单"""
    print()
    print("请选择:")
    print("1. 启动服务器 (Start Server)")
    print("2. 运行测试 (Run Tests)")
    print("3. 显示许可证信息 (Show License Info)")
    print("4. 显示帮助 (Show Help)")
    print("5. 退出 (Exit)")
    print()

def main():
    print_banner()

    os.chdir(Path(__file__).parent)

    # 检查环境
    env_ok = check_env_file()
    dep_ok = check_dependencies()

    if not (env_ok and dep_ok):
        print()
        print("请先完成配置后重新运行此脚本")
        return 1

    while True:
        show_menu()
        choice = input("请输入选项 (1-5): ").strip()

        if choice == "1":
            print()
            print("🚀 启动 MCP 服务器...")
            print("按 Ctrl+C 停止")
            print("="*60)
            try:
                subprocess.run([sys.executable, "server.py"])
            except KeyboardInterrupt:
                print()
                print("👋 服务器已停止")
        elif choice == "2":
            run_tests()
        elif choice == "3":
            show_license_info()
        elif choice == "4":
            print()
            print("📚 帮助信息:")
            print("- 中文快速入门: 请查看 README_CN.md")
            print("- 价格方案: 请查看 PRICING_GUIDE_CN.md")
            print("- 完整文档: 请查看 README.md")
            print("- 配置文件: .env")
        elif choice == "5":
            print()
            print("👋 再见!")
            return 0
        else:
            print("❌ 无效选项，请重新选择")

if __name__ == "__main__":
    sys.exit(main())

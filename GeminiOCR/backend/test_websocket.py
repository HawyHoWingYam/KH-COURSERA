#!/usr/bin/env python3
"""
WebSocket 測試工具
用於測試 GeminiOCR 後端的 WebSocket 連接功能
"""

import asyncio
import websockets
import json
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection(host="localhost", port=8000, job_id="test_123"):
    """測試 WebSocket 連接"""
    uri = f"ws://{host}:{port}/ws/{job_id}"
    
    try:
        logger.info(f"🔌 嘗試連接到 WebSocket: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket 連接成功建立")
            
            # 監聽初始消息
            try:
                initial_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📨 收到初始消息: {initial_message}")
                
                parsed_message = json.loads(initial_message)
                if parsed_message.get("type") == "connection_established":
                    logger.info("✅ 連接確認消息收到")
                else:
                    logger.info(f"📝 收到消息類型: {parsed_message.get('type', 'unknown')}")
                    
            except asyncio.TimeoutError:
                logger.warning("⚠️  等待初始消息超時")
            
            # 發送測試消息
            test_messages = ["ping", "test message", "hello server"]
            
            for message in test_messages:
                logger.info(f"📤 發送測試消息: {message}")
                await websocket.send(message)
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    logger.info(f"📬 收到響應: {response}")
                    
                    try:
                        parsed_response = json.loads(response)
                        if parsed_response.get("type") == "pong":
                            logger.info("✅ Ping-Pong 測試成功")
                    except json.JSONDecodeError:
                        logger.info("📝 收到非 JSON 響應")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️  等待響應超時: {message}")
                
                await asyncio.sleep(1)
            
            # 保持連接一段時間以測試穩定性
            logger.info("⏳ 保持連接 10 秒以測試穩定性...")
            try:
                await asyncio.wait_for(websocket.recv(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.info("✅ 連接在 10 秒內保持穩定")
            
            logger.info("🎉 WebSocket 測試完成")
            
    except websockets.exceptions.ConnectionRefused as e:
        logger.error(f"❌ 連接被拒絕: {e}")
        logger.error("   請確保後端服務器正在運行")
        return False
        
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ 無效狀態碼: {e}")
        logger.error("   WebSocket 握手失敗")
        return False
        
    except Exception as e:
        logger.error(f"❌ WebSocket 測試失敗: {e}")
        return False
    
    return True

async def test_multiple_connections(host="localhost", port=8000, num_connections=3):
    """測試多個並發 WebSocket 連接"""
    logger.info(f"🔄 測試 {num_connections} 個並發連接...")
    
    async def single_connection_test(job_id):
        return await test_websocket_connection(host, port, f"concurrent_{job_id}")
    
    tasks = [single_connection_test(i) for i in range(num_connections)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = sum(1 for r in results if r is True)
    logger.info(f"📊 並發測試結果: {successful}/{num_connections} 連接成功")
    
    return successful == num_connections

def main():
    """主測試函數"""
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    
    print("=" * 60)
    print("🧪 GeminiOCR WebSocket 連接測試")
    print("=" * 60)
    print(f"🎯 測試目標: ws://{host}:{port}")
    print(f"🕒 測試時間: {datetime.now().isoformat()}")
    print("-" * 60)
    
    async def run_tests():
        # 基本連接測試
        print("\n1️⃣  基本 WebSocket 連接測試")
        basic_success = await test_websocket_connection(host, port)
        
        if basic_success:
            print("\n2️⃣  並發連接測試")
            concurrent_success = await test_multiple_connections(host, port)
            
            if concurrent_success:
                print("\n✅ 所有 WebSocket 測試通過!")
                return True
            else:
                print("\n❌ 並發連接測試失敗")
                return False
        else:
            print("\n❌ 基本連接測試失敗")
            return False
    
    try:
        success = asyncio.run(run_tests())
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 WebSocket 測試全部通過")
            sys.exit(0)
        else:
            print("❌ WebSocket 測試失敗")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  測試被用戶中斷")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n💥 測試過程中發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
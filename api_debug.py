#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 接口调试脚本
通过 adb logcat 抓包获取接口信息后，用 Python requests 直接调用
"""

import requests
import json
from datetime import datetime

# ============== 配置信息（从 logcat 抓包获取） ==============
BASE_URL = "https://test.supervisions.cn"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjanNqIiwiaXNzIjoiY2pzaiIsImV4cCI6MTgxNzQ2NzY1MywiYXV0aFR5cGUiOjQsInVzZXJJZCI6IjU3ZDcwM2RjLTY1OWEtNDQ3NC04OThlLWI3NWVmYTFmMmUwYSJ9.evzNsb2k7yv33yNU8BDsit7FCN-eNCQk5iD5YL12h2c",
    "refresh_token": "ecbe9fe8a12e045be53db01e88f81da2"
}

USER_ID = "57d703dc-659a-4474-898e-b75efa1f2e0a"

# ============== 接口定义 ==============

API_ENDPOINTS = {
    "1_埋点事件上报": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/event/track",
        "data": {
            "modelType": 1,
            "eventType": 1,
            "attrName": "launch_source",
            "attrValue": "cold",
            "clientType": 1,
            "userId": USER_ID
        }
    },

    "2_获取用户盒子状态": {
        "method": "POST",
        "url": f"{BASE_URL}/mobile/getUserBoxStatus",
        "data": {
            "userId": USER_ID
        }
    },

    "3_获取用户信息": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/user/info",
        "data": {
            "userId": USER_ID
        }
    },

    "4_检查 App 版本": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/app/version/check",
        "data": {
            "platform": 2,
            "currentVersion": "1.0.0",
            "userId": USER_ID
        }
    },

    "5_检查视频券资格": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/coupon/checkEligibility",
        "data": {
            "userId": USER_ID
        }
    },

    "6_获取试用券列表": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/coupon/trialList",
        "data": {
            "pageNo": 1,
            "pageSize": 100,
            "status": 0,
            "userId": USER_ID
        }
    },

    "7_获取对手列表和视频": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/record/opponentListWithVideos",
        "data": {
            "startTime": "2026-08-03 00:00:00",
            "endTime": "2026-08-09 23:59:59",
            "page": 1,
            "pageSize": 20,
            "userId": USER_ID
        }
    },

    "8_获取对手统计数据": {
        "method": "POST",
        "url": f"{BASE_URL}/mp/record/opponentStatistics",
        "data": {
            "startTime": "2026-08-03 00:00:00",
            "endTime": "2026-08-09 23:59:59",
            "userId": USER_ID
        }
    }
}


# ============== 调试函数 ==============

def print_separator(char="=", length=80):
    print(char * length)


def call_api(name, endpoint):
    """调用单个 API 接口并打印结果"""
    print_separator()
    print(f"接口：{name}")
    print_separator("-")
    print(f"URL: {endpoint['url']}")
    print(f"Method: {endpoint['method']}")
    print(f"Request Data: {json.dumps(endpoint['data'], ensure_ascii=False, indent=2)}")
    print_separator("-")

    try:
        if endpoint['method'] == 'POST':
            response = requests.post(
                endpoint['url'],
                json=endpoint['data'],
                headers=HEADERS,
                timeout=10
            )
        else:
            response = requests.get(
                endpoint['url'],
                params=endpoint.get('data', {}),
                headers=HEADERS,
                timeout=10
            )

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body:")

        # 尝试解析 JSON
        try:
            result = response.json()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except:
            print(response.text)

        return response

    except requests.exceptions.RequestException as e:
        print(f" 请求失败：{e}")
        return None


def main():
    print("\n" + "=" * 80)
    print("  斯诺克大师 App API 接口调试脚本")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    results = {}

    # 依次调用所有接口
    for name, endpoint in API_ENDPOINTS.items():
        response = call_api(name, endpoint)
        results[name] = response
        print("\n")

    # 打印汇总
    print_separator("=")
    print("  调试结果汇总")
    print_separator("=")

    for name, response in results.items():
        if response is not None:
            status = "✅ 成功" if response.status_code == 200 else "❌ 失败"
            print(f"{status} | {name} | Status: {response.status_code}")
        else:
            print(f"❌ 失败 | {name} | 请求异常")

    print_separator("=")
    print("调试完成！")


if __name__ == "__main__":
    main()

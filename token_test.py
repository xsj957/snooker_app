"""
Token 验证脚本
使用微信登录获取的 accessToken 调用接口，验证 Token 有效性
"""
import requests
import os

# 禁用代理
os.environ["NO_PROXY"] = "*"

BASE_URL = "https://test.supervisions.cn"

# 从 wechatLogin 接口获取的 Token 信息
USER_ID = "aff7eae4-3680-4b89-9f01-819e02c3b6b5"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjanNqIiwiaXNzIjoiY2pzaiIsImV4cCI6MTgxNzU0MDc2NSwiYXV0aFR5cGUiOjQsInVzZXJJZCI6ImFmZjdlYWU0LTM2ODAtNGI4OS05ZjAxLTgxOWUwMmMzYjZiNSJ9.ahOE4ukCvLN-szO8Em5_xjBD1hbd0ARnC8n3yb0YlHU"
REFRESH_TOKEN = "234cf5187b85dfe4e9b642eebc91620e"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "refresh_token": REFRESH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Dart/3.0 (dart:io)",
}


def test_user_info():
    """测试1: 获取用户信息"""
    url = f"{BASE_URL}/mp/user/info"
    data = {"userId": USER_ID}
    print(f"测试1: POST {url}")
    print(f"  请求参数: {data}")

    try:
        resp = requests.post(url, json=data, headers=HEADERS,
                             proxies={"http": None, "https": None}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False


def test_my_clubs():
    """测试2: 获取我的俱乐部"""
    url = f"{BASE_URL}/mp/user/myClubs"
    data = {"userId": USER_ID}
    print(f"\n测试2: POST {url}")
    print(f"  请求参数: {data}")

    try:
        resp = requests.post(url, json=data, headers=HEADERS,
                             proxies={"http": None, "https": None}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False


def test_coupon():
    """测试3: 获取视频券信息"""
    url = f"{BASE_URL}/mp/coupon/checkEligibility"
    data = {"userId": USER_ID}
    print(f"\n测试3: POST {url}")
    print(f"  请求参数: {data}")

    try:
        resp = requests.post(url, json=data, headers=HEADERS,
                             proxies={"http": None, "https": None}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False


def test_expired_token():
    """测试4: 用过期/错误的 Token（验证鉴权是否生效）"""
    fake_headers = HEADERS.copy()
    fake_headers["Authorization"] = "Bearer invalid_token_xxx"
    url = f"{BASE_URL}/mp/user/info"
    data = {"userId": USER_ID}
    print(f"\n测试4: 用无效 Token 请求（预期被拒绝）")

    try:
        resp = requests.post(url, json=data, headers=fake_headers,
                             proxies={"http": None, "https": None}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False


def test_coupon_list():
    """测试5: 查询已有视频券列表"""
    url = f"{BASE_URL}/mp/coupon/trialList"
    data = {"userId": USER_ID, "status": 0}
    print(f"\n测试5: POST {url}")
    print(f"  请求参数: {data}")

    try:
        resp = requests.post(url, json=data, headers=HEADERS,
                             proxies={"http": None, "https": None}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        result = resp.json()
        print(f"  响应: {result}")
        if result.get("code") == 0 and result.get("data"):
            coupons = result["data"] if isinstance(result["data"], list) else result["data"].get("list", [])
            print(f"  券数量: {len(coupons)}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Token 验证脚本")
    print(f"  userId: {USER_ID}")
    print(f"  accessToken: {ACCESS_TOKEN[:30]}...")
    print(f"  过期时间: 2027-08-06 16:26:05")
    print("=" * 60)

    test_user_info()
    test_my_clubs()
    test_coupon()
    test_expired_token()
    test_coupon_list()

    print("\n" + "=" * 60)
    print("验证完成")

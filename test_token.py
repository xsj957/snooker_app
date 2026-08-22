#!/usr/bin/env python3
"""
接口调试脚本 — 每个接口一个方法，pytest 风格，按需调用

用法:
  python test_token.py                          # 运行全部
  python test_token.py -k test_user_info        # 运行指定接口
  python test_token.py -k test_opponent         # 模糊匹配
  python test_token.py -k "rank or coupon"      # 多条件

也可直接当普通脚本，注释掉 pytest 部分:
  python -c "from test_token import call; call('test_user_info')"
"""

import pytest
import requests
import json

# ===================== 配置区（改这里） =====================
TOKEN   = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjanNqIiwiaXNzIjoiY2pzaiIsImV4cCI6MTgxODkwNDM2MSwiYXV0aFR5cGUiOjQsInVzZXJJZCI6IjU3ZDcwM2RjLTY1OWEtNDQ3NC04OThlLWI3NWVmYTFmMmUwYSJ9.dCtKaZ3TZRH7RVBp4-hfonvPBHwbCgJqWaAM2wnvSrY"
USER_ID = "57d703dc-659a-4474-898e-b75efa1f2e0a"
BASE    = "https://test.supervisions.cn"

# 对手 user_id（交手记录等接口用）
OPPONENT_ID = "aff7eae4-3680-4b89-9f01-819e02c3b6b5"
# 默认俱乐部 ID
CLUB_ID = 45376
# 默认 client_id（设备）
CLIENT_ID = "2d14c8a0-66c6-4f04-aaa2-6cd00c991432"
# 比赛 ID（局列表、场视频等）
COMPETITION_ID = "fecd7c799ea5495ca23caceafaaca04b"
# ==============================================================

H = {"Authorization": TOKEN, "Content-Type": "application/json"}
P = {"http": None, "https": None}


def _post(path, data):
    """统一请求，返回 (code, msg, data_dict)"""
    r = requests.post(f"{BASE}/{path}", json=data, headers=H, timeout=10, proxies=P)
    rj = r.json()
    code = rj.get("code", -1)
    msg  = rj.get("msg", "")
    print(f"\n{'='*60}")
    print(f"  {path}")
    print(f"  code={code}  msg={msg}")
    print(f"{'='*60}")
    print(json.dumps(rj, ensure_ascii=False, indent=2)[:2000])
    return code, msg, rj


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ① 用户模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_user_info():
    """获取用户信息"""
    _post("mp/user/info", {"userId": USER_ID})

def test_my_clubs():
    """我的俱乐部列表"""
    _post("mp/user/myClubs", {"userId": USER_ID})

def test_save_default_club():
    """设置默认俱乐部"""
    _post("mp/user/saveDefaultClub", {"clubId": CLUB_ID, "userId": USER_ID})

def test_wechat_login():
    """微信登录（需要真实 code，仅占位）"""
    _post("mp/oauth/wechatLogin", {"code": "YOUR_WECHAT_CODE"})

def test_user_rating():
    """用户评级"""
    _post("mp/user/rating", {"userId": USER_ID, "lang": "zh_CN"})

def test_break_score_list():
    """单杆高分列表"""
    _post("mp/user/breakScoreList", {
        "pageNo": 1, "pageSize": 30,
        "sortingFields": "[]",
        "userId": USER_ID,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ② 版本 & 盒子
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_version_check():
    """检查 App 版本"""
    _post("mp/app/version/check", {
        "platform": 2, "currentVersion": "1.0.0", "userId": USER_ID,
    })

def test_box_status():
    """获取盒子状态"""
    _post("mobile/getUserBoxStatus", {"userId": USER_ID})

def test_bind_box():
    """扫码绑定盒子"""
    _post("mobile/loginBoxAfterScanningQrCode", {
        "encryptedString": "http://weixin.qq.com/q/02AYDNBsWOf9E1JX0n1GcW",
        "userId": USER_ID,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ③ 视频券模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_coupon_eligibility():
    """检查视频券资格/剩余"""
    _post("mp/coupon/checkEligibility", {"userId": USER_ID})

def test_coupon_trial_list():
    """试用券列表"""
    _post("mp/coupon/trialList", {
        "pageNo": 1, "pageSize": 10, "status": 2, "userId": USER_ID,
    })

def test_coupon_list():
    """视频券列表（status: 0=有效 1=已用 2=已过期）"""
    _post("mp/coupon/queryCouponList", {
        "pageNo": 1, "pageSize": 20, "status": 0,
        "userId": USER_ID, "lang": "zh_CN",
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ④ 交手记录模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_opponent_list():
    """对手列表（含视频卡片）"""
    _post("mp/record/opponentListWithVideos", {
        "startTime": "2026-01-01 00:00:00",
        "endTime":   "2026-12-31 23:59:59",
        "page": 1, "pageSize": 10, "userId": USER_ID,
    })

def test_opponent_stats():
    """对手统计"""
    _post("mp/record/opponentStatistics", {
        "userId": USER_ID,
        "startTime": "2026-01-01 00:00:00",
        "endTime":   "2026-12-31 23:59:59",
    })

def test_competition_list():
    """比赛列表（含视频卡片）"""
    _post("mp/record/competitionListWithVideos", {
        "userA": USER_ID, "userB": OPPONENT_ID,
        "startTime": "2026-01-01 00:00:00",
        "endTime":   "2026-12-31 23:59:59",
        "page": 1, "pageSize": 10, "userId": USER_ID,
    })

def test_competition_stats():
    """比赛统计"""
    _post("mp/record/competitionStatistics", {
        "userA": USER_ID, "userB": OPPONENT_ID,
        "startTime": "2026-01-01 00:00:00",
        "endTime":   "2026-12-31 23:59:59",
        "userId": USER_ID,
    })

def test_inning_list():
    """局列表"""
    _post("mp/record/inningList", {
        "competitionId": COMPETITION_ID, "userId": USER_ID,
    })

def test_inning_stats():
    """局统计"""
    _post("mp/record/inningStatistics", {
        "competitionId": COMPETITION_ID, "userId": USER_ID,
    })

def test_barchart():
    """柱状图统计"""
    _post("mp/record/barchart", {
        "userId": USER_ID,
        "startTime": "2026-08-01 00:00:00",
        "endTime":   "2026-08-31 23:59:59",
    })

def test_statics():
    """综合统计"""
    _post("mp/record/statics", {
        "userId": USER_ID,
        "startTime": "2026-08-01 00:00:00",
        "endTime":   "2026-08-31 23:59:59",
    })

def test_device_online():
    """设备在线状态"""
    _post("mp/record/deviceOnlineInfo", {
        "competitionId": COMPETITION_ID, "userId": USER_ID,
    })

def test_mark_video_viewed():
    """标记视频已观看（消除 new 标记）"""
    _post("mp/record/markVideoViewed", {
        "videoOrderId": 2004, "userId": USER_ID,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑤ 我的视频模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_my_videos_ready():
    """待制作视频列表"""
    _post("video/videoClient/myVideos/readyV2", {
        "pageNo": 1, "pageSize": 10, "clientId": CLIENT_ID, "userId": USER_ID,
    })

def test_my_videos_processing():
    """制作中视频列表"""
    _post("video/videoClient/myVideos/processingV2", {
        "pageNo": 1, "pageSize": 10, "clientId": CLIENT_ID, "userId": USER_ID,
    })

def test_my_videos_failed():
    """制作失败视频列表"""
    _post("video/videoClient/myVideos/failedV2", {
        "pageNo": 1, "pageSize": 10, "clientId": CLIENT_ID, "userId": USER_ID,
    })

def test_competition_videos():
    """场比赛视频列表"""
    _post("video/videoinfo/competitionVideos", {
        "competitionId": COMPETITION_ID, "userId": USER_ID,
    })

def test_video_statistics():
    """视频统计"""
    _post("video/videoClient/getVideoStatistics", {
        "clientId": CLIENT_ID, "userId": USER_ID,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑥ 视频操作模块（写操作，谨慎调用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_buy_video():
    """使用视频券解锁视频（写操作！）"""
    _post("video/videoinfo/buyitUseComboV3", {
        "videoId": 12246, "payChannel": 2,
        "clientId": CLIENT_ID, "userId": USER_ID, "lang": "zh_CN",
    })

def test_update_client_info():
    """更新客户端信息（写操作）"""
    _post("video/videoClient/updateClientInfo", {
        "clientId": CLIENT_ID, "attributeType": 1, "attributeValue": 1,
        "userId": USER_ID, "lang": "zh_CN",
    })

def test_update_video_status():
    """更新视频状态（写操作！）"""
    _post("video/videoClient/updateStatus", {
        "clientId": CLIENT_ID, "status": 3, "videoId": 12284,
        "videoOrderId": 2100, "userId": USER_ID, "lang": "zh_CN",
    })

def test_add_video_event():
    """上报视频播放事件（写操作）"""
    import time
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    _post("mp/video/addVideoEventFromMobile", {
        "clientId": CLIENT_ID,
        "eventDataList": json.dumps([{
            "videoId": 12352, "eventTime": now,
            "playCount": 1, "playMs": 1,
        }]),
        "userId": USER_ID, "lang": "zh_CN",
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑦ 排行榜模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_rank_club_list():
    """俱乐部排行榜"""
    _post("mp/rank/clubList", {"userId": USER_ID})

def test_rating_list():
    """评级排行榜"""
    _post("mp/rank/ratingList", {
        "type": 3, "merchantAddressId": CLUB_ID,
        "areaId": None, "userId": USER_ID,
    })

def test_break_list():
    """破分排行榜"""
    _post("mp/rank/breakList", {
        "type": 0, "merchantAddressId": CLUB_ID,
        "areaId": None, "rankRange": 0, "timeRange": 0,
        "userId": USER_ID,
    })

def test_win_rate_list():
    """胜率排行榜"""
    _post("mp/rank/winRateList", {
        "type": 2, "merchantAddressId": CLUB_ID,
        "areaId": None, "rankRange": 0, "timeRange": 0,
        "userId": USER_ID,
    })

def test_user_break_rank():
    """用户个人破分排名"""
    _post("mp/rank/userBreakRank", {
        "rankRange": None, "timeRange": None,
        "merchantAddressId": None, "userId": USER_ID,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑧ 埋点
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_event_track():
    """埋点上报"""
    _post("mp/event/track", {
        "modelType": 1, "eventType": 5,
        "attrName": "test", "clientType": 1,
        "userId": USER_ID, "lang": "zh_CN",
    })


# ===================== 快捷调用 =====================
def call(name):
    """按名称调用单个接口，如 call('test_user_info')"""
    g = globals()
    if name in g:
        g[name]()
    else:
        # 模糊匹配
        matches = [k for k in g if k.startswith("test_") and name in k]
        if matches:
            for m in matches:
                g[m]()
        else:
            print(f"未找到: {name}")
            print("可用:", ", ".join(k for k in g if k.startswith("test_")))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

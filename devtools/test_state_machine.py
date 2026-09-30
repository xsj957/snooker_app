#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓包状态机回归测试 v3.2 — 合成 logcat fixture，无需真机。

运行: python devtools/test_state_machine.py

覆盖 2026-09 全面排查 + 修复审查确认的根因:
  1. 系统日志行不得进入请求体/响应体（截图垃圾体根因）
  2. 响应段开始必须重置 in_data；响应分片按 '' 拼接并做完整性四重判定
  3. 响应归属: resp_uri 不匹配入 OrphanCache（设备维度+TTL+完整优先）
  4. 隐藏接口窗口零占用；但认证信息仍采集
  5. _dart_to_json: 嵌套/方括号/负深度不塌缩/完全消费
  6. 污染体/不配平体/带尾巴体 → _fetch_full_response 拒绝重放（不发网络请求）
  7. DioException 段抑制: 不产幻影记录
  8. payload 含字面量 [DIO] 不破坏协议行解析（锚定匹配）
  9. 请求体续行不被 uri:/method: 劫持
 10. 其它 *** 标记收尾 headers 态；空响应不产 captured 对象
 11. 单行 >=4000 字符的响应判截断（complete=False）
"""
import json
import os
import sys
import time

_devtools_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_devtools_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from devtools.api_tool import (
    new_request_buf, process_log_line, finalize_buf, OrphanCache,
)
from devtools.server import _dart_to_json, _fetch_full_response, _parse_request_data

SYS = "09-28 14:33:22.006 18894 18960 D SurfaceComposerClient: Transaction::setDataspace: 142671072"
SYS2 = "09-28 14:33:22.016 18894 18960 D HWUI    : VulkanManager::finishFrame,duration=0.1219 ms,mRtCacheCount=67"


def dio(msg):
    """构造一条带 flutter tag + [DIO] 前缀的 logcat 行"""
    return f"09-28 14:33:22.000 18894 18960 I flutter : [DIO] {msg}"


def feed(lines, hide_list=None, device="dev1", cache=None):
    buf = new_request_buf()
    recs = []
    orphan = cache if cache is not None else OrphanCache()

    def on_complete(b, dev, reason):
        rec = finalize_buf(b, dev, reason, orphan)
        if rec:
            recs.append(rec)

    for ln in lines:
        process_log_line(ln, device, buf, hide_list or [], on_complete, None, orphan)
    rec = finalize_buf(buf, device, "flush", orphan)
    if rec:
        recs.append(rec)
    return recs, orphan


def test_system_lines_not_in_body():
    """截图症状复现序列: data 行后跟系统行洪峰，再跟响应段"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mp/event/track?lang=zh_CN"),
        dio("method: POST"),
        dio("data: {success: true, eventId: [64660], count: 0, msg: success}"),
        SYS, SYS2, SYS,
        dio("*** Response ***"),
        dio("content-type: application/json"),
        dio("Response Text: {code: 0, msg: ok}"),
        SYS,
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mp/user/info?lang=zh_CN"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    track = recs[0]
    assert track['uri'].endswith('/mp/event/track?lang=zh_CN'), track['uri']
    assert track['data_str'] == "{success: true, eventId: [64660], count: 0, msg: success}", track['data_str']
    assert 'SurfaceComposer' not in track['data_str']
    assert track['captured'] and track['captured']['complete'], track['captured']
    assert track['captured']['text'] == '{code: 0, msg: ok}'


def test_response_chunks_and_seal():
    """分片响应体按 '' 拼接; 配平即封口; 封口后系统行不入任何桶"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/video/videoinfo/competitionVideos?lang=zh_CN"),
        dio("method: POST"),
        dio("data: {competitionId: c6b15a, page: 1}"),
        dio("*** Response ***"),
        dio('Response Text: {"code":0,"data":{"list":[{"id":1,"name":"进攻失败合集"}'),
        '],"total":1}}',
        SYS,
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mp/user/info?lang=zh_CN"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    cv = recs[0]
    assert cv['data_str'] == "{competitionId: c6b15a, page: 1}", cv['data_str']
    assert cv['captured']['complete'] is True
    assert json.loads(cv['captured']['text'])['data']['list'][0]['name'] == "进攻失败合集"


def test_orphan_response_not_overwritten():
    """并发交错: A 的响应段落在 B 的窗口内; 新 Response 段不得覆写已封口旧段"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/A"),
        dio("method: POST"),
        dio("data: {a: 1}"),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/B"),
        dio("method: POST"),
        dio("data: {b: 2}"),
        dio("*** Response ***"),
        dio("uri: https://test.supervisions.cn/A"),
        dio('Response Text: {"code":0,"who":"A"}'),
        dio("*** Response ***"),
        dio("uri: https://test.supervisions.cn/B"),
        dio('Response Text: {"code":0,"who":"B"}'),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/C"),
        dio("method: POST"),
    ]
    recs, orphan = feed(lines)
    b_rec = [r for r in recs if r['uri'].endswith('/B')]
    assert b_rec and b_rec[0]['captured'] and '"who":"B"' in b_rec[0]['captured']['text'], b_rec
    a_orphan = orphan.pop(("dev1", "https://test.supervisions.cn/A"))
    assert a_orphan and a_orphan['text'] == '{"code":0,"who":"A"}', orphan.keys()


def test_orphan_device_and_ttl():
    """orphan 缓存: 跨设备不可领用; 过期不可领用"""
    cache = OrphanCache(ttl=10)
    cache.put(("dev1", "U"), {'text': 'T', 'headers': {}, 'complete': True})
    assert cache.pop(("dev2", "U")) is None
    assert cache.pop(("dev1", "U"))['text'] == 'T'
    stale = OrphanCache(ttl=0)
    stale.put(("dev1", "U"), {'text': 'T', 'headers': {}, 'complete': True})
    time.sleep(0.01)
    assert stale.pop(("dev1", "U")) is None


def test_hidden_window_no_pollution():
    """隐藏接口的系统行/响应不得泄漏进下一个可见请求"""
    hide = ["/mobile/getUserBoxStatus"]
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mobile/getUserBoxStatus?lang=zh_CN"),
        dio("method: POST"),
        dio("data: {userId: u1}"),
        SYS, SYS2,
        dio("*** Response ***"),
        dio('Response Text: {"box":1}'),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mp/user/info?lang=zh_CN"),
        dio("method: POST"),
        dio("data: {userId: u1}"),
    ]
    recs, _ = feed(lines, hide)
    assert len(recs) == 1, recs
    info = recs[0]
    assert info['uri'].endswith('/mp/user/info?lang=zh_CN')
    assert info['data_str'] == "{userId: u1}", info['data_str']
    assert info['captured'] is None


def test_auth_captured_in_hidden_window():
    """隐藏请求段里的 Authorization/refresh_token 仍要采集（自动认证不被饿死）"""
    auth = []
    buf = new_request_buf()
    recs = []
    orphan = OrphanCache()

    def on_complete(b, d, r):
        rec = finalize_buf(b, d, r, orphan)
        if rec:
            recs.append(rec)

    def on_auth(kind, val, dev):
        auth.append((kind, val))

    for ln in [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/mp/user/info?lang=zh_CN"),
        dio("method: POST"),
        dio("Authorization: Bearer TOK123"),
        dio("refresh_token: RT456"),
        dio("data: {userId: u1}"),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]:
        process_log_line(ln, "dev1", buf, ["/mp/user/info"], on_complete, on_auth, orphan)
    assert ('token', 'Bearer TOK123') in auth, auth
    assert ('refresh', 'RT456') in auth, auth


def test_dart_parser():
    assert _dart_to_json("{a: 1, b: [1, 2, 3], c: {d: x, e: null}}") == \
        {"a": 1, "b": [1, 2, 3], "c": {"d": "x", "e": None}}
    polluted = ("{success: true, eventId: [64660], count: 0, msg: success} "
                "09-28 14:33:22.006 18894 18960 D SurfaceComposerClient: Transaction::setDataspace: 1")
    parsed = _dart_to_json(polluted)
    assert parsed is not None and len(parsed) == 4, parsed
    assert parsed["eventId"] == [64660], parsed
    # 标量保留原文（headers 采集路径），值内逗号不被误切
    assert _dart_to_json("{accept: a,b, x-token: null}", scalars_as_str=True) == \
        {"accept": "a,b", "x-token": "null"}


def test_replay_refusal():
    """污染体/不配平体必须在发网络请求前被拒绝（断网桩: 触网即失败）"""
    import http.client as hc
    origs = (hc.HTTPSConnection, hc.HTTPConnection)

    def _boom(*a, **k):
        raise AssertionError("replay refusal must not touch network")

    hc.HTTPSConnection = _boom
    hc.HTTPConnection = _boom
    try:
        r = _fetch_full_response("https://test.supervisions.cn/mp/user/info", "POST",
                                 "{ok: 1} " + SYS)
        assert r['error'] and 'body_polluted' in r['error'], r
        r2 = _fetch_full_response("https://test.supervisions.cn/mp/user/info", "POST", "{ok: 1,")
        assert r2['error'] and 'body_unparseable' in r2['error'], r2
        r4 = _fetch_full_response("https://test.supervisions.cn/mp/user/info", "POST",
                                  "{ok: 1} tail junk")
        assert r4['error'] and 'body_unparseable' in r4['error'], r4  # 配平但带尾巴也拒
    finally:
        hc.HTTPSConnection, hc.HTTPConnection = origs


def test_parse_request_data():
    d, raw, ok = _parse_request_data('{"a": 1}')
    assert ok and d == {"a": 1}
    d, raw, ok = _parse_request_data("garbage without braces")
    assert not ok and d == {}
    d, raw, ok = _parse_request_data("")
    assert ok and d == {}


def test_exception_suppress_phantom():
    """DioException 段回打的 uri/method 不得构成幻影请求"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio("data: {x: 1}"),
        dio("*** DioException ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    assert len(recs) == 2, [r['uri'] for r in recs]
    assert recs[0]['exception'] is True
    assert recs[0]['data_str'] == "{x: 1}"
    assert recs[1]['uri'].endswith('/Y')


def test_dio_literal_in_payload():
    """payload 含字面量 [DIO] 不破坏协议行解析（锚定匹配）"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio('data: {"msg":"hello [DIO] world"}'),
        dio("*** Response ***"),
        dio('Response Text: {"code":0,"log":"begin [DIO] tail"}'),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    x = recs[0]
    assert x['data_str'] == '{"msg":"hello [DIO] world"}', x['data_str']
    assert x['captured'] and x['captured']['text'] == '{"code":0,"log":"begin [DIO] tail"}', x['captured']


def test_in_data_continuation_hijack():
    """多行请求体的续行含 uri:/method: 字样不得劫持状态"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio("data: {info: {"),
        "uri: https://cdn.cn/x.mp4",
        "method: GET, id: 7",
        "}}",
        dio("*** Response ***"),
        dio('Response Text: {"code":0}'),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    x = recs[0]
    assert x['uri'].endswith('/X') and x['method'] == 'POST', (x['uri'], x['method'])
    assert x['data_str'] == "{info: {uri: https://cdn.cn/x.mp4method: GET, id: 7}}", x['data_str']


def test_other_marker_closes_headers():
    """其它 *** 段标记收尾 headers 态; 空响应体不产 captured 对象（不挤掉 orphan）"""
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio("*** Response ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("*** Dio Error ***"),
        "timeout after 30s: read failed",
        "retry-count: 3",
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    assert recs[0]['captured'] is None, recs[0]['captured']


def test_long_line_truncation_incomplete():
    """单行 >=4000 字符的响应（logcat 截断嫌疑）判 complete=False"""
    big_cut = ('{"code":0,"pad":"' + 'A' * 4200 + '"}')[:4100]
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/X"),
        dio("method: POST"),
        dio("*** Response ***"),
        dio("Response Text: " + big_cut),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    assert recs[0]['captured'] and recs[0]['captured']['complete'] is False, recs[0]['captured']


def test_truncated_json_not_complete():
    """截断到半键的 JSON（EOF 处被解析器消费完）不得判 complete —— 截图6 根因"""
    cut = '{"code":0,"data":{"list":[{"id":14375,"path":null,"competitionId":"3d7e","city":'
    lines = [
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/video/videoClient/myVideos/processingV2?lang=zh_CN"),
        dio("method: POST"),
        dio("*** Response ***"),
        dio("Response Text: " + cut),
        dio("*** Request ***"),
        dio("uri: https://test.supervisions.cn/Y"),
        dio("method: POST"),
    ]
    recs, _ = feed(lines)
    cap = recs[0]['captured']
    assert cap and cap['complete'] is False, cap


def test_replay_policy_tiers():
    """重放闸门三级: 副作用全禁 / 埋点仅测试环境 / 只读全放; 变体不绕过"""
    from devtools.server import replay_policy
    assert replay_policy('/mp/event/track', 'test')[0] is True
    assert replay_policy('/mp/event/track', 'prod')[0] is False
    assert replay_policy('/video/videoinfo/buyitUseComboV3', 'test')[0] is False
    assert replay_policy('/video/videoinfo/buyitUseComboV3', 'prod')[0] is False
    assert replay_policy('/mp/user/info', 'test')[0] is True
    assert replay_policy('/VIDEO/VIDEOINFO/BUYITUSECOMBOV3/', 'test')[0] is False
    # 幂等写: 测试环境放行 / 生产禁止
    assert replay_policy('/video/videoClient/updateStatus', 'test')[0] is True
    assert replay_policy('/video/videoClient/updateStatus', 'prod')[0] is False
    assert replay_policy('/mp/record/markVideoViewed', 'test')[0] is True


def test_profile_classify_and_decide():
    """方案 C: 画像分级(small/large/unstable) + 决策矩阵"""
    import tempfile
    from devtools.server import ProfileManager
    from devtools.api_tool import decide_replay

    pm = ProfileManager(os.path.join(tempfile.mkdtemp(), 'p.json'))
    try:
        k = 'POST [测试] /x'
        for _ in range(5):
            pm.observe(k, 200)
        assert pm.get(k)['class'] == 'small', pm.get(k)
        pm.observe(k, 9000)
        assert pm.get(k)['class'] == 'large', pm.get(k)
        assert pm.get(k)['size_p95'] >= 9000

        k2 = 'POST [测试] /y'
        for _ in range(10):
            pm.observe(k2, 100)
        for _ in range(3):
            pm.observe(k2, 100, truncated=True)
        assert pm.get(k2)['class'] == 'unstable', pm.get(k2)  # 截断率 3/13 > 20%

        # 决策矩阵
        assert decide_replay(False, False, 'large', 'auto') is False   # 安全闸门优先
        assert decide_replay(True, True, 'small', 'auto') is False     # 已知小+捕获完整=零重放
        assert decide_replay(True, True, None, 'auto') is False        # 未知+捕获完整=零重放(学习)
        assert decide_replay(True, True, 'large', 'auto') is True      # 已知大=主动重放
        assert decide_replay(True, True, 'unstable', 'auto') is True
        assert decide_replay(True, False, 'small', 'auto') is True     # 截断必重放
        assert decide_replay(True, True, 'small', 'reactive') is False
        assert decide_replay(True, False, 'small', 'reactive') is True
        assert decide_replay(True, True, 'small', 'always') is True
    finally:
        pm.shutdown()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

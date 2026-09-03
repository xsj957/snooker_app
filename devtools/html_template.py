# DevTools HTML 模板（内嵌，无需外部 index.html）
# 由 server.py 的 get_html() 直接引用

DEVTOOLS_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API DevTools - 斯诺克大师</title>
<style>
/* ===== Reset & Base ===== */
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden;font-family:'SF Mono','Cascadia Code','Consolas','Monaco',monospace;font-size:13px;background:#1e1e1e;color:#d4d4d4}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:#1e1e1e}
::-webkit-scrollbar-thumb{background:#424242;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#555}

/* ===== Layout ===== */
.app{display:flex;flex-direction:column;height:100vh}

/* ===== Header ===== */
.header{display:flex;align-items:center;gap:10px;padding:8px 16px;background:#252526;border-bottom:1px solid #3c3c3c;flex-shrink:0}
.logo{color:#4ec9b0;font-weight:700;font-size:14px;white-space:nowrap}
.logo span{color:#808080;font-weight:400;margin-left:6px}
.divider{width:1px;height:20px;background:#3c3c3c;flex-shrink:0}
.toolbar{display:flex;gap:6px;align-items:center;flex-wrap:nowrap;overflow:hidden}

/* Filter pills */
.pill{padding:3px 10px;border:1px solid #4a4a4a;border-radius:12px;background:transparent;color:#aaa;font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit}
.pill:hover{background:#2d2d2d;color:#d4d4d4;border-color:#666}
.pill.active{background:#007acc;border-color:#007acc;color:#fff}
.pill .badge{display:inline-block;margin-left:4px;padding:0 5px;border-radius:8px;font-size:10px;background:rgba(255,255,255,.15)}
.pill.active .badge{background:rgba(255,255,255,.25)}

/* Search */
.search-box{display:flex;align-items:center;gap:4px;background:#1e1e1e;border:1px solid #3c3c3c;border-radius:4px;padding:0 8px;margin-left:auto;flex-shrink:1;min-width:0}
.search-box:focus-within{border-color:#007acc}
.search-box input{background:transparent;border:none;color:#d4d4d4;padding:4px 6px;font-size:12px;font-family:inherit;outline:none;width:160px;min-width:60px}
.search-box input::placeholder{color:#555}
.search-icon{color:#555;font-size:13px}

/* Buttons */
.btn{padding:4px 10px;border:1px solid #4a4a4a;border-radius:4px;background:transparent;color:#aaa;font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit}
.btn:hover{background:#2d2d2d;color:#d4d4d4;border-color:#666}
.btn.active{background:#007acc;border-color:#007acc;color:#fff}
.btn-clear{border-color:#5a3030;color:#c44}
.btn-clear:hover{background:#3a1515;border-color:#a44}
.btn-record{padding:4px 8px;border:none;background:transparent;color:#555;font-size:15px;cursor:pointer;transition:color .15s}
.btn-record:hover{color:#d4d4d4}
.btn-record.active{color:#e55}

/* Layout toggle & expand buttons */
.btn-layout{padding:4px 8px;border:none;background:transparent;color:#666;font-size:14px;cursor:pointer;transition:color .15s;line-height:1}
.btn-layout:hover{color:#d4d4d4}
.btn-layout.active{color:#007acc}

/* Copy button (Preview tab toolbar) */
.btn-copy{padding:4px 12px;border:1px solid #3a6a3a;border-radius:4px;background:transparent;color:#4ec9b0;font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit;margin-left:8px}
.btn-copy:hover{background:#1a3a1a;border-color:#4ec9b0;color:#6ee7b7}
.btn-copy:active{background:#2a5a2a}

/* Toast notification */
.toast{position:fixed;top:20px;right:20px;padding:10px 20px;border-radius:6px;background:#2d5a2d;color:#4ec9b0;font-size:13px;font-family:inherit;z-index:9999;opacity:0;transform:translateY(-10px);transition:all .3s;pointer-events:none;border:1px solid #4ec9b0}
.toast.show{opacity:1;transform:translateY(0)}

/* ===== Main Body: Horizontal Split Layout ===== */
.main-body{display:flex;flex:1;overflow:hidden;position:relative}

/* ===== Request List (Virtual Scroll) ===== */
.request-list{flex:1;overflow-y:auto;min-width:280px;position:relative;background:#1e1e1e}
.request-list.full-width{position:absolute;left:0;right:0;top:0;bottom:0;z-index:5}
.req-header-row{display:grid;grid-template-columns:48px 62px 1fr 75px 70px 70px;background:#2d2d2d;position:sticky;top:0;z-index:10}
.req-header-row > *{color:#9cdcfe;font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.5px;padding:5px 10px;text-align:left;user-select:none;border-bottom:2px solid #3c3c3c;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.req-header-row > *:nth-child(5),.req-header-row > *:nth-child(6){text-align:right}
.vs-container{position:relative}
.vs-row{display:grid;grid-template-columns:48px 62px 1fr 75px 70px 70px;align-items:center;height:30px;cursor:pointer;transition:background .1s;border-bottom:1px solid rgba(45,45,45,.6);position:absolute;left:0;right:0}
.vs-row:hover{background:#2a2a2a}
.vs-row.selected{background:#094771}
.vs-row.new-row{animation:flashNew .8s ease-out}
.vs-cell{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;padding:0 10px}
.vs-cell:nth-child(1){text-align:center}
.vs-cell:nth-child(5),.vs-cell:nth-child(6){text-align:right}
.vs-cell .req-device{font-size:11px;white-space:nowrap}
@keyframes flashNew{0%{background:#264f26}100%{background:transparent}}

/* Status dot */
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%}
.status-2xx{background:#4ec9b0}
.status-3xx{background:#4a90d9}
.status-4xx{background:#cca700}
.status-5xx{background:#f48771}
.status-err{background:#f48771;animation:pulse 1.2s infinite}
.status-wait{background:#555;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Method badges */
.method{font-weight:700;font-size:10px;letter-spacing:.3px}
.method-GET{color:#4ec9b0}
.method-POST{color:#569cd6}
.method-PUT{color:#cca700}
.method-DELETE{color:#f48771}

/* Environment badges */
.env-tag{display:inline-block;font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px;margin-right:4px;vertical-align:middle;letter-spacing:.3px}
.env-test{background:#1b3a1b;color:#6ccb5f;border:1px solid #2d5a2d}
.env-prod{background:#3a2a1b;color:#f0a050;border:1px solid #5a4020}

/* Path & URL */
.req-path{color:#ce9178;max-width:100%}
.req-name{color:#d4d4d4;max-width:100%}
.req-name .api-path{color:#ce9178}
.req-device{color:#dcdcaa;font-size:11px}
.req-size,.req-time{color:#b5b5b5;text-align:right;font-variant-numeric:tabular-nums}
.req-time.slow{color:#cca700}
.req-time.very-slow{color:#f48771}
.tag-new{display:inline-block;margin-left:6px;padding:0 4px;border-radius:2px;font-size:9px;background:#4ec9b0;color:#1e1e1e;font-weight:700;vertical-align:middle}

/* ===== Drag Handle ===== */
.drag-handle{width:6px;background:#2d2d2d;cursor:col-resize;flex-shrink:0;position:relative;transition:background .15s;z-index:20}
.drag-handle:hover,.drag-handle.active{background:#007acc}
.drag-handle::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:2px;height:24px;background:#555;border-radius:1px}
.drag-handle:hover::after,.drag-handle.active::after{background:#007acc}

/* ===== Detail Panel ===== */
.detail-panel{flex:1;display:flex;flex-direction:column;min-width:300px;background:#1e1e1e;position:relative}
.detail-panel.hidden{display:none}
.detail-panel.expanded{position:absolute;left:0;right:0;top:0;bottom:0;z-index:30}

/* Tabs */
.tabs{display:flex;background:#2d2d2d;border-bottom:1px solid #3c3c3c;flex-shrink:0;align-items:center;gap:0}
.tab{padding:7px 16px;cursor:pointer;color:#888;font-size:12px;border-bottom:2px solid transparent;transition:all .15s;user-select:none}
.tab:hover{color:#d4d4d4;background:#333}
.tab.active{color:#fff;border-bottom-color:#007acc}
.tab .count{margin-left:4px;color:#666;font-size:10px}
.tab-detail-info{margin-left:auto;padding-right:12px;color:#666;font-size:11px;display:flex;gap:10px;align-items:center}
.tab-detail-info .sep{color:#3c3c3c}

/* Tab content */
.tab-content{flex:1;overflow-y:auto;padding:12px 16px}
.tab-content.hidden{display:none}

/* Preview toolbar (copy button row) */
.preview-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #333}
.preview-toolbar .toolbar-left{color:#888;font-size:11px}

/* Section labels */
.detail-section{margin-bottom:14px}
.detail-section:last-child{margin-bottom:0}
.section-label{color:#4ec9b0;font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;display:flex;align-items:center;gap:8px}
.section-label .info{color:#666;font-weight:400;text-transform:none;letter-spacing:0;font-size:11px}

/* Headers table */
.headers-table{width:100%;border-collapse:collapse;font-size:12px}
.headers-table td{padding:3px 0;vertical-align:top;word-break:break-all}
.headers-table .hk{color:#9cdcfe;width:180px;padding-right:12px;font-weight:500;white-space:nowrap}
.headers-table .hv{color:#ce9178}

/* JSON tree (collapsible) */
.json-tree{font-size:12px;line-height:1.6;font-family:'SF Mono','Cascadia Code','Consolas',monospace}
.json-tree .jt-key{color:#9cdcfe}
.json-tree .jt-str{color:#ce9178}
.json-tree .jt-num{color:#b5cea8}
.json-tree .jt-bool{color:#569cd6}
.json-tree .jt-null{color:#569cd6}
.json-tree .jt-bracket{color:#d4d4d4}
.json-tree .jt-children{padding-left:20px}
.json-tree .jt-toggle{cursor:pointer;user-select:none;color:#808080;display:inline-block;width:14px;text-align:center;font-size:10px;line-height:1.6}
.json-tree .jt-toggle:hover{color:#d4d4d4}
.json-tree .jt-row{white-space:nowrap}
.json-tree .jt-preview{color:#808080;font-style:italic}
.json-tree .jt-close-after{color:#d4d4d4}
.json-tree .jt-hl{background:#515c6a;border-radius:2px;padding:0 1px;outline:1px solid rgba(255,200,0,0.3)}
.json-tree .jt-hl-active{background:#3a3d18;outline:2px solid #f8d44e;z-index:1;position:relative}
.jt-match-info{font-size:11px;color:#b5b5b5;white-space:nowrap;min-width:60px;text-align:center}
.jt-nav-btn{background:transparent;border:1px solid #555;color:#ccc;width:20px;height:20px;cursor:pointer;border-radius:3px;font-size:10px;line-height:1;display:inline-flex;align-items:center;justify-content:center}
.jt-nav-btn:hover{background:#333;border-color:#888}

/* Raw text */
.raw-view{font-size:12px;line-height:1.5;white-space:pre-wrap;word-break:break-all;color:#d4d4d4;background:#252526;padding:12px;border-radius:4px;border:1px solid #333}

/* Placeholder */
.detail-placeholder{display:flex;align-items:center;justify-content:center;height:100%;color:#555;font-size:13px}

/* Timing bars */
.timing-item{display:flex;align-items:center;gap:8px;margin-bottom:4px;font-size:12px}
.timing-label{color:#9cdcfe;width:80px;text-align:right}
.timing-bar-wrap{flex:1;height:14px;background:#252526;border-radius:3px;overflow:hidden}
.timing-bar{height:100%;border-radius:3px;transition:width .3s}
.timing-val{color:#b5b5b5;width:70px;font-variant-numeric:tabular-nums}
.bar-queue{background:#569cd6}
.bar-dns{background:#4ec9b0}
.bar-connect{background:#cca700}
.bar-ttfb{background:#ce9178}
.bar-download{background:#c586c0}

/* ===== Empty & Loading ===== */
.empty-state,.loading-state{text-align:center;padding:50px 20px;color:#666}
.empty-state .icon,.loading-state .icon{font-size:40px;margin-bottom:12px}
.empty-state h3{color:#999;font-size:15px;margin-bottom:6px}
.loading-state p{color:#888}

/* ===== Footer ===== */
.footer{display:flex;align-items:center;padding:4px 16px;background:#007acc;color:#fff;font-size:11px;gap:16px;flex-shrink:0}
.footer-item{display:flex;align-items:center;gap:4px}
.footer-dot{width:6px;height:6px;border-radius:50%}
.footer-dot.live{background:#4ec9b0;animation:pulse 2s infinite}
.footer-dot.off{background:#888}
</style>
</head>
<body>
<div class="app">

    <!-- Header -->
    <div class="header">
        <div class="logo">⚡ API DevTools<span>斯诺克大师</span></div>
        <div class="divider"></div>
        <button class="btn-record active" id="btnRecord" title="录制中（点击切换）">●</button>
        <div class="toolbar">
            <button class="pill active" data-filter="all">全部 <span class="badge" id="cntAll">0</span></button>
            <button class="pill" data-filter="GET">GET</button>
            <button class="pill" data-filter="POST">POST</button>
            <button class="pill" data-filter="2xx" id="pill2xx">2xx <span class="badge" id="cnt2xx">0</span></button>
            <button class="pill" data-filter="3xx">3xx</button>
            <button class="pill" data-filter="4xx">4xx</button>
            <button class="pill" data-filter="5xx">5xx</button>
            <span style="width:1px;height:16px;background:#444;margin:0 2px"></span>
            <button class="pill" data-filter="env:test" title="测试环境"><span class="env-tag env-test" style="margin:0">测试</span></button>
            <button class="pill" data-filter="env:prod" title="生产环境"><span class="env-tag env-prod" style="margin:0">生产</span></button>
        </div>
        <div class="search-box">
            <span class="search-icon">🔍</span>
            <input type="text" id="searchInput" placeholder="过滤 URL / 参数 / JSON key..." style="width:200px">
            <span class="jt-match-info" id="matchInfo" style="display:none"></span>
            <button class="jt-nav-btn" id="matchPrev" style="display:none" title="上一个">&#9650;</button>
            <button class="jt-nav-btn" id="matchNext" style="display:none" title="下一个">&#9660;</button>
        </div>
        <!-- 布局控制按钮 -->
        <button class="btn-layout" id="btnLayoutToggle" title="切换左右/上下布局">⬌</button>
        <button class="btn-layout" id="btnExpandDetail" title="展开/收起详情面板">⛶</button>
        <button class="btn btn-clear" id="btnClear" title="清空记录">🗑 清空</button>
    </div>

    <!-- Main Body: 左右分栏 -->
    <div class="main-body" id="mainBody">
        <!-- Request list (Virtual Scroll) -->
        <div class="request-list" id="requestList">
            <div class="empty-state" id="emptyState">
                <div class="icon">📡</div>
                <h3>等待抓包数据...</h3>
                <p>请在 App 中操作，网络请求将实时显示在此处</p>
                <p style="margin-top:8px;color:#555">提示: 使用 <code>python devtools/api_tool.py auto</code> 启动</p>
            </div>
            <div id="vsWrapper" style="display:none">
                <div class="req-header-row">
                    <div>状态</div>
                    <div>方法</div>
                    <div>接口</div>
                    <div>设备</div>
                    <div style="text-align:right">大小</div>
                    <div style="text-align:right">耗时</div>
                </div>
                <div class="vs-container" id="vsContainer"></div>
            </div>
        </div>

        <!-- Drag Handle -->
        <div class="drag-handle" id="dragHandle" title="拖拽调整宽度"></div>

        <!-- Detail panel -->
        <div class="detail-panel hidden" id="detailPanel">
            <div class="tabs" id="tabsBar">
                <div class="tab active" data-tab="headers">Headers</div>
                <div class="tab" data-tab="payload">Payload</div>
                <div class="tab" data-tab="preview">Preview</div>
                <div class="tab" data-tab="raw">Raw</div>
                <div class="tab" data-tab="timing">Timing</div>
                <div class="tab-detail-info" id="tabDetailInfo"></div>
                <button class="btn btn-copy" style="margin-left:auto;font-size:12px;padding:4px 14px" onclick="copyBugReport()" title="复制 URL+Payload+响应，直接发给开发"> 复制 Bug 报告</button>
            </div>

            <!-- Headers tab -->
            <div class="tab-content" id="tabHeaders">
                <div class="detail-section">
                    <div class="section-label">General</div>
                    <div id="generalInfo"></div>
                </div>
                <div class="detail-section">
                    <div class="section-label">Request Headers <span class="info" id="reqHeaderCount"></span></div>
                    <table class="headers-table" id="reqHeadersTable"></table>
                </div>
                <div class="detail-section" id="respHeadersSection">
                    <div class="section-label">Response Headers <span class="info" id="respHeaderCount"></span></div>
                    <table class="headers-table" id="respHeadersTable"></table>
                </div>
            </div>

            <!-- Payload tab -->
            <div class="tab-content hidden" id="tabPayload">
                <div class="detail-section">
                    <div class="section-label">Query String Parameters</div>
                    <div class="json-view" id="queryParams"></div>
                </div>
                <div class="detail-section">
                    <div class="section-label">Request Body</div>
                    <div class="json-view" id="requestBody"></div>
                </div>
            </div>

            <!-- Preview tab -->
            <div class="tab-content hidden" id="tabPreview">
                <div class="json-tree" id="responsePreview"></div>
            </div>

            <!-- Raw tab -->
            <div class="tab-content hidden" id="tabRaw">
                <div class="raw-view" id="responseRaw"></div>
            </div>

            <!-- Timing tab -->
            <div class="tab-content hidden" id="tabTiming">
                <div id="timingContent"></div>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <!-- Footer -->
    <div class="footer">
        <div class="footer-item">
            <span class="footer-dot live" id="statusDot"></span>
            <span id="statusText">正在录制</span>
        </div>
        <div class="footer-item" id="footerStats">
            <span id="footerCount">0 个请求</span>
        </div>
        <div class="footer-item" style="margin-left:auto">
            <span id="lastUpdate">--:--:--</span>
        </div>
    </div>
</div>

<script>
// ==================== State ====================
const state = {
    requests: [],          // 全量数据（只存引用，不渲染）
    filtered: [],          // 筛选后的数据
    selectedId: null,
    filter: 'all',
    search: '',
    recording: true,
    lastId: null,
    activeTab: 'headers',
    // 虚拟滚动
    rowHeight: 30,
    visibleCount: 0,
    scrollTop: 0,
    // JSON 树搜索
    matchIndex: -1,
    matchElements: [],
    // 布局状态
    layoutMode: 'horizontal',  // 'horizontal' | 'vertical'
    detailExpanded: false,     // 详情面板是否全屏
    savedLeftWidth: null,      // 记住拖拽前的左侧宽度
};

// ==================== API Names ====================
const API_NAMES = {
    // ===== 用户 =====
    '/mp/user/info': '用户信息',
    '/mp/user/myClubs': '我的俱乐部',
    '/mp/user/saveDefaultClub': '设置默认俱乐部',
    '/mp/user/rating': '我的评级',
    '/mp/user/breakScoreList': '单杆分列表',
    '/mp/user/deleteAccount': '注销账号',

    // ===== 登录 =====
    '/mp/oauth/wechatLogin': '微信登录',

    // ===== 版本 =====
    '/mp/app/version/check': '版本检查',
    '/mp/app/domestic/version/check': '国内版版本检查',

    // ===== 视频券 =====
    '/mp/coupon/checkEligibility': '视频券资格',
    '/mp/coupon/trialList': '体验券列表',
    '/mp/coupon/queryCouponList': '我的视频券',

    // ===== 交手记录 =====
    '/mp/record/opponentListWithVideos': '交手卡片',
    '/mp/record/opponentStatistics': '对手统计',
    '/mp/record/competitionListWithVideos': '比赛场次',
    '/mp/record/competitionStatistics': '交手统计(双人)',
    '/mp/record/inningList': '局列表',
    '/mp/record/inningStatistics': '场次统计',
    '/mp/record/markVideoViewed': '标记视频已观看',
    '/mp/record/deviceOnlineInfo': '设备在线信息',
    '/mp/record/barchart': '柱状图数据',
    '/mp/record/statics': '个人统计数据',

    // ===== 排行 =====
    '/mp/rank/clubList': '俱乐部排行',
    '/mp/rank/userBreakRank': '单杆排行',
    '/mp/rank/ratingList': '评级排行',
    '/mp/rank/breakList': '进球排行',
    '/mp/rank/winRateList': '胜率排行',

    // ===== 埋点 =====
    '/mp/event/track': '埋点上报',
    '/mp/video/addVideoEventFromMobile': 'App播放事件上报',

    // ===== 盒子/工控机 =====
    '/mobile/getUserBoxStatus': '盒子状态',
    '/mobile/loginBoxAfterScanningQrCode': '扫码登录盒子',

    // ===== 我的视频(视频客户端) =====
    '/video/videoClient/getVideoStatistics': '视频统计概览',
    '/video/videoClient/myVideos/processingV2': '制作中视频',
    '/video/videoClient/myVideos/readyV2': '有效视频列表',
    '/video/videoClient/myVideos/failedV2': '失效视频列表',
    '/video/videoClient/updateClientInfo': '更新设备信息',
    '/video/videoClient/updateStatus': '更新视频状态',

    // ===== 视频详情/解锁 =====
    '/video/videoinfo/competitionVideos': '比赛场详情',
    '/video/videoinfo/buyitUseComboV3': '视频券解锁',

    // ===== 退款 =====
    '/video/videoOrder/appPostVideoRefund': '视频退款',
};

function getApiName(path) {
    return API_NAMES[path] || '';
}

// 从 full_url 提取纯路径（兼容测试/生产环境）
function extractPathFromUrl(url) {
    if (!url) return '';
    try {
        var u = new URL(url);
        return u.pathname + (u.search || '');
    } catch(e) {
        return url;
    }
}

// 检测环境（从 full_url 的域名判断）
function detectEnv(url) {
    if (!url) return {env: 'unknown', label: '未知', cls: ''};
    if (url.indexOf('app.supervisions.cn') !== -1) return {env: 'prod', label: '生产', cls: 'env-prod'};
    if (url.indexOf('test.supervisions.cn') !== -1) return {env: 'test', label: '测试', cls: 'env-test'};
    return {env: 'unknown', label: '未知', cls: ''};
}

function getShortPath(path) {
    const prefixes = ['/mp', '/mobile', '/video'];
    for (const p of prefixes) {
        if (path.startsWith(p + '/')) return path.slice(p.length);
    }
    return path;
}

// ==================== Helpers ====================
function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    const str = String(s);
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatSize(bytes) {
    if (!bytes || bytes <= 0) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function formatTime(ms) {
    if (!ms || ms <= 0) return '-';
    if (ms < 1) return ms.toFixed(1) + ' ms';
    if (ms < 1000) return Math.round(ms) + ' ms';
    return (ms / 1000).toFixed(2) + ' s';
}

function statusClass(code) {
    if (!code) return 'status-wait';
    if (code >= 200 && code < 300) return 'status-2xx';
    if (code >= 300 && code < 400) return 'status-3xx';
    if (code >= 400 && code < 500) return 'status-4xx';
    if (code >= 500) return 'status-5xx';
    return 'status-err';
}

function timeClass(ms) {
    if (ms > 2000) return 'very-slow';
    if (ms > 1000) return 'slow';
    return '';
}

// ==================== Toast ====================
function showToast(msg, duration) {
    var toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(function() { toast.classList.remove('show'); }, duration || 2000);
}

// ==================== Copy Bug Report (URL + Payload + Response) ====================
window.copyBugReport = function() {
    var req = state.requests.find(function(r) { return r.id === state.selectedId; });
    if (!req) { showToast(' 请先选择一条请求'); return; }
    var lines = [];
    lines.push('URL: ' + req.full_url);
        var rh = req.request_headers || {};
    var tokenKeys = ['Authorization', 'refresh_token'];
    var tokenLines = tokenKeys.filter(function(k) { return rh[k]; }).map(function(k) { return k + ': ' + rh[k]; });
    if (tokenLines.length) {
        lines.push('--- Auth Headers ---');
        tokenLines.forEach(function(l) { lines.push(l); });
        lines.push('');
    }
    var rd = req.request_data;
    if (rd && typeof rd === 'object') {
        lines.push('--- Request Body ---');
        lines.push(JSON.stringify(rd, null, 2));
        lines.push('');
    } else if (rd && typeof rd === 'string') {
        lines.push('--- Request Body ---');
        lines.push(rd);
        lines.push('');
    }
    var rb = req.response_body;
    if (rb !== null && rb !== undefined) {
        lines.push('--- Response Body ---');
        if (typeof rb === 'object') {
            lines.push(JSON.stringify(rb, null, 2));
        } else {
            lines.push(String(rb));
        }
    }
    var text = lines.join('\n');
    navigator.clipboard.writeText(text).then(function() {
        showToast(' 已复制 Bug 报告（' + text.length + ' 字符）');
    }).catch(function() {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); showToast(' 已复制'); }
        catch(e) { showToast(' 复制失败，请手动复制'); }
        document.body.removeChild(ta);
    });
};

// ==================== Copy Formatted JSON ====================
window.copyFormattedJson = function() {
    var req = state.requests.find(function(r) { return r.id === state.selectedId; });
    if (!req || !req.response_body) {
        showToast('⚠️ 无可复制的响应数据');
        return;
    }
    var text;
    if (typeof req.response_body === 'object') {
        text = JSON.stringify(req.response_body, null, 2);
    } else {
        text = String(req.response_body);
    }
    navigator.clipboard.writeText(text).then(function() {
        showToast('✅ 已复制格式化 JSON（' + text.length + ' 字符）');
    }).catch(function() {
        // Fallback for older browsers
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); showToast('✅ 已复制'); }
        catch(e) { showToast(' 复制失败，请手动复制'); }
        document.body.removeChild(ta);
    });
};

// ==================== Collapsible JSON Tree ====================
let _jtId = 0;

function buildJsonTree(data, keyName) {
    _jtId = 0;
    return _buildNode(data, keyName, 0, 2);  // 默认展开前 2 层
}

function _buildNode(value, key, depth, expandDepth) {
    const type = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;

    if (type === 'object' || type === 'array') {
        const id = 'jt' + (++_jtId);
        const isArr = type === 'array';
        const entries = isArr ? value : Object.keys(value);
        const count = entries.length;
        const preview = isArr
            ? 'Array(' + count + ')'
            : 'Object {' + count + '}';
        const shouldExpand = depth < expandDepth;

        if (count === 0) {
            return '<div class="jt-row">' +
                (key !== null ? '<span class="jt-key">' + escapeHtml(key) + '</span>: ' : '') +
                '<span class="jt-bracket">' + (isArr ? '[]' : '{}') + '</span>' +
            '</div>';
        }

        // 根据 shouldExpand 决定初始状态
        let html = '<div class="jt-row">' +
            '<span class="jt-toggle" data-jt="' + id + '" onclick="event.stopPropagation();_jtToggle(\'' + id + '\')">' + (shouldExpand ? '&#9660;' : '&#9654;') + '</span>' +
            (key !== null ? '<span class="jt-key">' + escapeHtml(key) + '</span>: ' : '') +
            '<span class="jt-bracket">' + (isArr ? '[' : '{') + '</span>' +
            '<span class="jt-preview" data-jt-preview="' + id + '" style="display:' + (shouldExpand ? 'none' : '') + '">' + preview + '</span>' +
            '<span class="jt-bracket" data-jt-close="' + id + '" style="display:' + (shouldExpand ? 'none' : 'inline') + '">' + (isArr ? ']' : '}') + '</span>' +
        '</div>';

        html += '<div class="jt-children" data-jt-children="' + id + '" style="display:' + (shouldExpand ? '' : 'none') + '">';
        if (isArr) {
            for (let i = 0; i < count; i++) {
                html += _buildNode(value[i], String(i), depth + 1, expandDepth);
            }
        } else {
            const keys = Object.keys(value);
            for (let i = 0; i < keys.length; i++) {
                html += _buildNode(value[keys[i]], keys[i], depth + 1, expandDepth);
            }
        }
        html += '</div>';
        // 展开后显示的关闭符号（jt-children 同级，缩进对齐）
        html += '<div data-jt-after="' + id + '" class="jt-children" style="display:' + (shouldExpand ? '' : 'none') + '">' +
            '<div class="jt-row">' +
                '<span class="jt-toggle" style="visibility:hidden">&#9660;</span>' +
                '<span class="jt-bracket">' + (isArr ? ']' : '}') + '</span>' +
            '</div>' +
        '</div>';
        return html;
    }

    // Primitive
    let valHtml;
    if (type === 'string') {
        valHtml = '<span class="jt-str">"' + escapeHtml(value) + '"</span>';
    } else if (type === 'number') {
        valHtml = '<span class="jt-num">' + value + '</span>';
    } else if (type === 'boolean') {
        valHtml = '<span class="jt-bool">' + value + '</span>';
    } else {
        valHtml = '<span class="jt-null">null</span>';
    }
    return '<div class="jt-row">' +
        (key !== null ? '<span class="jt-toggle" style="visibility:hidden">&#9660;</span><span class="jt-key">' + escapeHtml(key) + '</span>: ' : '') +
        valHtml +
    '</div>';
}

// Toggle expand/collapse (global, called from onclick)
window._jtToggle = function(id) {
    var toggle = document.querySelector('[data-jt="' + id + '"]');
    var children = document.querySelector('[data-jt-children="' + id + '"]');
    var after = document.querySelector('[data-jt-after="' + id + '"]');
    var preview = document.querySelector('[data-jt-preview="' + id + '"]');
    var close = document.querySelector('[data-jt-close="' + id + '"]');
    if (!toggle || !children) return;

    if (children.style.display === 'none') {
        // Expand
        children.style.display = '';
        if (after) after.style.display = '';
        toggle.innerHTML = '&#9660;';
        if (preview) preview.style.display = 'none';
        if (close) close.style.display = 'none';
    } else {
        // Collapse
        children.style.display = 'none';
        if (after) after.style.display = 'none';
        toggle.innerHTML = '&#9654;';
        if (preview) preview.style.display = '';
        if (close) close.style.display = 'inline';
    }
};

// ==================== JSON Tree Search Highlight ====================
function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlightJsonTree(container, term) {
    if (!container) return;
    state.matchElements = [];
    state.matchIndex = -1;

    // Remove old highlights
    var oldHls = container.querySelectorAll('.jt-hl');
    for (var i = 0; i < oldHls.length; i++) {
        var parent = oldHls[i].parentNode;
        parent.replaceChild(document.createTextNode(oldHls[i].textContent), oldHls[i]);
        parent.normalize();
    }

    if (!term) {
        updateMatchUI(0, -1);
        return;
    }

    var regex = new RegExp('(' + escapeRegExp(term) + ')', 'gi');

    // Find all searchable text nodes inside .jt-key and .jt-str
    var nodes = container.querySelectorAll('.jt-key, .jt-str');
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
        var textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);

        for (var j = 0; j < textNodes.length; j++) {
            var tn = textNodes[j];
            var text = tn.nodeValue;
            if (!regex.test(text)) continue;
            regex.lastIndex = 0;

            var parts = [];
            var lastIndex = 0;
            var match;
            while ((match = regex.exec(text)) !== null) {
                if (match.index > lastIndex) {
                    parts.push({type: 'text', value: text.slice(lastIndex, match.index)});
                }
                parts.push({type: 'match', value: match[1]});
                lastIndex = regex.lastIndex;
            }
            if (lastIndex < text.length) {
                parts.push({type: 'text', value: text.slice(lastIndex)});
            }

            var frag = document.createDocumentFragment();
            for (var k = 0; k < parts.length; k++) {
                if (parts[k].type === 'match') {
                    var span = document.createElement('span');
                    span.className = 'jt-hl';
                    span.textContent = parts[k].value;
                    frag.appendChild(span);
                    state.matchElements.push(span);
                } else {
                    frag.appendChild(document.createTextNode(parts[k].value));
                }
            }
            tn.parentNode.replaceChild(frag, tn);
        }
    }

    updateMatchUI(state.matchElements.length, state.matchElements.length > 0 ? 0 : -1);
    if (state.matchElements.length > 0) {
        state.matchIndex = 0;
        state.matchElements[0].classList.add('jt-hl-active');
    }
}

function updateMatchUI(total, idx) {
    var info = document.getElementById('matchInfo');
    var prev = document.getElementById('matchPrev');
    var next = document.getElementById('matchNext');
    if (total === 0) {
        info.style.display = 'none';
        prev.style.display = 'none';
        next.style.display = 'none';
    } else {
        info.style.display = '';
        prev.style.display = '';
        next.style.display = '';
        info.textContent = (idx + 1) + '/' + total;
    }
}

function expandParentsOf(el) {
    var node = el.parentNode;
    while (node) {
        if (node.classList && node.classList.contains('jt-children') && node.style.display === 'none') {
            var id = node.getAttribute('data-jt-children');
            if (id) {
                var toggle = document.querySelector('[data-jt="' + id + '"]');
                var after = document.querySelector('[data-jt-after="' + id + '"]');
                var preview = document.querySelector('[data-jt-preview="' + id + '"]');
                var close = document.querySelector('[data-jt-close="' + id + '"]');
                node.style.display = '';
                if (after) after.style.display = '';
                if (toggle) toggle.innerHTML = '&#9660;';
                if (preview) preview.style.display = 'none';
                if (close) close.style.display = 'none';
            }
        }
        node = node.parentNode;
    }
}

function navigateMatch(direction) {
    if (state.matchElements.length === 0) return;
    if (state.matchIndex >= 0 && state.matchElements[state.matchIndex]) {
        state.matchElements[state.matchIndex].classList.remove('jt-hl-active');
    }
    state.matchIndex += direction;
    if (state.matchIndex < 0) state.matchIndex = state.matchElements.length - 1;
    if (state.matchIndex >= state.matchElements.length) state.matchIndex = 0;
    var active = state.matchElements[state.matchIndex];
    active.classList.add('jt-hl-active');
    expandParentsOf(active);
    active.scrollIntoView({behavior: 'smooth', block: 'center'});
    updateMatchUI(state.matchElements.length, state.matchIndex);
}

// ==================== Virtual Scroll ====================
const vsContainer = document.getElementById('vsContainer');

function updateVirtualScroll() {
    const listEl = document.getElementById('requestList');
    const wrapper = document.getElementById('vsWrapper');
    const empty = document.getElementById('emptyState');
    const filtered = state.filtered;

    if (filtered.length === 0) {
        wrapper.style.display = 'none';
        empty.style.display = '';
        return;
    }

    wrapper.style.display = '';
    empty.style.display = 'none';

    const totalHeight = filtered.length * state.rowHeight;
    vsContainer.style.height = totalHeight + 'px';

    state.visibleCount = Math.ceil(listEl.clientHeight / state.rowHeight) + 5;
    const scrollTop = listEl.scrollTop;
    state.scrollTop = scrollTop;

    const startIdx = Math.max(0, Math.floor(scrollTop / state.rowHeight) - 2);
    const endIdx = Math.min(filtered.length, startIdx + state.visibleCount + 4);

    const existingRows = vsContainer.querySelectorAll('.vs-row');
    const existingMap = new Map();
    for (let i = 0; i < existingRows.length; i++) {
        existingMap.set(Number(existingRows[i].dataset.idx), existingRows[i]);
    }

    const frag = document.createDocumentFragment();
    for (let i = startIdx; i < endIdx; i++) {
        const req = filtered[i];
        let row = existingMap.get(i);
        if (!row) {
            row = document.createElement('div');
            row.className = 'vs-row';
            row.dataset.idx = i;
        }
        row.style.top = (i * state.rowHeight) + 'px';
        row.style.height = state.rowHeight + 'px';

        const sc = req.status || 0;
        const rawPath = req.path || '';
        // 兼容生产环境 path 可能是完整 URL 的情况
        const path = rawPath.startsWith('http') ? extractPathFromUrl(rawPath) : rawPath;
        const envInfo = detectEnv(req.full_url || rawPath);
        const apiName = getApiName(path);
        const tc = timeClass(req.time_ms);
        const sel = req.id === state.selectedId;

        row.className = 'vs-row' + (sel ? ' selected' : '') + (req.is_new ? ' new-row' : '');
        row.dataset.idx = i;
        row.onclick = function() { selectRequest(req.id); };

        row.innerHTML =
            '<div class="vs-cell"><span class="status-dot ' + statusClass(sc) + '"></span></div>' +
            '<div class="vs-cell"><span class="method method-' + req.method + '">' + req.method + '</span></div>' +
            '<div class="vs-cell"><span class="req-name">' +
                '<span class="env-tag ' + envInfo.cls + '">' + envInfo.label + '</span>' +
                (apiName ? '<span style="color:#888;margin-right:4px">' + escapeHtml(apiName) + '</span>' : '') +
                '<span class="api-path">' + escapeHtml(getShortPath(path)) + '</span>' +
            '</span>' + (req.is_new ? '<span class="tag-new">NEW</span>' : '') + '</div>' +
            '<div class="vs-cell"><span class="req-device">' + escapeHtml(req.device || '-') + '</span></div>' +
            '<div class="vs-cell"><span class="req-size">' + formatSize(req.size) + '</span></div>' +
            '<div class="vs-cell"><span class="req-time ' + tc + '">' + formatTime(req.time_ms) + '</span></div>';
        frag.appendChild(row);
    }

    for (const [idx, el] of existingMap) {
        if (idx < startIdx || idx >= endIdx) {
            vsContainer.removeChild(el);
        }
    }

    vsContainer.appendChild(frag);
}

let vsScrollTimer = null;
(function() {
    const listEl = document.getElementById('requestList');
    listEl.addEventListener('scroll', function() {
        if (vsScrollTimer) return;
        vsScrollTimer = requestAnimationFrame(function() {
            vsScrollTimer = null;
            updateVirtualScroll();
        });
    });
})();

// ==================== Data Fetching ====================
async function fetchLogs() {
    try {
        const params = new URLSearchParams();
        if (state.lastId) params.set('since', state.lastId);

        const resp = await fetch('/api/logs?' + params.toString());
        const data = await resp.json();

        if (data.logs && data.logs.length > 0) {
            if (state.recording) {
                const oldLen = state.requests.length;
                // full_reset = 服务器端 since_id 已被淘汰（buffer溢出），返回了全量数据
                // 此时应替换而非追加，否则会产生重复
                if (data.full_reset) {
                    state.requests = data.logs;
                } else {
                    // 增量追加，同时做 ID 去重防护
                    const existingIds = new Set(state.requests.map(function(r) { return r.id; }));
                    const newEntries = data.logs.filter(function(r) { return !existingIds.has(r.id); });
                    state.requests.push(...newEntries);
                }
                if (state.requests.length > 1000) {
                    state.requests = state.requests.slice(-1000);
                }
                if (state.requests.length !== oldLen) {
                    applyFilter();
                }
                if (state.selectedId) {
                    const sel = state.requests.find(function(r) { return r.id === state.selectedId; });
                    if (sel) {
                        const curBody = JSON.stringify(sel.response_body || '');
                        if (sel._lastBody !== curBody) {
                            sel._detailVersion = (sel._detailVersion || 0) + 1;
                            sel._lastBody = curBody;
                        }
                    }
                }
            }
            state.lastId = data.logs[data.logs.length - 1].id;
        }

        updateStats(data.stats || {total: state.requests.length, by_status: {}});
        requestAnimationFrame(updateVirtualScroll);

        if (state.selectedId) {
            const sel = state.requests.find(function(r) { return r.id === state.selectedId; });
            if (sel && sel._detailVersion !== (sel._lastRenderedVersion || 0)) {
                renderDetail(sel);
                sel._lastRenderedVersion = sel._detailVersion || 1;
            }
        }
    } catch (e) {
        console.error('Fetch error:', e);
    }
}

// ==================== Filter ====================
function applyFilter() {
    state.filtered = state.requests.filter(req => {
        const f = state.filter;
        if (f && f !== 'all') {
            const sc = req.status || 0;
            if (f === 'GET' || f === 'POST') {
                if (req.method !== f) return false;
            } else if (f === '2xx') { if (!(sc >= 200 && sc < 300)) return false; }
            else if (f === '3xx') { if (!(sc >= 300 && sc < 400)) return false; }
            else if (f === '4xx') { if (!(sc >= 400 && sc < 500)) return false; }
            else if (f === '5xx') { if (!(sc >= 500)) return false; }
            else if (f === 'env:test' || f === 'env:prod') {
                const targetEnv = f.split(':')[1];
                const envInfo = detectEnv(req.full_url || req.path || '');
                if (envInfo.env !== targetEnv) return false;
            }
        }
        if (state.search) {
            const s = state.search.toLowerCase();
            const rawPath = req.path || '';
            const resolvedPath = rawPath.startsWith('http') ? extractPathFromUrl(rawPath) : rawPath;
            const apiName = getApiName(resolvedPath);
            const envLabel = detectEnv(req.full_url || rawPath).label;
            const haystack = (resolvedPath + ' ' + apiName + ' ' + req.method + ' ' + envLabel + ' ' +
                JSON.stringify(req.request_data || '') + ' ' +
                JSON.stringify(req.response_body || '')).toLowerCase();
            if (!haystack.includes(s)) return false;
        }
        return true;
    });
}

// ==================== Stats ====================
function updateStats(stats) {
    const total = stats.total || state.requests.length;
    const by = stats.by_status || {};

    document.getElementById('cntAll').textContent = total;
    document.getElementById('cnt2xx').textContent = by['2xx'] || 0;

    document.getElementById('footerCount').textContent = total + ' 个请求';
    // 环境分布
    var testCnt = 0, prodCnt = 0;
    state.requests.forEach(function(r) {
        var e = detectEnv(r.full_url || r.path || '');
        if (e.env === 'test') testCnt++;
        else if (e.env === 'prod') prodCnt++;
    });
    var envParts = [];
    if (testCnt) envParts.push('<span class="env-tag env-test">测试 ' + testCnt + '</span>');
    if (prodCnt) envParts.push('<span class="env-tag env-prod">生产 ' + prodCnt + '</span>');
    var footerEl = document.getElementById('footerCount');
    footerEl.innerHTML = total + ' 个请求' + (envParts.length ? ' ' + envParts.join('') : '');
    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
}

// ==================== Select Request ====================
function selectRequest(id) {
    state.selectedId = id;
    const req = state.requests.find(function(r) { return r.id === id; });
    if (!req) return;

    const detailPanel = document.getElementById('detailPanel');
    const dragHandle = document.getElementById('dragHandle');
    detailPanel.classList.remove('hidden');
    // 手柄在水平布局 + 非全屏时显示
    if (state.layoutMode === 'horizontal' && !state.detailExpanded) {
        dragHandle.style.display = '';
    }
    renderDetail(req);
    req._detailVersion = (req._detailVersion || 0) + 1;
    req._lastRenderedVersion = req._detailVersion;
    req._lastBody = JSON.stringify(req.response_body || '');
    requestAnimationFrame(updateVirtualScroll);
}

// ==================== Render Detail ====================
function renderDetail(req) {
    const info = document.getElementById('tabDetailInfo');
    const rawPath = req.path || '';
    const resolvedPath = rawPath.startsWith('http') ? extractPathFromUrl(rawPath) : rawPath;
    const envInfo = detectEnv(req.full_url || rawPath);
    const apiName = getApiName(resolvedPath);
    info.innerHTML =
        '<span class="env-tag ' + envInfo.cls + '">' + envInfo.label + '</span>' +
        '<span class="method method-' + req.method + '">' + req.method + '</span>' +
        (apiName ? '<span style="color:#888;margin-right:6px">' + escapeHtml(apiName) + '</span>' : '') +
        '<span style="color:#ce9178">' + escapeHtml(resolvedPath) + '</span>' +
        '<span class="sep">|</span>' +
        '<span style="color:' + (((req.status||0)>=200&&(req.status||0)<300) ? '#4ec9b0' : '#f48771') + '">' + (req.status || '...') + '</span>' +
        '<span class="sep">|</span>' +
        '<span>' + formatTime(req.time_ms) + '</span>';

    const tab = state.activeTab;
    if (tab === 'headers') renderHeadersTab(req);
    else if (tab === 'payload') { renderPayloadTab(req); if (state.search) highlightJsonTree(document.getElementById('requestBody'), state.search); }
    else if (tab === 'preview') { renderPreviewTab(req); if (state.search) highlightJsonTree(document.getElementById('responsePreview'), state.search); }
    else if (tab === 'raw') renderRawTab(req);
    else if (tab === 'timing') renderTimingTab(req);
}

// ----- Headers Tab -----
function renderHeadersTab(req) {
    const general = document.getElementById('generalInfo');
    general.innerHTML =
        '<table class="headers-table">' +
        '<tr><td class="hk">Request URL</td><td class="hv">' + escapeHtml(req.full_url || req.path) + '</td></tr>' +
        '<tr><td class="hk">Request Method</td><td class="hv">' + req.method + '</td></tr>' +
        '<tr><td class="hk">Status Code</td><td class="hv" style="color:' + (((req.status||0)>=200&&(req.status||0)<300) ? '#4ec9b0' : '#f48771') + '">' + (req.status || 'pending') + (req.is_error ? ' (Error)' : '') + '</td></tr>' +
        '<tr><td class="hk">Timestamp</td><td class="hv">' + (req.timestamp || '-') + '</td></tr>' +
        '<tr><td class="hk">Device</td><td class="hv">' + escapeHtml(req.device || '-') + '</td></tr>' +
        (req.time_ms ? '<tr><td class="hk">Duration</td><td class="hv">' + formatTime(req.time_ms) + '</td></tr>' : '') +
        (req.size ? '<tr><td class="hk">Response Size</td><td class="hv">' + formatSize(req.size) + '</td></tr>' : '') +
        '</table>';

    const reqTable = document.getElementById('reqHeadersTable');
    const reqHeaders = req.request_headers || {};
    const reqKeys = Object.keys(reqHeaders);
    document.getElementById('reqHeaderCount').textContent = reqKeys.length ? '(' + reqKeys.length + ')' : '';

    if (reqKeys.length) {
        reqTable.innerHTML = reqKeys.map(k =>
            '<tr><td class="hk">' + escapeHtml(k) + '</td><td class="hv">' + escapeHtml(String(reqHeaders[k])) + '</td></tr>'
        ).join('');
    } else {
        reqTable.innerHTML = '<tr><td style="color:#555">No headers captured</td></tr>';
    }

    const respSection = document.getElementById('respHeadersSection');
    const respTable = document.getElementById('respHeadersTable');
    const respHeaders = req.response_headers || {};
    const respKeys = Object.keys(respHeaders);
    document.getElementById('respHeaderCount').textContent = respKeys.length ? '(' + respKeys.length + ')' : '';

    if (respKeys.length) {
        respSection.style.display = '';
        respTable.innerHTML = respKeys.map(k =>
            '<tr><td class="hk">' + escapeHtml(k) + '</td><td class="hv">' + escapeHtml(String(respHeaders[k])) + '</td></tr>'
        ).join('');
    } else {
        respSection.style.display = 'none';
    }
}

// ----- Payload Tab -----
function renderPayloadTab(req) {
    const qpDiv = document.getElementById('queryParams');
    const url = req.full_url || '';
    const qIdx = url.indexOf('?');
    if (qIdx >= 0) {
        const params = new URLSearchParams(url.slice(qIdx));
        const entries = [...params.entries()];
        if (entries.length) {
            qpDiv.innerHTML = '<table class="headers-table">' +
                entries.map(([k, v]) => '<tr><td class="hk">' + escapeHtml(k) + '</td><td class="hv">' + escapeHtml(v) + '</td></tr>').join('') +
                '</table>';
        } else {
            qpDiv.innerHTML = '<span style="color:#555">No query parameters</span>';
        }
    } else {
        qpDiv.innerHTML = '<span style="color:#555">No query parameters</span>';
    }

    const bodyDiv = document.getElementById('requestBody');
    const reqData = req.request_data;
    if (reqData && Object.keys(reqData).length > 0) {
        bodyDiv.innerHTML = buildJsonTree(reqData, null);
    } else {
        bodyDiv.innerHTML = '<span style="color:#555">No request body</span>';
    }
}

// ----- Preview Tab (Collapsible JSON Tree) -----
function renderPreviewTab(req) {
    const div = document.getElementById('responsePreview');

    if (req.is_error && req.response_body) {
        div.innerHTML = '<div style="color:#f48771;margin-bottom:8px">&#9888; Request Error</div><div style="color:#ccc">' + escapeHtml(typeof req.response_body === 'string' ? req.response_body : JSON.stringify(req.response_body)) + '</div>';
        return;
    }

    // 获取响应数据，尝试解析为 JSON 对象
    let body = req.response_body;

    // 如果 response_body 是字符串，尝试解析为 JSON
    if (typeof body === 'string') {
        const trimmed = body.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                body = JSON.parse(trimmed);
            } catch (e) {
                // 解析失败，保持原字符串
            }
        }
    }

    // 如果 response_body 仍为空，尝试使用 response_raw
    if (!body && req.response_raw) {
        const raw = req.response_raw.trim();
        if (raw.startsWith('{') || raw.startsWith('[')) {
            try {
                body = JSON.parse(raw);
            } catch (e) {
                // 解析失败
            }
        }
        if (!body) {
            body = req.response_raw;
        }
    }

    if (!body || (typeof body === 'object' && Object.keys(body).length === 0 && !Array.isArray(body))) {
        div.innerHTML = '<span style="color:#555">No response data' + (!req.status ? ' (pending...)' : '') + '</span>';
        return;
    }

    // 如果是字符串（非 JSON），直接显示
    if (typeof body === 'string') {
        div.innerHTML = '<div class="raw-view">' + escapeHtml(body) + '</div>';
        return;
    }

    // 可折叠 JSON 树（根节点不显示 key）
    div.innerHTML = buildJsonTree(body, null);
}

// ----- Raw Tab -----
function renderRawTab(req) {
    const div = document.getElementById('responseRaw');

    let raw = req.response_raw || '';
    if (!raw) {
        if (req.response_body) {
            raw = typeof req.response_body === 'object'
                ? JSON.stringify(req.response_body, null, 2)
                : String(req.response_body);
        }
    }

    if (!raw) {
        div.innerHTML = '<span style="color:#555">No raw data available</span>';
        return;
    }

    div.textContent = raw;
}

// ----- Timing Tab -----
function renderTimingTab(req) {
    const div = document.getElementById('timingContent');
    const ms = req.time_ms || 0;

    if (!ms) {
        div.innerHTML = '<span style="color:#555">No timing data available' + (!req.status ? ' (request still pending...)' : '') + '</span>';
        return;
    }

    const timing = req.timing || {};
    if (timing.ttfb) {
        const total = timing.ttfb + (timing.download || 0);
        const ttfbPct = (timing.ttfb / total * 100).toFixed(0);
        const dlPct = ((timing.download || 0) / total * 100).toFixed(0);

        div.innerHTML =
            '<div class="timing-item"><span class="timing-label">TTFB</span><div class="timing-bar-wrap"><div class="timing-bar bar-ttfb" style="width:' + ttfbPct + '%"></div></div><span class="timing-val">' + formatTime(timing.ttfb) + '</span></div>' +
            '<div class="timing-item"><span class="timing-label">Download</span><div class="timing-bar-wrap"><div class="timing-bar bar-download" style="width:' + dlPct + '%"></div></div><span class="timing-val">' + formatTime(timing.download || 0) + '</span></div>' +
            '<div class="timing-item" style="border-top:1px solid #333;padding-top:6px;margin-top:6px"><span class="timing-label" style="font-weight:bold">Total</span><div class="timing-bar-wrap"><div class="timing-bar" style="width:100%;background:#4ec9b0"></div></div><span class="timing-val" style="font-weight:bold">' + formatTime(total) + '</span></div>';
    } else {
        div.innerHTML =
            '<div class="timing-item"><span class="timing-label">Total</span><div class="timing-bar-wrap"><div class="timing-bar" style="width:100%;background:#4ec9b0"></div></div><span class="timing-val" style="font-weight:bold">' + formatTime(ms) + '</span></div>';
    }
}

// ==================== Event Handlers ====================
function initEvents() {
    // Filter pills
    document.querySelectorAll('.pill[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.pill[data-filter]').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            state.filter = btn.dataset.filter;
            applyFilter();
            requestAnimationFrame(updateVirtualScroll);
        });
    });

    // Search input (debounced, with IME composition support)
    let searchTimer = null;
    let isComposing = false;
    const searchInput = document.getElementById('searchInput');

    searchInput.addEventListener('compositionstart', function() {
        isComposing = true;
        clearTimeout(searchTimer);
    });
    searchInput.addEventListener('compositionend', function(e) {
        isComposing = false;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function() {
            doSearch(e.target.value.trim());
        }, 50);
    });
    searchInput.addEventListener('input', function(e) {
        if (isComposing) return;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function() {
            doSearch(e.target.value.trim());
        }, 300);
    });

    function doSearch(term) {
        state.search = term;
        applyFilter();
        requestAnimationFrame(updateVirtualScroll);
        if (state.selectedId) {
            const req = state.requests.find(function(r) { return r.id === state.selectedId; });
            if (req) {
                const tab = state.activeTab;
                if (tab === 'preview') highlightJsonTree(document.getElementById('responsePreview'), term);
                else if (tab === 'payload') highlightJsonTree(document.getElementById('requestBody'), term);
            }
        }
    }

    document.getElementById('matchPrev').addEventListener('click', function() { navigateMatch(-1); });
    document.getElementById('matchNext').addEventListener('click', function() { navigateMatch(1); });

    // Tab switching
    document.querySelectorAll('.tab[data-tab]').forEach(function(tab) {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.tab[data-tab]').forEach(function(t) { t.classList.remove('active'); });
            tab.classList.add('active');
            state.activeTab = tab.dataset.tab;

            document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.add('hidden'); });
            const target = document.getElementById('tab' + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1));
            if (target) target.classList.remove('hidden');

            if (state.selectedId) {
                const req = state.requests.find(function(r) { return r.id === state.selectedId; });
                if (req) {
                    renderDetail(req);
                    if (state.search) {
                        if (tab.dataset.tab === 'preview') highlightJsonTree(document.getElementById('responsePreview'), state.search);
                        else if (tab.dataset.tab === 'payload') highlightJsonTree(document.getElementById('requestBody'), state.search);
                    }
                }
            }
        });
    });

    // Clear button
    document.getElementById('btnClear').addEventListener('click', function() {
        if (!confirm('确定要清空所有抓包记录吗？')) return;
        state.requests = [];
        state.filtered = [];
        state.selectedId = null;
        state.lastId = null;
        // 重置布局状态
        if (state.detailExpanded) {
            state.detailExpanded = false;
            document.getElementById('detailPanel').classList.remove('expanded');
            document.getElementById('btnExpandDetail').classList.remove('active');
        }
        document.getElementById('detailPanel').classList.add('hidden');
        document.getElementById('dragHandle').style.display = state.layoutMode === 'horizontal' ? '' : 'none';
        document.getElementById('requestList').style.display = '';
        document.getElementById('requestList').classList.remove('full-width');
        fetch('/api/clear').catch(function() {});
        requestAnimationFrame(updateVirtualScroll);
        updateStats({total: 0, by_status: {}});
    });

    // Record toggle
    document.getElementById('btnRecord').addEventListener('click', function() {
        state.recording = !state.recording;
        const btn = document.getElementById('btnRecord');
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        if (state.recording) {
            btn.classList.add('active');
            dot.className = 'footer-dot live';
            text.textContent = '正在录制';
        } else {
            btn.classList.remove('active');
            dot.className = 'footer-dot off';
            text.textContent = '已暂停';
        }
    });

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (document.activeElement === searchInput && state.search) {
                searchInput.value = '';
                doSearch('');
                searchInput.blur();
                return;
            }
            // 全屏模式先收起
            if (state.detailExpanded) {
                document.getElementById('btnExpandDetail').click();
                return;
            }
            state.selectedId = null;
            document.getElementById('detailPanel').classList.add('hidden');
            document.getElementById('dragHandle').style.display = state.layoutMode === 'horizontal' ? '' : 'none';
            requestAnimationFrame(updateVirtualScroll);
        }
        if ((e.ctrlKey && e.key === 'f') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
        if (e.key === 'Enter' && document.activeElement === searchInput) {
            e.preventDefault();
            navigateMatch(e.shiftKey ? -1 : 1);
        }
    });
}

// ==================== Layout: Drag Handle + Toggle + Expand ====================

(function() {
    const handle = document.getElementById('dragHandle');
    const reqList = document.getElementById('requestList');
    const detailPanel = document.getElementById('detailPanel');
    const mainBody = document.getElementById('mainBody');
    const btnLayout = document.getElementById('btnLayoutToggle');
    const btnExpand = document.getElementById('btnExpandDetail');

    let isDragging = false;
    let startX = 0;
    let startWidth = 0;

    // --- Drag to resize ---
    handle.addEventListener('mousedown', function(e) {
        if (state.layoutMode !== 'horizontal') return;
        isDragging = true;
        startX = e.clientX;
        startWidth = reqList.offsetWidth;
        handle.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        const dx = e.clientX - startX;
        const newWidth = Math.max(280, Math.min(startWidth + dx, window.innerWidth - 320));
        reqList.style.flex = 'none';
        reqList.style.width = newWidth + 'px';
        requestAnimationFrame(updateVirtualScroll);
    });

    document.addEventListener('mouseup', function() {
        if (!isDragging) return;
        isDragging = false;
        handle.classList.remove('active');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        requestAnimationFrame(updateVirtualScroll);
    });

    // --- Toggle layout: horizontal ↔ vertical ---
    btnLayout.addEventListener('click', function() {
        if (state.detailExpanded) return;  // 全屏时禁止切换布局
        if (state.layoutMode === 'horizontal') {
            // 切换到上下布局
            state.layoutMode = 'vertical';
            state.savedLeftWidth = reqList.style.width || '45%';
            mainBody.style.flexDirection = 'column';
            reqList.style.width = '';
            reqList.style.flex = '1';
            reqList.style.minHeight = '180px';
            reqList.style.maxHeight = '50vh';
            handle.style.display = 'none';
            btnLayout.classList.remove('active');
            btnLayout.title = '切换为左右布局';
        } else {
            // 切换到左右布局
            state.layoutMode = 'horizontal';
            mainBody.style.flexDirection = 'row';
            reqList.style.maxHeight = '';
            reqList.style.minHeight = '';
            if (state.savedLeftWidth) {
                reqList.style.flex = 'none';
                reqList.style.width = state.savedLeftWidth;
            }
            handle.style.display = '';
            btnLayout.classList.add('active');
            btnLayout.title = '切换为上下布局';
        }
        requestAnimationFrame(updateVirtualScroll);
    });

    // --- Expand / Collapse detail panel ---
    btnExpand.addEventListener('click', function() {
        if (!state.selectedId) return;
        state.detailExpanded = !state.detailExpanded;
        if (state.detailExpanded) {
            // 全屏展开：隐藏请求列表和手柄，详情占满
            reqList.classList.add('full-width');
            reqList.style.display = 'none';
            handle.style.display = 'none';
            detailPanel.classList.add('expanded');
            btnExpand.classList.add('active');
        } else {
            // 恢复分栏
            reqList.classList.remove('full-width');
            reqList.style.display = '';
            handle.style.display = state.layoutMode === 'horizontal' ? '' : 'none';
            detailPanel.classList.remove('expanded');
            btnExpand.classList.remove('active');
        }
        requestAnimationFrame(updateVirtualScroll);
    });
})();

// ==================== Init ====================
function init() {
    initEvents();
    setInterval(fetchLogs, 2000);
    fetchLogs();
}

init();
</script>
</body>
</html>'''

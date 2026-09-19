# DB Query Tool HTML 模板 — 数据库专用暗色主题

DBTOOLS_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DB Query Tool — supervisions</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
    --bg:#0d1117;
    --sidebar-bg:#161b22;
    --header-bg:#010409;
    --border:#30363d;
    --text:#c9d1d9;
    --text-dim:#8b949e;
    --accent:#58a6ff;
    --accent-green:#3fb950;
    --accent-orange:#d29922;
    --accent-red:#f85149;
    --accent-purple:#bc8cff;
    --table-header:#1f2937;
    --table-row-alt:#0d1117;
    --table-row:#161b22;
    --code-bg:#1c2128;
    --btn-primary:#238636;
    --btn-primary-hover:#2ea043;
}
html,body{height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;font-size:13px;background:var(--bg);color:var(--text)}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#484f58}

/* Layout */
.app{display:flex;flex-direction:column;height:100vh}

/* Header */
.header{display:flex;align-items:center;padding:0 16px;height:48px;background:var(--header-bg);border-bottom:1px solid var(--border);flex-shrink:0;gap:12px}
.logo{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600;color:var(--text)}
.logo-icon{width:24px;height:24px;background:linear-gradient(135deg,#58a6ff,#3fb950);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff}
.logo-db{color:var(--accent);font-weight:700}
.logo-name{color:var(--text-dim);font-weight:400;font-size:12px;margin-left:4px}
.header-right{display:flex;align-items:center;gap:8px;margin-left:auto}
.db-badge{padding:3px 8px;background:#1f6feb22;border:1px solid #1f6feb44;border-radius:12px;font-size:11px;color:var(--accent)}

/* Buttons */
.btn{display:inline-flex;align-items:center;gap:4px;padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--text-dim);font-size:12px;cursor:pointer;transition:all .15s;font-family:inherit}
.btn:hover{background:var(--sidebar-bg);color:var(--text);border-color:var(--text-dim)}
.btn-primary{background:var(--btn-primary);border-color:var(--btn-primary);color:#fff;font-weight:600}
.btn-primary:hover{background:var(--btn-primary-hover);border-color:var(--btn-primary-hover)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed}
.btn-outline{border-color:var(--border)}
.btn-sm{padding:4px 10px;font-size:11px}
.btn-icon{padding:6px 8px}

/* Main */
.main{display:flex;flex:1;overflow:hidden}

/* Sidebar */
.sidebar{width:280px;background:var(--sidebar-bg);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;overflow:hidden;transition:width .2s}
.sidebar.collapsed{width:0;border:none}
.sidebar-header{display:flex;align-items:center;padding:12px 16px 8px;font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px;gap:6px}
.sidebar-header .icon{font-size:14px}
.sidebar-content{flex:1;overflow-y:auto;padding-bottom:8px}
.sidebar-section{margin-bottom:4px}

/* Table list */
.table-item{display:flex;align-items:center;justify-content:space-between;padding:6px 16px;font-size:12px;color:var(--text-dim);cursor:pointer;transition:all .1s}
.table-item:hover{background:#1c2128;color:var(--text)}
.table-item .tbl-icon{color:var(--accent);font-size:11px;margin-right:8px;width:14px;text-align:center}
.table-item .tbl-name{flex:1;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}
.table-item .tbl-rows{font-size:10px;color:#484f58;background:#21262d;padding:1px 6px;border-radius:10px}

/* Catalog */
.catalog-group{padding:8px 16px 4px;font-size:10px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.5px}
.catalog-item{display:block;padding:5px 16px 5px 24px;font-size:12px;color:var(--text-dim);cursor:pointer;transition:all .1s;text-decoration:none;border-left:2px solid transparent}
.catalog-item:hover{background:#1c2128;color:var(--text);border-left-color:var(--accent)}
.catalog-item.active{background:#1c2128;color:var(--accent);border-left-color:var(--accent)}

/* History */
.history-item{padding:5px 16px 5px 24px;font-size:11px;color:#484f58;cursor:pointer;font-family:'SFMono-Regular',Consolas,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:all .1s}
.history-item:hover{background:#1c2128;color:var(--text-dim)}

/* Editor area */
.editor-area{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}

/* SQL editor */
.editor-panel{border-bottom:none;flex-shrink:0;position:relative}
.editor-toolbar{display:flex;align-items:center;padding:6px 12px;background:var(--sidebar-bg);border-bottom:1px solid var(--border);gap:6px;min-height:36px}
.editor-toolbar .hint{font-size:11px;color:var(--text-dim);margin-left:auto}
.editor-toolbar kbd{background:#21262d;border:1px solid var(--border);border-radius:3px;padding:1px 5px;font-size:10px;font-family:inherit;color:var(--text-dim)}
.sql-editor{width:100%;min-height:80px;height:120px;background:var(--code-bg);color:var(--text);border:none;padding:12px 16px;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:13px;line-height:1.6;resize:none;outline:none;tab-size:2;display:block}
.sql-editor:focus{box-shadow:inset 0 0 0 1px var(--accent)}
.sql-editor::placeholder{color:#484f58}

/* Resize handle between editor and results */
.resize-handle{height:6px;background:var(--border);cursor:ns-resize;flex-shrink:0;position:relative;transition:background .15s}
.resize-handle:hover,.resize-handle.active{background:var(--accent)}
.resize-handle::after{content:'';position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:40px;height:2px;background:var(--text-dim);border-radius:1px}
.resize-handle:hover::after{background:var(--accent)}

/* Results */
.results-panel{flex:1;overflow:auto;position:relative}
.results-table-wrap{overflow:auto;height:100%}
.results-table{width:max-content;min-width:100%;border-collapse:collapse;font-size:12px;font-family:'SFMono-Regular',Consolas,monospace}
.results-table th{position:sticky;top:0;background:var(--table-header);color:var(--accent);font-weight:600;padding:8px 12px;text-align:left;border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap;font-size:11px;letter-spacing:.3px}
.results-table th:hover{background:#262f3a}
.results-table th .sort-arrow{margin-left:4px;font-size:10px;opacity:.5}
.results-table td{padding:6px 12px;border-bottom:1px solid #21262d;vertical-align:top;white-space:nowrap}
.results-table tbody tr:nth-child(even) td{background:var(--table-row-alt)}
.results-table tbody tr:nth-child(odd) td{background:var(--table-row)}
.results-table tbody tr:hover td{background:#1f2937}
.cell-null{color:#484f58;font-style:italic}
.cell-num{color:var(--accent-orange);font-weight:500}
.cell-str{color:var(--text)}
.cell-copy{cursor:pointer;position:relative}
.cell-copy:hover{background:#262f3a !important;border-radius:3px}

/* Status bar */
.status-bar{display:flex;align-items:center;padding:0 16px;height:28px;background:var(--accent);color:#fff;font-size:11px;gap:16px;flex-shrink:0}
.status-item{display:flex;align-items:center;gap:4px}
.status-dot{width:6px;height:6px;border-radius:50%;background:#fff}
.status-dot.ok{background:#7ee787}
.status-dot.err{background:#f85149}
.status-dot.loading{background:#d29922;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.status-right{margin-left:auto;display:flex;gap:12px;align-items:center}

/* Empty & Error */
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text-dim);gap:8px}
.empty-state .empty-icon{font-size:48px;opacity:.3;margin-bottom:8px}
.empty-state h3{font-size:16px;font-weight:500;color:var(--text)}
.empty-state p{font-size:13px;color:var(--text-dim)}
.error-box{margin:16px;padding:12px 16px;background:#f8514922;border:1px solid #f8514944;border-radius:6px;color:var(--accent-red);font-size:13px;display:flex;align-items:center;gap:8px}

/* Toast */
.toast{position:fixed;bottom:40px;right:20px;padding:10px 20px;border-radius:8px;background:var(--sidebar-bg);color:var(--accent-green);font-size:13px;z-index:9999;opacity:0;transform:translateY(10px);transition:all .3s;pointer-events:none;border:1px solid var(--accent-green)}
.toast.show{opacity:1;transform:translateY(0)}
.toast.err{color:var(--accent-red);border-color:var(--accent-red)}

/* Schema modal */
.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:100;display:none;align-items:center;justify-content:center;backdrop-filter:blur(2px)}
.modal-overlay.show{display:flex}
.modal-box{background:var(--sidebar-bg);border:1px solid var(--border);border-radius:10px;width:80%;max-width:800px;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 16px 48px rgba(0,0,0,.4)}
.modal-header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.modal-header h3{color:var(--accent);font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px}
.modal-close{background:none;border:none;color:var(--text-dim);font-size:20px;cursor:pointer;padding:4px 8px;border-radius:4px}
.modal-close:hover{background:#21262d;color:var(--text)}
.modal-body{overflow:auto;padding:12px}
.schema-table{width:100%;border-collapse:collapse;font-size:12px}
.schema-table th{background:var(--table-header);color:var(--accent);padding:6px 12px;text-align:left;font-weight:600;position:sticky;top:0;font-size:11px}
.schema-table td{padding:5px 12px;border-bottom:1px solid #21262d;color:var(--text-dim)}
.schema-table .col-pri{color:var(--accent-orange);font-family:'SFMono-Regular',Consolas,monospace;font-weight:600}
.schema-table .col-type{color:var(--accent-purple);font-family:'SFMono-Regular',Consolas,monospace}
.schema-table td:last-child{color:var(--text);white-space:normal;max-width:300px}

/* Quick actions bar */
.quick-bar{display:flex;gap:6px;padding:8px 16px;background:var(--sidebar-bg);border-bottom:1px solid var(--border);flex-wrap:wrap;align-items:center}
.quick-bar .label{font-size:11px;color:var(--text-dim);margin-right:4px}
.quick-tag{padding:3px 10px;font-size:11px;background:#21262d;border:1px solid var(--border);border-radius:12px;color:var(--accent);cursor:pointer;transition:all .15s}
.quick-tag:hover{background:#262f3a;border-color:var(--accent)}
.quick-tag .tag-id{color:var(--text-dim);margin-right:4px}

/* Responsive */
@media(max-width:900px){
    .sidebar{position:absolute;left:0;top:48px;bottom:28px;z-index:50;box-shadow:4px 0 24px rgba(0,0,0,.5)}
    .sidebar.collapsed{width:0}
}
</style>
</head>
<body>
<div class="app">
    <!-- Header -->
    <div class="header">
        <div class="logo">
            <div class="logo-icon">DB</div>
            <span class="logo-db">Query Tool</span>
            <span class="logo-name">supervisions</span>
        </div>
        <div class="header-right">
            <span class="db-badge">MySQL 8.0</span>
            <button class="btn btn-primary" id="btnRun" onclick="runQuery()">
                <span id="runIcon">&#9654;</span> <span id="runText">执行</span>
            </button>
            <button class="btn btn-outline" onclick="exportCSV()" id="btnCsv">
                &#8681; CSV
            </button>
            <button class="btn btn-outline btn-icon" onclick="toggleSidebar()" title="切换侧栏" id="btnToggle">
                &#9776;
            </button>
        </div>
    </div>

    <!-- Main -->
    <div class="main">
        <!-- Sidebar -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-content">
                <!-- Catalog (常用查询) on top -->
                <div class="sidebar-section">
                    <div class="sidebar-header"><span class="icon">&#128214;</span> 常用查询</div>
                    <div id="catalogList"></div>
                </div>
                <!-- Tables below -->
                <div class="sidebar-section">
                    <div class="sidebar-header"><span class="icon">&#128451;</span> 数据表</div>
                    <div id="tableList"></div>
                </div>
                <!-- History -->
                <div class="sidebar-section">
                    <div class="sidebar-header"><span class="icon">&#128339;</span> 查询历史</div>
                    <div id="historyList">
                        <div style="padding:8px 16px;color:#484f58;font-size:11px">暂无历史</div>
                    </div>
                </div>
            </div>
            <!-- Quick user bar -->
            <div class="quick-bar" id="quickBar">
                <span class="label">&#128100; 测试用户:</span>
            </div>
        </div>

        <!-- Editor + Results -->
        <div class="editor-area">
            <!-- Editor -->
            <div class="editor-panel">
                <div class="editor-toolbar">
                    <span style="font-size:11px;color:var(--text-dim)">SQL</span>
                    <span class="hint">
                        <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 执行 &nbsp;
                        <kbd>Ctrl</kbd>+<kbd>L</kbd> 清空
                    </span>
                </div>
                <textarea class="sql-editor" id="sqlEditor"
                    placeholder="输入 SQL 查询...&#10;&#10;例如: SELECT * FROM video_coupon_record WHERE id = 381"
                    spellcheck="false"></textarea>
            </div>
            <!-- Resize handle -->
            <div class="resize-handle" id="resizeHandle"></div>
            <!-- Results -->
            <div class="results-panel" id="resultsArea">
                <div class="empty-state" id="emptyState">
                    <div class="empty-icon">&#128269;</div>
                    <h3>输入 SQL 并执行查询</h3>
                    <p>支持 SELECT / SHOW / DESCRIBE 语句</p>
                    <p style="margin-top:12px;color:#484f58">点击左侧「常用查询」快速填充</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Status bar -->
    <div class="status-bar">
        <div class="status-item"><span class="status-dot" id="statusDot"></span><span id="statusText">就绪</span></div>
        <div class="status-item" id="statusRows"></div>
        <div class="status-item" id="statusTime"></div>
        <div class="status-right">
            <span>supervisions @ 121.40.243.17</span>
        </div>
    </div>
</div>

<!-- Schema modal -->
<div class="modal-overlay" id="schemaOverlay" onclick="closeSchema(event)">
    <div class="modal-box">
        <div class="modal-header">
            <h3 id="schemaTitle">&#128203; 表结构</h3>
            <button class="modal-close" onclick="closeSchema()">&times;</button>
        </div>
        <div class="modal-body" id="schemaBody"></div>
    </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ==================== State ====================
const state = {
    tables: [],
    history: JSON.parse(localStorage.getItem('dbtools_history') || '[]'),
    lastResult: null,
    sidebarVisible: true,
    catalog: [],
};

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', function() {
    loadTables();
    loadCatalog();
    loadQuickUsers();
    setupEditor();
    renderHistory();
});

// ==================== Tables ====================
async function loadTables() {
    try {
        const resp = await fetch('/api/tables');
        const data = await resp.json();
        state.tables = data.tables || [];
        renderTables();
    } catch(e) {
        console.error('加载表列表失败:', e);
    }
}

function renderTables() {
    const el = document.getElementById('tableList');
    if (!state.tables.length) {
        el.innerHTML = '<div style="padding:8px 16px;color:#484f58;font-size:11px">加载失败</div>';
        return;
    }
    el.innerHTML = state.tables.map(function(t) {
        return '<div class="table-item" data-table="' + escAttr(t.name) + '" onclick="showSchema(\'' + escAttr(t.name) + '\')">' +
            '<span class="tbl-icon">&#9642;</span>' +
            '<span class="tbl-name">' + escHtml(t.name) + '</span>' +
            '<span class="tbl-rows">' + fmtNum(t.rows) + '</span>' +
        '</div>';
    }).join('');
}

// ==================== Schema modal ====================
// Column mapping: SHOW FULL COLUMNS returns [Field, Type, Collation, Null, Key, Default, Extra, Privileges, Comment]
// We only show: 字段名(Field), 类型(Type), 键(Key), 注释(Comment)
var SCHEMA_COLS = [
    {idx: 0, label: '字段名'},
    {idx: 1, label: '类型'},
    {idx: 4, label: '键'},
    {idx: 8, label: '注释'},
];

async function showSchema(tableName) {
    var overlay = document.getElementById('schemaOverlay');
    var title = document.getElementById('schemaTitle');
    var body = document.getElementById('schemaBody');
    title.innerHTML = '&#128203; ' + escHtml(tableName) + ' — 表结构';
    body.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-dim)">加载中...</div>';
    overlay.classList.add('show');

    try {
        var resp = await fetch('/api/schema/' + encodeURIComponent(tableName));
        var data = await resp.json();
        if (data.error) {
            body.innerHTML = '<div class="error-box">' + escHtml(data.error) + '</div>';
            return;
        }
        var cols = data.columns || [];
        var rows = data.rows || [];
        var html = '<table class="schema-table"><thead><tr>';
        SCHEMA_COLS.forEach(function(sc) { html += '<th>' + sc.label + '</th>'; });
        html += '</tr></thead><tbody>';
        rows.forEach(function(r) {
            html += '<tr>';
            SCHEMA_COLS.forEach(function(sc) {
                var v = r[sc.idx];
                var display = v === null || v === undefined ? '' : String(v);
                var cls = '';
                if (sc.idx === 0) cls = 'col-pri';
                else if (sc.idx === 1) cls = 'col-type';
                else if (sc.idx === 8 && !display) cls = 'cell-null';
                // Key column: highlight PRI/MUL
                if (sc.idx === 4) {
                    if (display === 'PRI') cls = 'col-pri';
                    else if (display === 'MUL') cls = 'col-type';
                }
                html += '<td class="' + cls + '">' + escHtml(display) + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        body.innerHTML = html;
    } catch(e) {
        body.innerHTML = '<div class="error-box">加载失败: ' + escHtml(e.message) + '</div>';
    }
}

function closeSchema(e) {
    if (e && e.target !== document.getElementById('schemaOverlay')) return;
    document.getElementById('schemaOverlay').classList.remove('show');
}

// ==================== Catalog ====================
async function loadCatalog() {
    try {
        var resp = await fetch('/api/catalog');
        var data = await resp.json();
        state.catalog = data.catalog || [];
        renderCatalog(state.catalog);
    } catch(e) {
        console.error('加载查询模板失败:', e);
    }
}

function renderCatalog(catalog) {
    var el = document.getElementById('catalogList');
    var html = '';
    catalog.forEach(function(group) {
        html += '<div class="catalog-group">' + escHtml(group.group) + '</div>';
        group.items.forEach(function(item) {
            // 使用 data-sql 属性存储 SQL，onclick 通过 JS 读取，避免引号转义问题
            var safeSql = item.sql.replace(/\\/g, '\\\\').replace(/"/g, '&quot;');
            html += '<div class="catalog-item" data-sql="' + safeSql + '" onclick="fillFromCatalog(this)" title="' + escHtml(item.name) + '">' +
                escHtml(item.name) + '</div>';
        });
    });
    el.innerHTML = html;
}

function fillFromCatalog(el) {
    // 清除之前的 active
    document.querySelectorAll('.catalog-item.active').forEach(function(n) { n.classList.remove('active'); });
    el.classList.add('active');
    var sql = el.getAttribute('data-sql')
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>');
    document.getElementById('sqlEditor').value = sql;
    document.getElementById('sqlEditor').focus();
}

// ==================== Quick user bar ====================
function loadQuickUsers() {
    var users = [
        {name: 'ice', id: 'aff7eae4-3680-4b89-9f01-819e02c3b6b5'},
        {name: 'Natural', id: '57d703dc-659a-4474-898e-b75efa1f2e0a'},
        {name: '用户C', id: '7c37a4a2-d11a-4ac8-83c6-b7c293b6c1f4'},
    ];
    var bar = document.getElementById('quickBar');
    users.forEach(function(u) {
        var tag = document.createElement('span');
        tag.className = 'quick-tag';
        tag.innerHTML = '<span class="tag-id">' + escHtml(u.name) + '</span>' + escHtml(u.id.substring(0, 8)) + '...';
        tag.title = u.id;
        tag.onclick = function() { copyText(u.id, u.name + ' ID'); };
        bar.appendChild(tag);
    });
}

// ==================== Editor ====================
function setupEditor() {
    var editor = document.getElementById('sqlEditor');
    editor.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            runQuery();
        }
        if (e.ctrlKey && e.key === 'l') {
            e.preventDefault();
            editor.value = '';
            editor.focus();
        }
    });
    editor.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            var start = editor.selectionStart;
            var end = editor.selectionEnd;
            editor.value = editor.value.substring(0, start) + '  ' + editor.value.substring(end);
            editor.selectionStart = editor.selectionEnd = start + 2;
        }
    });

    // Resize handle drag
    var handle = document.getElementById('resizeHandle');
    var editorPanel = handle.previousElementSibling; // .editor-panel
    var dragging = false;
    var startY = 0;
    var startH = 0;

    handle.addEventListener('mousedown', function(e) {
        e.preventDefault();
        dragging = true;
        startY = e.clientY;
        startH = editorPanel.offsetHeight;
        handle.classList.add('active');
        document.body.style.cursor = 'ns-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        var diff = e.clientY - startY;
        var newH = Math.max(80, startH + diff);
        editorPanel.style.height = newH + 'px';
    });

    document.addEventListener('mouseup', function() {
        if (dragging) {
            dragging = false;
            handle.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

function fillQuery(sql) {
    document.getElementById('sqlEditor').value = sql;
    document.getElementById('sqlEditor').focus();
}

// ==================== Query ====================
async function runQuery() {
    var editor = document.getElementById('sqlEditor');
    var sql = editor.value.trim();
    if (!sql) { showToast('&#9888;&#65039; 请输入 SQL', true); return; }

    var btn = document.getElementById('btnRun');
    var icon = document.getElementById('runIcon');
    var text = document.getElementById('runText');
    var dot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');

    btn.disabled = true;
    icon.innerHTML = '&#9203;';
    text.textContent = '执行中';
    dot.className = 'status-dot loading';
    statusText.textContent = '查询中...';
    document.getElementById('statusRows').textContent = '';
    document.getElementById('statusTime').textContent = '';

    try {
        var resp = await fetch('/api/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sql: sql}),
        });
        var data = await resp.json();
        state.lastResult = {sql: sql, data: data};

        if (data.error) {
            renderError(data.error);
            dot.className = 'status-dot err';
            statusText.textContent = '错误';
        } else {
            renderResults(data);
            dot.className = 'status-dot ok';
            statusText.textContent = '查询成功';
            document.getElementById('statusRows').textContent = data.count + ' 行';
            document.getElementById('statusTime').textContent = data.time_ms + ' ms';
        }
        addHistory(sql);
    } catch(e) {
        renderError('请求失败: ' + e.message);
        dot.className = 'status-dot err';
        statusText.textContent = '连接错误';
    } finally {
        btn.disabled = false;
        icon.innerHTML = '&#9654;';
        text.textContent = '执行';
    }
}

function renderResults(data) {
    var area = document.getElementById('resultsArea');
    var empty = document.getElementById('emptyState');
    if (empty) empty.style.display = 'none';

    if (!data.columns || data.columns.length === 0) {
        area.innerHTML = '<div class="empty-state"><div class="empty-icon">&#9989;</div><h3>执行成功</h3><p>无返回数据</p></div>';
        return;
    }

    var html = '<div class="results-table-wrap"><table class="results-table" id="resultTable"><thead><tr>';
    data.columns.forEach(function(col, i) {
        html += '<th onclick="sortColumn(' + i + ')" title="点击排序">' + escHtml(col) + '</th>';
    });
    html += '</tr></thead><tbody>';

    data.rows.forEach(function(row) {
        html += '<tr>';
        row.forEach(function(val, i) {
            var isNum = typeof val === 'number';
            var isNull = val === null || val === undefined;
            var cls = isNull ? 'cell-null' : (isNum ? 'cell-num' : 'cell-str');
            var display = isNull ? 'NULL' : String(val);
            html += '<td class="' + cls + ' cell-copy" onclick="copyCell(this)" title="点击复制">' + escHtml(display) + '</td>';
        });
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    area.innerHTML = html;
}

function renderError(msg) {
    var area = document.getElementById('resultsArea');
    area.innerHTML = '<div class="error-box">&#10060; ' + escHtml(msg) + '</div>';
    document.getElementById('statusRows').textContent = '';
    document.getElementById('statusTime').textContent = '';
}

// ==================== Sort ====================
var sortState = {col: -1, asc: true};

function sortColumn(colIdx) {
    if (!state.lastResult || !state.lastResult.data.rows) return;
    var data = state.lastResult.data;

    if (sortState.col === colIdx) {
        sortState.asc = !sortState.asc;
    } else {
        sortState.col = colIdx;
        sortState.asc = true;
    }

    data.rows.sort(function(a, b) {
        var va = a[colIdx], vb = b[colIdx];
        if (va === null && vb === null) return 0;
        if (va === null) return 1;
        if (vb === null) return -1;
        if (typeof va === 'number' && typeof vb === 'number') {
            return sortState.asc ? va - vb : vb - va;
        }
        var sa = String(va), sb = String(vb);
        return sortState.asc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });

    renderResults(data);
}

// ==================== History ====================
function addHistory(sql) {
    state.history = state.history.filter(function(h) { return h !== sql; });
    state.history.unshift(sql);
    if (state.history.length > 20) state.history = state.history.slice(0, 20);
    localStorage.setItem('dbtools_history', JSON.stringify(state.history));
    renderHistory();
}

function renderHistory() {
    var el = document.getElementById('historyList');
    if (state.history.length === 0) {
        el.innerHTML = '<div style="padding:8px 16px;color:#484f58;font-size:11px">暂无历史</div>';
        return;
    }
    el.innerHTML = state.history.map(function(h) {
        var short = h.length > 50 ? h.substring(0, 50) + '...' : h;
        return '<div class="history-item" onclick="fillQuery(' + makeSafeArg(h) + ')" title="' + escHtml(h) + '">' + escHtml(short) + '</div>';
    }).join('');
}

// ==================== CSV ====================
function exportCSV() {
    if (!state.lastResult || !state.lastResult.data.columns || state.lastResult.data.columns.length === 0) {
        showToast('&#9888;&#65039; 无数据可导出', true);
        return;
    }
    var data = state.lastResult.data;
    var csv = '﻿';
    csv += data.columns.map(function(c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(',') + '\n';
    data.rows.forEach(function(row) {
        csv += row.map(function(v) {
            if (v === null || v === undefined) return '';
            return '"' + String(v).replace(/"/g, '""') + '"';
        }).join(',') + '\n';
    });

    var blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'query_' + new Date().toISOString().slice(0, 19).replace(/[:-]/g, '') + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('&#9989; CSV 已导出 (' + data.count + ' 行)');
}

// ==================== Sidebar ====================
function toggleSidebar() {
    state.sidebarVisible = !state.sidebarVisible;
    document.getElementById('sidebar').classList.toggle('collapsed');
}

// ==================== Helpers ====================
function escHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function makeSafeArg(s) {
    return "'" + String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').replace(/\r/g, '\\r') + "'";
}

function fmtNum(n) {
    if (!n && n !== 0) return '';
    if (n >= 10000) return (n / 10000).toFixed(1) + 'w';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
}

function showToast(msg, isErr) {
    var t = document.getElementById('toast');
    t.innerHTML = msg;
    t.className = 'toast show' + (isErr ? ' err' : '');
    setTimeout(function() { t.className = 'toast'; }, 2000);
}

function copyText(text, label) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('&#9989; 已复制 ' + (label || ''));
    }).catch(function() {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); showToast('&#9989; 已复制 ' + (label || '')); }
        catch(e) { showToast('&#10060; 复制失败', true); }
        document.body.removeChild(ta);
    });
}

function copyCell(td) {
    var text = td.textContent;
    if (text === 'NULL') return;
    copyText(text, '单元格');
}
</script>
</body>
</html>'''

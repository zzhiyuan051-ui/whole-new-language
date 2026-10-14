// 洄文输入法 · TSF 文本服务
//
// 这是 Windows 的**系统级**输入法：作为一个 TSF(Text Services Framework) 文本服务
// 注册进语言栏，被任意程序（微信 / Word / 浏览器…）调用，直接往文档里写字。
//
// 工作方式：
//   1. 用户用 Win+Space 选到「洄文输入法」（或按 Ctrl+Shift+H 在本 DLL 内开关）
//   2. 敲字母 → 归一化成音节串 → 在编入二进制的词表里查候选
//   3. 候选显示在自己的小窗里（贴着光标），按 1–9 或空格选中
//   4. 选中的洄文字形通过 ITfInsertAtSelection 写进目标文档
//
// 为什么声调可选：人打字习惯是「连着敲字母、再从候选里挑」，不该被迫记声调；
// 但声调仍可敲 —— 匹配时两边都剥掉数字再比（见 normKey），敲了就更准。

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
// RegDeleteTreeW 等 API 需要 Vista+；不定义会拿不到声明
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif

#include <windows.h>
#include <msctf.h>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdarg>

#include "hwdata.h"

// ------------------------------------------------------------------ GUID
// {7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}
static const CLSID CLSID_HuiwenTextService =
{ 0x7f3a9c10, 0x2b4d, 0x4e6a, { 0x9c, 0x11, 0x8a, 0x2f, 0x0d, 0x55, 0x3e, 0x71 } };

// {7F3A9C11-2B4D-4E6A-9C11-8A2F0D553E72}
static const GUID GUID_HuiwenProfile =
{ 0x7f3a9c11, 0x2b4d, 0x4e6a, { 0x9c, 0x11, 0x8a, 0x2f, 0x0d, 0x55, 0x3e, 0x72 } };

// 用 zh-CN 的 LANGID：让它在语言栏里跟中文输入法排在一起，用户好找。
static const LANGID HUIWEN_LANGID = 0x0804;

static const wchar_t* kServiceDesc = L"洄文输入法";
static const wchar_t* kServiceDescEn = L"Gal Huiwen IME";

// ------------------------------------------------------------------ 全局
static HINSTANCE g_hInst = nullptr;
static LONG      g_cRef = 0;
static ITfThreadMgr* g_pThreadMgr = nullptr;
static TfClientId    g_clientId = 0;

// 输入法开关（Ctrl+Shift+H 切换）。默认为开，方便刚装完就能用。
static bool g_enabled = true;

// ------------------------------------------------------------------ 日志
// 输入法是被**别的进程**加载的，出了事在那边看不见摸不着。
// 所以把关键动作写进一个共享日志文件，事后能查出「到底有没有被调用、
// 键收到了没有、为什么没出候选」。
// 路径：%LOCALAPPDATA%\GalHuiwenIME\ime.log
//
// 两条硬约束（都是踩过的坑）：
//   1. **不要在 DllMain 里调用**。那是加载器锁里，做文件 IO 会让进程
//      以 0xC0000409（栈缓冲区溢出 / __fastfail）直接崩掉 ——
//      实测日志只写下 3 字节的 BOM，DLL 一加载进程就死。
//   2. **不要用 fopen 的 "ccs=UTF-8"**。走 CRT 的编码转换容易出问题；
//      这里改成自己写字节：源码用 /utf-8 编译，所以窄字符串字面量本来就是
//      UTF-8 字节，直接以二进制追加即可。
static void ImeLog(const char* fmt, ...)
{
    char body[1024];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(body, sizeof(body), _TRUNCATE, fmt, ap);
    va_end(ap);

    wchar_t dir[MAX_PATH] = { 0 };
    if (!GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH)) return;
    std::wstring path = dir;
    path += L"\\GalHuiwenIME\\ime.log";

    FILE* f = nullptr;
    if (_wfopen_s(&f, path.c_str(), L"ab") != 0 || !f) return;

    SYSTEMTIME st;
    GetLocalTime(&st);
    char head[64];
    int hn = _snprintf_s(head, sizeof(head), _TRUNCATE,
                         "[%02d:%02d:%02d.%03d pid=%lu] ",
                         st.wHour, st.wMinute, st.wSecond, st.wMilliseconds,
                         (unsigned long)GetCurrentProcessId());
    if (hn > 0) fwrite(head, 1, (size_t)hn, f);
    fwrite(body, 1, strlen(body), f);
    fwrite("\r\n", 1, 2, f);
    fclose(f);
}

// ------------------------------------------------------------------ 工具
// 归一化：只留 a-z，去掉空格与声调数字。
// **必须与 Python 侧 engine.IME.norm 保持一致**，否则两边候选不一致。
static std::wstring normKey(const std::wstring& s)
{
    std::wstring out;
    for (wchar_t c : s)
    {
        if (c >= L'A' && c <= L'Z') out.push_back((wchar_t)(c - L'A' + L'a'));
        else if (c >= L'a' && c <= L'z') out.push_back(c);
    }
    return out;
}

// ------------------------------------------------------------------ 候选窗
// 一个极简的置顶小窗：显示已输入的音节串 + 候选列表。
// 不做自绘，用 STATIC 控件，代码短、够用。
class CCandWindow
{
public:
    CCandWindow() : m_hwnd(nullptr), m_hFont(nullptr) {}

    bool Create(HINSTANCE hInst)
    {
        WNDCLASSEXW wc = { 0 };
        wc.cbSize = sizeof(wc);
        wc.lpfnWndProc = WndProc;
        wc.hInstance = hInst;
        wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
        wc.hbrBackground = (HBRUSH)GetStockObject(WHITE_BRUSH);
        wc.lpszClassName = L"HuiwenCandWnd";
        if (!RegisterClassExW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
            return false;

        m_hFont = CreateFontW(-18, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                              0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei");

        m_hwnd = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
                                 L"HuiwenCandWnd", L"", WS_POPUP | WS_BORDER,
                                 0, 0, 10, 10, nullptr, nullptr, hInst, this);
        if (!m_hwnd) return false;
        SendMessageW(m_hwnd, WM_SETFONT, (WPARAM)m_hFont, TRUE);
        m_label = CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE | SS_LEFT,
                                  6, 4, 10, 20, m_hwnd, nullptr, hInst, nullptr);
        SendMessageW(m_label, WM_SETFONT, (WPARAM)m_hFont, TRUE);
        return true;
    }

    void Destroy()
    {
        if (m_hwnd) { DestroyWindow(m_hwnd); m_hwnd = nullptr; }
        if (m_hFont) { DeleteObject(m_hFont); m_hFont = nullptr; }
    }

    bool IsVisible() const { return m_hwnd && IsWindowVisible(m_hwnd); }

    void Hide() { if (m_hwnd) ShowWindow(m_hwnd, SW_HIDE); }

    // 贴着光标显示
    void Show(const std::wstring& text, HDC /*hdc*/)
    {
        if (!m_hwnd) return;
        SetWindowTextW(m_label, text.c_str());

        HDC hdc = GetDC(m_hwnd);
        SIZE sz = { 0, 0 };
        HFONT old = (HFONT)SelectObject(hdc, m_hFont);
        GetTextExtentPoint32W(hdc, text.c_str(), (int)text.size(), &sz);
        SelectObject(hdc, old);
        ReleaseDC(m_hwnd, hdc);

        int w = sz.cx + 24;
        int h = sz.cy + 16;
        if (w < 160) w = 160;

        POINT pt = CaretPos();
        int sw = GetSystemMetrics(SM_CXSCREEN);
        int sh = GetSystemMetrics(SM_CYSCREEN);
        int x = pt.x + 8, y = pt.y + 24;
        if (x + w > sw) x = sw - w - 4;
        if (y + h > sh) y = pt.y - h - 8;
        if (x < 0) x = 0;
        if (y < 0) y = 0;

        MoveWindow(m_hwnd, x, y, w, h, TRUE);
        MoveWindow(m_label, 8, 6, w - 16, h - 12, TRUE);
        ShowWindow(m_hwnd, SW_SHOWNOACTIVATE);
        SetWindowPos(m_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }

private:
    // 取目标窗口的光标位置。用 GetGUIThreadInfo 而不是 GetCaretPos ——
    // 后者只在当前线程有焦点时有效，而输入法运行时焦点在**别的**线程。
    static POINT CaretPos()
    {
        POINT pt = { 0, 0 };
        GUITHREADINFO gti = { 0 };
        gti.cbSize = sizeof(gti);
        DWORD tid = GetWindowThreadProcessId(GetForegroundWindow(), nullptr);
        if (GetGUIThreadInfo(tid, &gti) && gti.hwndCaret)
        {
            pt.x = gti.rcCaret.left;
            pt.y = gti.rcCaret.bottom;
            POINT p2 = pt;
            if (ClientToScreen(gti.hwndCaret, &p2)) return p2;
        }
        GetCursorPos(&pt);
        return pt;
    }

    static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
    {
        if (msg == WM_ERASEBKGND) return 1;
        return DefWindowProcW(hwnd, msg, wp, lp);
    }

    HWND  m_hwnd;
    HWND  m_label = nullptr;
    HFONT m_hFont;
};

// ------------------------------------------------------------------ 文本服务
class CHuiwenTextService : public ITfTextInputProcessor,
                           public ITfThreadMgrEventSink,
                           public ITfKeyEventSink,
                           public ITfEditSession
{
public:
    CHuiwenTextService() : m_cRef(1), m_tid(0), m_dwSinkCookie(TF_INVALID_COOKIE),
                           m_dwKeyCookie(TF_INVALID_COOKIE) { InterlockedIncrement(&g_cRef); }
    ~CHuiwenTextService() { InterlockedDecrement(&g_cRef); }

    // IUnknown
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override
    {
        if (!ppv) return E_INVALIDARG;
        *ppv = nullptr;
        if (IsEqualIID(riid, IID_IUnknown) ||
            IsEqualIID(riid, IID_ITfTextInputProcessor))
            *ppv = static_cast<ITfTextInputProcessor*>(this);
        else if (IsEqualIID(riid, IID_ITfThreadMgrEventSink))
            *ppv = static_cast<ITfThreadMgrEventSink*>(this);
        else if (IsEqualIID(riid, IID_ITfKeyEventSink))
            *ppv = static_cast<ITfKeyEventSink*>(this);
        else if (IsEqualIID(riid, IID_ITfEditSession))
            *ppv = static_cast<ITfEditSession*>(this);
        else
            return E_NOINTERFACE;
        AddRef();
        return S_OK;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_cRef); }
    STDMETHODIMP_(ULONG) Release() override
    {
        LONG c = InterlockedDecrement(&m_cRef);
        if (c == 0) delete this;
        return c;
    }

    // ITfTextInputProcessor
    STDMETHODIMP Activate(ITfThreadMgr* ptim, TfClientId tid) override
    {
        ImeLog("Activate: 文本服务被加载并激活");
        m_tim = ptim;
        if (m_tim) m_tim->AddRef();      // TSF 传进来的接口，自己持有引用
        m_tid = tid;

        // **不要在这里创建窗口**。
        // 原来这行 `m_cand.Create(g_hInst)` 就在这个位置，结果是
        // AdviseSink(IID_ITfKeyEventSink) 返回 TF_E_NOOBJECT(0x80040202) ——
        // 按键接收器挂不上，敲什么都没反应。
        // 原因：CreateWindowExW 会派发消息，在 TSF 激活过程中重入。
        // 候选窗改成**第一次要用时**再建（见 EnsureCand）。

        // AdviseSink / UnadviseSink 是 ITfSource 的方法，不在 ITfThreadMgr 上。
        // 每一步的 HRESULT 都记下来：按键接收器装不上是**静默**失败。
        HRESULT hs = ptim->QueryInterface(IID_ITfSource, (void**)&m_source);
        ImeLog("  ITfSource = 0x%08X %s", (unsigned)hs,
               SUCCEEDED(hs) ? "OK" : "失败");
        if (SUCCEEDED(hs) && m_source)
        {
            // 先挂线程事件接收器（它决定我们何时收到 OnSetFocus），
            // 再试着挂按键接收器 —— 后者多半会失败(TF_E_NOOBJECT)，
            // 真正的挂载点在 OnSetFocus 里。
            ITfThreadMgrEventSink* pSink = nullptr;
            if (SUCCEEDED(QueryInterface(IID_ITfThreadMgrEventSink, (void**)&pSink)))
            {
                HRESULT h1 = m_source->AdviseSink(IID_ITfThreadMgrEventSink, pSink,
                                                  &m_dwSinkCookie);
                ImeLog("  AdviseSink(ThreadMgr) = 0x%08X cookie=%lu", (unsigned)h1,
                       (unsigned long)m_dwSinkCookie);
                pSink->Release();
            }
            else ImeLog("  QueryInterface(ThreadMgrEventSink) 失败");
            // 不再调用 AdviseSingleSink：那是给「提供 ITfFunctionProvider」用的，
            // 我们不提供任何 function provider，传 nullptr 只会拿到 E_INVALIDARG。

            // 这里也试一次按键接收器。多数情况下会失败（还没焦点），
            // 但有些场景（例如进程启动时已经带着焦点）这里就能成。
            TryAdviseKeySink("Activate");
        }
        ImeLog("Activate 结束");
        return S_OK;
    }

    STDMETHODIMP Deactivate() override
    {
        // 先撤按键接收器 —— 它挂在 ITfKeystrokeMgr 上，不在 ITfSource 上
        if (m_keySinkOn && m_keystrokeMgr)
        {
            m_keystrokeMgr->UnadviseKeyEventSink(m_tid);
            m_keySinkOn = false;
        }
        if (m_keystrokeMgr) { m_keystrokeMgr->Release(); m_keystrokeMgr = nullptr; }

        if (m_source)
        {
            if (m_dwSinkCookie != TF_INVALID_COOKIE)
                m_source->UnadviseSink(m_dwSinkCookie);
            m_source->Release();
            m_source = nullptr;
        }
        m_dwKeyCookie = m_dwSinkCookie = TF_INVALID_COOKIE;
        m_cand.Destroy();
        m_candReady = false;
        if (m_tim) { m_tim->Release(); m_tim = nullptr; }
        return S_OK;
    }

    // ITfThreadMgrEventSink
    STDMETHODIMP OnSetFocus(ITfDocumentMgr* pdimFocus,
                            ITfDocumentMgr*) override
    {
        // **按键接收器要在这里挂，不是在 Activate 里。**
        // 在 Activate 里挂会拿到 TF_E_NOOBJECT(0x80040202)：那时我们还没有焦点，
        // TSF 认为「没有可挂的对象」。等收到 OnSetFocus（拿到文档）之后才挂得上。
        // 这一步失败是静默的 —— 现象就是「输入法切过去了，敲什么都打不出来」。
        ImeLog("OnSetFocus dim=%p", (void*)pdimFocus);
        TryAdviseKeySink("OnSetFocus");
        Reset();
        return S_OK;
    }
    STDMETHODIMP OnPushContext(ITfContext*) override { return S_OK; }
    STDMETHODIMP OnPopContext(ITfContext*) override { return S_OK; }
    STDMETHODIMP OnInitDocumentMgr(ITfDocumentMgr*) override { return S_OK; }
    STDMETHODIMP OnUninitDocumentMgr(ITfDocumentMgr*) override { return S_OK; }

    // ITfKeyEventSink
    STDMETHODIMP OnSetFocus(BOOL fForeground) override
    {
        // 输入法拿到/失去前台时也会通知；这时再补挂一次，
        // 因为焦点可能来得比 OnSetFocus 早或晚。
        if (fForeground) TryAdviseKeySink("KeySink::OnSetFocus");
        return S_OK;
    }

    STDMETHODIMP OnTestKeyDown(ITfContext*, WPARAM wParam, LPARAM, BOOL* pfEaten) override
    {
        *pfEaten = ShouldEat(wParam) ? TRUE : FALSE;
        return S_OK;
    }
    STDMETHODIMP OnTestKeyUp(ITfContext*, WPARAM, LPARAM, BOOL* pfEaten) override
    { *pfEaten = FALSE; return S_OK; }
    STDMETHODIMP OnKeyUp(ITfContext*, WPARAM, LPARAM, BOOL* pfEaten) override
    { *pfEaten = FALSE; return S_OK; }

    // ITfKeyEventSink 的纯虚函数，必须实现（我们不用保留键，直接返回 FALSE）
    STDMETHODIMP OnPreservedKey(ITfContext*, REFGUID, BOOL* pfEaten) override
    { *pfEaten = FALSE; return S_OK; }

    STDMETHODIMP OnKeyDown(ITfContext* pic, WPARAM wParam, LPARAM, BOOL* pfEaten) override
    {
        *pfEaten = FALSE;
        ImeLog("OnKeyDown vk=%u buf=%d enabled=%d", (unsigned)wParam,
               (int)m_buf.size(), (int)g_enabled);

        // 开关热键：Ctrl+Shift+H
        if (wParam == 'H' &&
            (GetKeyState(VK_CONTROL) & 0x8000) &&
            (GetKeyState(VK_SHIFT) & 0x8000))
        {
            g_enabled = !g_enabled;
            Reset();
            *pfEaten = TRUE;
            return S_OK;
        }
        if (!g_enabled) return S_OK;

        switch (wParam)
        {
        case VK_ESCAPE:
            if (!m_buf.empty()) { Reset(); *pfEaten = TRUE; }
            return S_OK;

        case VK_BACK:
            if (!m_buf.empty())
            {
                m_buf.pop_back();
                Update();
                *pfEaten = TRUE;
            }
            return S_OK;

        case VK_SPACE:
        case VK_RETURN:
            if (!m_buf.empty() && !m_cands.empty())
            {
                Commit(pic, 0);
                *pfEaten = TRUE;
            }
            return S_OK;

        case '1': case '2': case '3': case '4': case '5':
        case '6': case '7': case '8': case '9':
            if (!m_buf.empty())
            {
                int idx = (int)(wParam - '1');
                if (idx < (int)m_cands.size())
                {
                    Commit(pic, idx);
                    *pfEaten = TRUE;
                }
            }
            return S_OK;

        default:
            break;
        }

        // 字母：进缓冲区
        if (wParam >= 'A' && wParam <= 'Z')
        {
            m_buf.push_back((wchar_t)(wParam - 'A' + 'a'));
            Update();
            *pfEaten = TRUE;
        }
        return S_OK;
    }

    // ITfEditSession
    STDMETHODIMP DoEditSession(TfEditCookie ec) override
    {
        if (!m_pCommitted) return S_OK;

        ITfInsertAtSelection* pInsert = nullptr;
        if (SUCCEEDED(m_pCommittedCtx->QueryInterface(
                IID_ITfInsertAtSelection, (void**)&pInsert)) && pInsert)
        {
            ITfRange* pRange = nullptr;
            // TF_IAS_QUERYONLY 不传，只要插入
            pInsert->InsertTextAtSelection(ec, 0, m_pCommitted,
                                           (LONG)m_commitLen, &pRange);
            if (pRange) pRange->Release();
            pInsert->Release();
        }
        return S_OK;
    }

private:
    bool ShouldEat(WPARAM wParam) const
    {
        if (wParam == 'H' &&
            (GetKeyState(VK_CONTROL) & 0x8000) &&
            (GetKeyState(VK_SHIFT) & 0x8000))
            return true;
        if (!g_enabled) return false;
        if (!m_buf.empty())
        {
            if (wParam == VK_ESCAPE || wParam == VK_BACK || wParam == VK_SPACE ||
                wParam == VK_RETURN) return true;
            if (wParam >= '1' && wParam <= '9') return true;
        }
        return wParam >= 'A' && wParam <= 'Z';
    }

    // 候选窗**延迟创建**：Activate 期间不做任何创建窗口的事，
    // 那时正处在 TSF 的激活路径上，重入没有好处。
    void EnsureCand()
    {
        if (!m_candReady)
            m_candReady = m_cand.Create(g_hInst);
    }

    // 挂按键接收器。
    //
    // **正确的接口是 `ITfKeystrokeMgr::AdviseKeyEventSink(tid, pSink, fForeground)`**，
    // 不是 `ITfSource::AdviseSink(IID_ITfKeyEventSink, ...)`。
    // 用后者会一直拿到 `TF_E_NOOBJECT (0x80040202)` —— 线程管理器的 ITfSource
    // 根本不认这个 IID（它的 AdviseSink 是给 ITfThreadMgrEventSink 用的）。
    // 这个失败是**静默**的：输入法切过去了、组件也加载了、OnSetFocus 也收到了，
    // 就是敲什么都没反应 —— 最难查的一种。
    void TryAdviseKeySink(const char* where)
    {
        if (m_keySinkOn) return;                 // 已经挂上了
        if (!m_tim) { ImeLog("  (%s) 没有 thread manager", where); return; }
        ITfKeystrokeMgr* pKm = nullptr;
        HRESULT hq = m_tim->QueryInterface(IID_ITfKeystrokeMgr, (void**)&pKm);
        if (FAILED(hq) || !pKm)
        {
            ImeLog("  (%s) 取 ITfKeystrokeMgr 失败 0x%08X", where, (unsigned)hq);
            return;
        }
        HRESULT hr = pKm->AdviseKeyEventSink(m_tid, this, TRUE);
        ImeLog("  (%s) AdviseKeyEventSink = 0x%08X %s", where, (unsigned)hr,
               SUCCEEDED(hr) ? "← 按键接通了" : "（没挂上）");
        if (SUCCEEDED(hr))
        {
            if (m_keystrokeMgr) m_keystrokeMgr->Release();
            m_keystrokeMgr = pKm;                // 反注册时要用
            m_keySinkOn = true;
        }
        else
        {
            pKm->Release();
        }
    }

    // 按当前缓冲区重算候选
    void Update()
    {
        m_cands.clear();
        if (m_buf.empty()) { m_cand.Hide(); return; }
        EnsureCand();

        // 前缀匹配：表已按 key 排序，扫一遍即可（3000 条，每次击键扫完很快）
        for (int i = 0; i < HW_ENTRY_COUNT && (int)m_cands.size() < 9; ++i)
        {
            const HwEntry& e = HW_ENTRIES[i];
            size_t n = m_buf.size();
            if (wcslen(e.key) >= n && wcsncmp(e.key, m_buf.c_str(), n) == 0)
                m_cands.push_back(&e);
        }

        std::wstring show = m_buf + L"　";
        if (m_cands.empty())
            show += L"(无候选)";
        else
            for (size_t i = 0; i < m_cands.size(); ++i)
            {
                show += std::to_wstring(i + 1);
                show += L".";
                show += m_cands[i]->zh;
                show += L" ";
            }
        m_cand.Show(show, nullptr);
    }

    void Reset()
    {
        m_buf.clear();
        m_cands.clear();
        m_cand.Hide();
    }

    void Commit(ITfContext* pic, size_t idx)
    {
        if (idx >= m_cands.size()) { Reset(); return; }
        // 只记码位，不记汉字：窄 printf 的 %ls 会走 locale 转换，中文可能变问号
        ImeLog("Commit idx=%d cp=U+%04X -> 插入文档",
               (int)idx, (unsigned)m_cands[idx]->cp);
        m_committed = m_cands[idx]->cp;      // 只提交**一个字**（一个词一个字形）
        m_commitLen = 1;
        m_pCommitted = &m_committed;
        m_pCommittedCtx = pic;

        HRESULT hr = S_OK;
        if (pic)
            pic->RequestEditSession(m_tid, this,
                                    TF_ES_ASYNCDONTCARE | TF_ES_READWRITE, &hr);
        Reset();
    }

    LONG m_cRef;
    TfClientId m_tid;
    ITfThreadMgr* m_tim = nullptr;
    ITfSource*    m_source = nullptr;
    ITfKeystrokeMgr* m_keystrokeMgr = nullptr;   // 按键接收器挂在这个接口上
    bool m_keySinkOn = false;
    DWORD m_dwSinkCookie;
    DWORD m_dwKeyCookie;

    std::wstring m_buf;                              // 已输入的字母
    std::vector<const HwEntry*> m_cands;             // 当前候选
    CCandWindow m_cand;
    bool m_candReady = false;                        // 候选窗是否已创建（延迟创建）

    // 提交用（DoEditSession 里读）
    wchar_t m_committed = 0;
    LONG m_commitLen = 0;
    wchar_t* m_pCommitted = nullptr;
    ITfContext* m_pCommittedCtx = nullptr;
};

// ------------------------------------------------------------------ 类工厂
class CClassFactory : public IClassFactory
{
public:
    CClassFactory() : m_cRef(1) { InterlockedIncrement(&g_cRef); }
    ~CClassFactory() { InterlockedDecrement(&g_cRef); }

    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override
    {
        if (!ppv) return E_INVALIDARG;
        *ppv = nullptr;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IClassFactory))
        {
            *ppv = static_cast<IClassFactory*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_cRef); }
    STDMETHODIMP_(ULONG) Release() override
    {
        LONG c = InterlockedDecrement(&m_cRef);
        if (c == 0) delete this;
        return c;
    }

    STDMETHODIMP CreateInstance(IUnknown* pUnkOuter, REFIID riid, void** ppv) override
    {
        if (pUnkOuter) return CLASS_E_NOAGGREGATION;
        CHuiwenTextService* p = new (std::nothrow) CHuiwenTextService();
        if (!p) return E_OUTOFMEMORY;
        HRESULT hr = p->QueryInterface(riid, ppv);
        p->Release();
        return hr;
    }
    STDMETHODIMP LockServer(BOOL lock) override
    {
        if (lock) InterlockedIncrement(&g_cRef);
        else InterlockedDecrement(&g_cRef);
        return S_OK;
    }

private:
    LONG m_cRef;
};

// ------------------------------------------------------------------ DLL 导出
STDAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void** ppv)
{
    // TSF 走 COM 创建我们时必经此处，记一笔作为「确实被调用」的证据
    ImeLog("DllGetClassObject: TSF 正在创建文本服务");
    if (!IsEqualCLSID(rclsid, CLSID_HuiwenTextService)) return CLASS_E_CLASSNOTAVAILABLE;
    CClassFactory* p = new (std::nothrow) CClassFactory();
    if (!p) return E_OUTOFMEMORY;
    HRESULT hr = p->QueryInterface(riid, ppv);
    p->Release();
    return hr;
}

STDAPI DllCanUnloadNow()
{
    return g_cRef > 0 ? S_FALSE : S_OK;
}

// 把 DLL 路径写进 HKCR\CLSID\{...}\InprocServer32
static HRESULT RegisterServer()
{
    wchar_t path[MAX_PATH] = { 0 };
    if (!GetModuleFileNameW(g_hInst, path, MAX_PATH)) return E_FAIL;

    wchar_t clsid[64] = { 0 };
    StringFromGUID2(CLSID_HuiwenTextService, clsid, 64);

    // COM 类注册：**优先机器级（HKLM），失败再退回用户级（HKCU）**。
    //   提权安装时 HKLM 可用，所有进程（含管理员进程）都能加载；
    //   未提权时 HKLM 会拒绝访问，退回 HKCU 也能让同一用户的所有程序加载。
    //   注意：TSF 的**语言档案**（AddLanguageProfile）只能写 HKLM，
    //   那是 Windows 的安全边界 —— 注册输入法必须提权，没有绕法。
    std::wstring key = L"Software\\Classes\\CLSID\\";
    key += clsid;
    HKEY hk = nullptr;
    HKEY hRoot = HKEY_LOCAL_MACHINE;
    LONG r = RegCreateKeyExW(HKEY_LOCAL_MACHINE, key.c_str(), 0, nullptr, 0,
                             KEY_WRITE, nullptr, &hk, nullptr);
    if (r != ERROR_SUCCESS)
    {
        hRoot = HKEY_CURRENT_USER;
        r = RegCreateKeyExW(HKEY_CURRENT_USER, key.c_str(), 0, nullptr, 0,
                            KEY_WRITE, nullptr, &hk, nullptr);
    }
    if (r != ERROR_SUCCESS)
        return E_FAIL;
    (void)hRoot;
    const wchar_t* desc = kServiceDesc;
    RegSetValueExW(hk, nullptr, 0, REG_SZ, (const BYTE*)desc,
                   (DWORD)((wcslen(desc) + 1) * sizeof(wchar_t)));

    HKEY hk2 = nullptr;
    RegCreateKeyExW(hk, L"InprocServer32", 0, nullptr, 0, KEY_WRITE, nullptr,
                    &hk2, nullptr);
    RegSetValueExW(hk2, nullptr, 0, REG_SZ, (const BYTE*)path,
                   (DWORD)((wcslen(path) + 1) * sizeof(wchar_t)));
    const wchar_t* model = L"Apartment";
    RegSetValueExW(hk2, L"ThreadingModel", 0, REG_SZ, (const BYTE*)model,
                   (DWORD)((wcslen(model) + 1) * sizeof(wchar_t)));
    RegCloseKey(hk2);
    RegCloseKey(hk);
    return S_OK;
}

static void UnregisterServer()
{
    wchar_t clsid[64] = { 0 };
    StringFromGUID2(CLSID_HuiwenTextService, clsid, 64);
    std::wstring key = L"Software\\Classes\\CLSID\\";
    key += clsid;
    RegDeleteTreeW(HKEY_LOCAL_MACHINE, key.c_str());
    RegDeleteTreeW(HKEY_CURRENT_USER, key.c_str());
}

STDAPI DllRegisterServer()
{
    // 下面要 CoCreateInstance 调 TSF 的注册接口，必须先把 COM 起起来。
    // regsvr32 **不保证**已经初始化过 COM，不自己初始化会拿到 CO_E_NOTINITIALIZED。
    HRESULT hrCo = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool needUninit = SUCCEEDED(hrCo);

    if (FAILED(RegisterServer()))
    {
        if (needUninit) CoUninitialize();
        return E_FAIL;
    }

    // 用 TSF 自己的 API 注册文本服务与语言档案（比手写注册表可靠）
    ITfInputProcessorProfiles* pProf = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfiles, (void**)&pProf);
    if (FAILED(hr) || !pProf)
    {
        if (needUninit) CoUninitialize();
        return E_FAIL;
    }

    hr = pProf->Register(CLSID_HuiwenTextService);
    if (SUCCEEDED(hr))
    {
        // 图标**不能留空**：留空时注册表里会写下一个空的 IconFile，
        // 而能正常切换的输入法那一条都是实路径。找不到图标就退化为无名，
        // 但不要写空串。
        wchar_t dllPath[MAX_PATH] = { 0 };
        GetModuleFileNameW(g_hInst, dllPath, MAX_PATH);
        std::wstring icon = dllPath;
        size_t slash = icon.find_last_of(L'\\');
        if (slash != std::wstring::npos)
        {
            icon = icon.substr(0, slash);            // ...\tsf\out
            icon += L"\\..\\..\\font\\GalHuiwen.ico"; // → huiwen/font/GalHuiwen.ico
        }
        bool hasIcon = (GetFileAttributesW(icon.c_str()) != INVALID_FILE_ATTRIBUTES);
        ImeLog("Register: 图标 %s", hasIcon ? "找到" : "没找到");

        hr = pProf->AddLanguageProfile(
            CLSID_HuiwenTextService, HUIWEN_LANGID, GUID_HuiwenProfile,
            kServiceDesc, (ULONG)wcslen(kServiceDesc),
            hasIcon ? icon.c_str() : L"",
            hasIcon ? (ULONG)icon.size() : 0, 0);
    }
    // 必须显式 Enable，否则语言栏里不出现
    if (SUCCEEDED(hr))
    {
        pProf->EnableLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                     GUID_HuiwenProfile, TRUE);
        pProf->EnableLanguageProfileByDefault(CLSID_HuiwenTextService,
                                              HUIWEN_LANGID,
                                              GUID_HuiwenProfile, TRUE);
    }
    pProf->Release();

    // 注册「键盘输入法」这个类别，否则 TSF 不会把它当输入法加载
    ITfCategoryMgr* pCat = nullptr;
    hr = CoCreateInstance(CLSID_TF_CategoryMgr, nullptr, CLSCTX_INPROC_SERVER,
                          IID_ITfCategoryMgr, (void**)&pCat);
    if (SUCCEEDED(hr) && pCat)
    {
        pCat->RegisterCategory(CLSID_HuiwenTextService,
                               GUID_TFCAT_TIP_KEYBOARD,
                               CLSID_HuiwenTextService);
        pCat->Release();
    }
    if (needUninit) CoUninitialize();
    return S_OK;
}

STDAPI DllUnregisterServer()
{
    ITfCategoryMgr* pCat = nullptr;
    if (SUCCEEDED(CoCreateInstance(CLSID_TF_CategoryMgr, nullptr,
                                   CLSCTX_INPROC_SERVER, IID_ITfCategoryMgr,
                                   (void**)&pCat)) && pCat)
    {
        pCat->UnregisterCategory(CLSID_HuiwenTextService,
                                 GUID_TFCAT_TIP_KEYBOARD,
                                 CLSID_HuiwenTextService);
        pCat->Release();
    }

    ITfInputProcessorProfiles* pProf = nullptr;
    if (SUCCEEDED(CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                   CLSCTX_INPROC_SERVER,
                                   IID_ITfInputProcessorProfiles,
                                   (void**)&pProf)) && pProf)
    {
        pProf->RemoveLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                     GUID_HuiwenProfile);
        pProf->Unregister(CLSID_HuiwenTextService);
        pProf->Release();
    }
    UnregisterServer();
    return S_OK;
}

BOOL APIENTRY DllMain(HINSTANCE hInst, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_hInst = hInst;
        DisableThreadLibraryCalls(hInst);
        // **这里绝对不能写日志**：DllMain 在加载器锁内，做文件 IO 会让
        // 进程以 0xC0000409 崩溃（实测：DLL 一加载进程就死，日志只留下 3 字节 BOM）。
        // 要确认「DLL 有没有被加载」，看 DllGetClassObject 那条日志即可 ——
        // TSF 走 COM 创建我们时必经那里，且在加载器锁之外。
    }
    return TRUE;
}


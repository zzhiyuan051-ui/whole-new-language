// 洄文输入法 · 键盘钩子版（免管理员）
//
// 为什么还要一个「钩子版」：
//   正统的 TSF 版本（huiwen_ime.dll）注册时必须写 HKLM\...\CTF\TIP，
//   而 Windows 把那条路锁死了 —— **注册输入法必须管理员权限**（实测拒绝访问）。
//   钩子版不需要注册任何东西，任何权限都能跑，代价是不能被语言栏识别、
//   且对「以管理员运行的程序」无效（Windows 不允许低权限进程往高权限窗口注入输入）。
//
// 工作方式：
//   WH_KEYBOARD_LL 全局低级键盘钩子 → 拦字母键进缓冲区 → 候选窗显示 →
//   选中后用 SendInput(KEYEVENTF_UNICODE) 把洄文字形打进当前焦点窗口。
//
// 开关：Ctrl+Shift+H（默认开）

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif

#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string>
#include <vector>

#include "hwdata.h"

static HHOOK  g_hook = nullptr;
static HWND   g_wnd = nullptr;      // 候选窗
static HWND   g_label = nullptr;
static HFONT  g_font = nullptr;
static bool   g_enabled = true;
static bool   g_injecting = false;  // 正在注入，避免钩子吃自己的输入
// 是否接受「注入的」按键（flags 带 LLKHF_INJECTED）。
//
// 默认**接受**。理由：远程桌面、虚拟机、某些键盘驱动与辅助工具产生的按键
// 都带这个标记；默认拒收的话，输入法在这些环境下会完全没反应 ——
// 而表象只是「双击了、也弹窗了，就是打不出字」，极难排查。
// 代价：别的程序合成出来的键也会被接管；对本项目是可接受的取舍。
// 想恢复「只接管真实按键」用 --ignore-injected。
static bool   g_acceptInjected = true;

// 诊断日志。**默认就开**（不用加参数）：
//   钩子里的问题在外面看不见，用户双击运行时也不会带命令行参数，
//   所以必须默认写日志，否则出问题无从查起。
//   默认路径 %LOCALAPPDATA%\GalHuiwenIME\hook.log，可用 --log <文件> 改。
//   一次运行截断一次（写起来用 "wb"），避免越滚越大。
static FILE* g_log = nullptr;
static void LOG(const char* fmt, ...)
{
    if (!g_log) return;
    va_list ap; va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fflush(g_log);
}

// 控制台也用 UTF-8，否则中文输出全是乱码
static void SetupConsole()
{
    SetConsoleOutputCP(65001);
    SetConsoleCP(65001);
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    if (h && h != INVALID_HANDLE_VALUE)
    {
        DWORD mode = 0;
        if (GetConsoleMode(h, &mode))
            SetConsoleMode(h, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
    }
}

// 打开默认日志（%LOCALAPPDATA%\GalHuiwenIME\hook.log）
static void OpenDefaultLog()
{
    if (g_log) return;
    wchar_t dir[MAX_PATH] = { 0 };
    if (!GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH)) return;
    std::wstring path = std::wstring(dir) + L"\\GalHuiwenIME";
    CreateDirectoryW(path.c_str(), nullptr);
    path += L"\\hook.log";
    FILE* f = nullptr;
    if (_wfopen_s(&f, path.c_str(), L"wb") == 0) g_log = f;
}

static std::wstring g_buf;
static std::vector<const HwEntry*> g_cands;

#define WM_HW_UPDATE (WM_APP + 1)
#define WM_HW_COMMIT (WM_APP + 2)

static const wchar_t* kWndClass = L"HuiwenHookWnd";

// 归一化：只留 a-z。**必须与 Python engine.IME.norm 一致**。
static std::wstring normKey(const std::wstring& s)
{
    std::wstring o;
    for (wchar_t c : s)
        if (c >= L'A' && c <= L'Z') o.push_back((wchar_t)(c - L'A' + L'a'));
        else if (c >= L'a' && c <= L'z') o.push_back(c);
    return o;
}

static POINT CaretPos()
{
    POINT pt = { 0, 0 };
    GUITHREADINFO gti = { 0 };
    gti.cbSize = sizeof(gti);
    DWORD tid = GetWindowThreadProcessId(GetForegroundWindow(), nullptr);
    if (GetGUIThreadInfo(tid, &gti) && gti.hwndCaret)
    {
        POINT p2 = { gti.rcCaret.left, gti.rcCaret.bottom };
        if (ClientToScreen(gti.hwndCaret, &p2)) return p2;
    }
    GetCursorPos(&pt);
    return pt;
}

static void UpdateCands()
{
    g_cands.clear();
    if (g_buf.empty()) { ShowWindow(g_wnd, SW_HIDE); return; }
    for (int i = 0; i < HW_ENTRY_COUNT && (int)g_cands.size() < 9; ++i)
    {
        const HwEntry& e = HW_ENTRIES[i];
        size_t n = g_buf.size();
        if (wcslen(e.key) >= n && wcsncmp(e.key, g_buf.c_str(), n) == 0)
            g_cands.push_back(&e);
    }

    std::wstring show = g_buf + L"  ";
    if (g_cands.empty()) show += L"(无候选)";
    else
        for (size_t i = 0; i < g_cands.size(); ++i)
        {
            show += std::to_wstring(i + 1);
            show += L".";
            show += g_cands[i]->zh;
            show += L" ";
        }
    SetWindowTextW(g_label, show.c_str());

    HDC hdc = GetDC(g_wnd);
    HFONT old = (HFONT)SelectObject(hdc, g_font);
    SIZE sz = { 0, 0 };
    GetTextExtentPoint32W(hdc, show.c_str(), (int)show.size(), &sz);
    SelectObject(hdc, old);
    ReleaseDC(g_wnd, hdc);

    int w = sz.cx + 28, h = sz.cy + 18;
    if (w < 200) w = 200;
    POINT pt = CaretPos();
    int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
    int x = pt.x + 6, y = pt.y + 22;
    if (x + w > sw) x = sw - w - 4;
    if (y + h > sh) y = pt.y - h - 8;
    if (x < 0) x = 0;
    if (y < 0) y = 0;

    MoveWindow(g_wnd, x, y, w, h, TRUE);
    MoveWindow(g_label, 10, 7, w - 20, h - 14, TRUE);
    ShowWindow(g_wnd, SW_SHOWNOACTIVATE);
    SetWindowPos(g_wnd, HWND_TOPMOST, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
}

// 用 SendInput 把字**按 Unicode 打出去**。
// 关键：KEYEVENTF_UNICODE 走的是「字符」通道，不受键盘布局影响，
// 这正是输入法注入私用区码位所需要的。
static void SendUnicodeChar(wchar_t ch)
{
    LOG("SendUnicodeChar U+%04X", (unsigned)ch);
    g_injecting = true;
    INPUT in[2] = { 0 };
    in[0].type = INPUT_KEYBOARD;
    in[0].ki.wScan = ch;
    in[0].ki.dwFlags = KEYEVENTF_UNICODE;
    in[1] = in[0];
    in[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
    UINT sent = SendInput(2, in, sizeof(INPUT));
    LOG("SendInput returned %u (err=%lu)", sent, GetLastError());
    Sleep(8);
    g_injecting = false;
}

static void Commit(size_t idx)
{
    LOG("Commit idx=%d cands=%d", (int)idx, (int)g_cands.size());
    if (idx < g_cands.size())
    {
        wchar_t c = (wchar_t)g_cands[idx]->cp;
        SendUnicodeChar(c);
    }
    g_buf.clear();
    g_cands.clear();
    ShowWindow(g_wnd, SW_HIDE);
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM wp, LPARAM lp)
{
    switch (m)
    {
    case WM_HW_UPDATE: UpdateCands(); return 0;
    case WM_HW_COMMIT: Commit((size_t)wp); return 0;
    case WM_ERASEBKGND: return 1;
    }
    return DefWindowProcW(h, m, wp, lp);
}

static bool IsToggle(WPARAM vk)
{
    return vk == 'H' && (GetKeyState(VK_CONTROL) & 0x8000) &&
           (GetKeyState(VK_SHIFT) & 0x8000);
}

static LRESULT CALLBACK LowLevelProc(int code, WPARAM wp, LPARAM lp)
{
    if (code != HC_ACTION) return CallNextHookEx(g_hook, code, wp, lp);

    KBDLLHOOKSTRUCT* k = (KBDLLHOOKSTRUCT*)lp;
    bool down = (wp == WM_KEYDOWN || wp == WM_SYSKEYDOWN);

    // 每个按键都记一笔（放在所有过滤之前）：
    // 这条日志在不在，直接决定「钩子到底有没有被调用」；
    // flags 里的 LLKHF_INJECTED(0x10) 决定「这个键是不是被合成出来的」。
    LOG("key vk=%u flags=0x%X down=%d injecting=%d accept=%d enabled=%d buf=%d",
        (unsigned)k->vkCode, (unsigned)k->flags, (int)down, (int)g_injecting,
        (int)g_acceptInjected, (int)g_enabled, (int)g_buf.size());

    // 控制台实时回显：用户一眼就能看出「钩子到底有没有在工作」，
    // 不必等我去读日志。只回显字母/数字/空格这类有意义的键，避免刷屏。
    static long s_seen = 0;
    if (down && ((k->vkCode >= 'A' && k->vkCode <= 'Z') ||
                 (k->vkCode >= '0' && k->vkCode <= '9') ||
                 k->vkCode == VK_SPACE || k->vkCode == VK_BACK ||
                 k->vkCode == VK_ESCAPE || k->vkCode == VK_RETURN))
    {
        ++s_seen;
        printf("  [%ld] vk=%u%s%s  缓冲=%d\r\n", s_seen, (unsigned)k->vkCode,
               (k->flags & LLKHF_INJECTED) ? " 注入" : " 物理",
               g_enabled ? "" : " (已关闭)", (int)g_buf.size());
        fflush(stdout);
    }
    if (g_injecting) return CallNextHookEx(g_hook, code, wp, lp);
    if (!g_acceptInjected && (k->flags & LLKHF_INJECTED))
        return CallNextHookEx(g_hook, code, wp, lp);

    if (!down) return CallNextHookEx(g_hook, code, wp, lp);

    if (IsToggle(k->vkCode))
    {
        g_enabled = !g_enabled;
        g_buf.clear();
        g_cands.clear();
        ShowWindow(g_wnd, SW_HIDE);
        return 1;
    }
    if (!g_enabled) return CallNextHookEx(g_hook, code, wp, lp);

    switch (k->vkCode)
    {
    case VK_ESCAPE:
        if (!g_buf.empty())
        {
            g_buf.clear();
            PostMessageW(g_wnd, WM_HW_UPDATE, 0, 0);
            return 1;
        }
        break;
    case VK_BACK:
        if (!g_buf.empty())
        {
            g_buf.pop_back();
            PostMessageW(g_wnd, WM_HW_UPDATE, 0, 0);
            return 1;
        }
        break;
    case VK_SPACE:
    case VK_RETURN:
        if (!g_buf.empty())
        {
            PostMessageW(g_wnd, WM_HW_COMMIT, 0, 0);
            return 1;
        }
        break;
    default:
        if (k->vkCode >= '1' && k->vkCode <= '9' && !g_buf.empty())
        {
            size_t idx = (size_t)(k->vkCode - '1');
            if (idx < g_cands.size())
            {
                PostMessageW(g_wnd, WM_HW_COMMIT, idx, 0);
                return 1;
            }
        }
        if (k->vkCode >= 'A' && k->vkCode <= 'Z')
        {
            g_buf.push_back((wchar_t)(k->vkCode - 'A' + 'a'));
            PostMessageW(g_wnd, WM_HW_UPDATE, 0, 0);
            return 1;
        }
        break;
    }
    return CallNextHookEx(g_hook, code, wp, lp);
}

static bool CreateCandWindow(HINSTANCE hInst)
{
    WNDCLASSEXW wc = { 0 };
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)GetStockObject(WHITE_BRUSH);
    wc.lpszClassName = kWndClass;
    if (!RegisterClassExW(&wc)) return false;

    g_font = CreateFontW(-20, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
                         0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei");
    g_wnd = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
                            kWndClass, L"", WS_POPUP | WS_BORDER,
                            0, 0, 10, 10, nullptr, nullptr, hInst, nullptr);
    if (!g_wnd) return false;
    g_label = CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE,
                              10, 7, 10, 20, g_wnd, nullptr, hInst, nullptr);
    SendMessageW(g_label, WM_SETFONT, (WPARAM)g_font, TRUE);
    return true;
}

int wmain(int argc, wchar_t** argv)
{
    SetupConsole();
    OpenDefaultLog();          // 默认就写日志，双击运行时也能事后排查

    for (int i = 1; i < argc; ++i)
    {
        if (wcscmp(argv[i], L"--accept-injected") == 0)
            g_acceptInjected = true;
        else if (wcscmp(argv[i], L"--ignore-injected") == 0)
            g_acceptInjected = false;
        else if (wcscmp(argv[i], L"--log") == 0 && i + 1 < argc)
        {
            if (g_log) { fclose(g_log); g_log = nullptr; }
            _wfopen_s(&g_log, argv[++i], L"wb");
        }
    }
    LOG("started acceptInjected=%d", (int)g_acceptInjected);

    HINSTANCE hInst = GetModuleHandleW(nullptr);
    if (!CreateCandWindow(hInst))
    {
        printf("创建候选窗失败\n");
        return 1;
    }

    g_hook = SetWindowsHookExW(WH_KEYBOARD_LL, LowLevelProc, hInst, 0);
    if (!g_hook)
    {
        printf("安装键盘钩子失败，错误码 %lu\n", GetLastError());
        LOG("SetWindowsHookEx 失败 err=%lu", GetLastError());
        return 1;
    }
    LOG("键盘钩子已安装 handle=%p", (void*)g_hook);

    printf("洄文输入法（钩子版）已启动。\n");
    printf("  Ctrl+Shift+H  开关输入法（当前：开）\n");
    printf("  敲字母出候选，按 1-9 或空格上屏，Esc 取消\n");
    printf("  本窗口关掉即退出\n");
    printf("  接受注入按键：%s（--ignore-injected 可关）\n",
           g_acceptInjected ? "是" : "否");
    wchar_t dir[MAX_PATH] = { 0 };
    if (GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH))
        printf("  日志：%ls\\GalHuiwenIME\\hook.log\n", dir);
    printf("\n现在请点进记事本，敲 z a。本窗口会实时显示收到的按键。\n");
    fflush(stdout);

    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0) > 0)
    {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    if (g_hook) UnhookWindowsHookEx(g_hook);
    return 0;
}

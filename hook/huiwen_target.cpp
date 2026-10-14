// 洄文输入法 · 端到端测试靶子
//
// 一个带编辑框的小窗口，定时把编辑框内容写成文件。
// 为什么要自己写靶子而不是用记事本：
//   记事本在不同 Windows 版本上控件类名不同，取文本不稳定；
//   自己写靶子就能确定性地读回「输入法到底往文档里打了什么」。
//
// 用法：huiwen_target.exe <输出文件> [存活秒数]

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>   // _wtoi

static HWND         g_edit = nullptr;
static const wchar_t* g_outPath = nullptr;
static int          g_lifeMs = 0;
static DWORD        g_start = 0;

static void DumpEdit()
{
    if (!g_edit || !g_outPath) return;
    int n = GetWindowTextLengthW(g_edit);
    wchar_t* buf = new wchar_t[n + 2];
    GetWindowTextW(g_edit, buf, n + 1);
    buf[n] = 0;

    // 写成「码位列表」，人读机读都方便
    FILE* f = nullptr;
    if (_wfopen_s(&f, g_outPath, L"wb") == 0 && f)
    {
        fprintf(f, "len=%d\n", n);
        fprintf(f, "hex=");
        for (int i = 0; i < n; ++i) fprintf(f, "%04X ", (unsigned)buf[i]);
        fprintf(f, "\n");
        // UTF-8 原样一份，便于肉眼核对
        int need = WideCharToMultiByte(CP_UTF8, 0, buf, n, nullptr, 0,
                                       nullptr, nullptr);
        char* u8 = new char[need + 1];
        WideCharToMultiByte(CP_UTF8, 0, buf, n, u8, need, nullptr, nullptr);
        u8[need] = 0;
        fprintf(f, "utf8=%s\n", u8);
        delete[] u8;
        fclose(f);
    }
    delete[] buf;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM wp, LPARAM lp)
{
    switch (m)
    {
    case WM_CREATE:
        g_edit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
                                 WS_CHILD | WS_VISIBLE | WS_VSCROLL |
                                 ES_MULTILINE | ES_AUTOVSCROLL,
                                 10, 10, 560, 120, h, (HMENU)100,
                                 GetModuleHandleW(nullptr), nullptr);
        SetFocus(g_edit);
        SetTimer(h, 1, 200, nullptr);
        return 0;
    case WM_TIMER:
        DumpEdit();
        if (g_lifeMs > 0 && (int)(GetTickCount() - g_start) > g_lifeMs)
            PostQuitMessage(0);
        return 0;
    case WM_SETFOCUS:
        SetFocus(g_edit);
        return 0;
    case WM_CLOSE:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

int wmain(int argc, wchar_t** argv)
{
    if (argc < 2)
    {
        printf("用法: huiwen_target.exe <输出文件> [存活秒数]\n");
        return 1;
    }
    g_outPath = argv[1];
    g_lifeMs = (argc > 2) ? _wtoi(argv[2]) * 1000 : 0;
    g_start = GetTickCount();

    HINSTANCE hInst = GetModuleHandleW(nullptr);
    WNDCLASSEXW wc = { 0 };
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = L"HuiwenTestTarget";
    RegisterClassExW(&wc);

    HWND h = CreateWindowExW(0, wc.lpszClassName, L"洄文输入法 · 测试靶子",
                             WS_OVERLAPPEDWINDOW, 80, 80, 620, 220,
                             nullptr, nullptr, hInst, nullptr);
    ShowWindow(h, SW_SHOW);
    SetForegroundWindow(h);
    SetFocus(g_edit);

    printf("靶子已启动，输出到 %ls\n", g_outPath);
    fflush(stdout);

    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0) > 0)
    {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    DumpEdit();
    return 0;
}

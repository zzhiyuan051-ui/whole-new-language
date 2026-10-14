// 洄文输入法 · TSF 诊断与注册工具
//
// 为什么不用 Python 做这件事：
//   TSF 的 CLSID/IID 在 msctf.h 里只是 extern 声明，值在库里。
//   用 C++ 直接链接这些库，就不必靠记忆去写 GUID，也不会抄错。
//
// 用法：
//   hwimetool verify          查 TSF 认不认「洄文输入法」
//   hwimetool list            列出当前语言下的所有输入法档案
//   hwimetool register-user   按用户写注册表（免管理员）
//   hwimetool unregister-user 清掉按用户的注册

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif

#include <windows.h>
#include <msctf.h>
#include <psapi.h>
#include <stdio.h>
#include <string>

static const CLSID CLSID_HuiwenTextService =
{ 0x7f3a9c10, 0x2b4d, 0x4e6a, { 0x9c, 0x11, 0x8a, 0x2f, 0x0d, 0x55, 0x3e, 0x71 } };

static const GUID GUID_HuiwenProfile =
{ 0x7f3a9c11, 0x2b4d, 0x4e6a, { 0x9c, 0x11, 0x8a, 0x2f, 0x0d, 0x55, 0x3e, 0x72 } };

static const LANGID HUIWEN_LANGID = 0x0804;

static void ToStr(REFGUID g, wchar_t* out, int cch)
{
    StringFromGUID2(g, out, cch);
    // StringFromGUID2 给的是大写带花括号，注册表里就是这形式
}

// ------------------------------------------------------------ verify
static int DoVerify()
{
    printf("=== TSF 档案验证 ===\n");

    ITfInputProcessorProfiles* p = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfiles, (void**)&p);
    printf("CoCreateInstance(ITfInputProcessorProfiles) -> 0x%08X\n", (unsigned)hr);
    if (FAILED(hr) || !p) return 1;

    BOOL enabled = FALSE;
    hr = p->IsEnabledLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                     GUID_HuiwenProfile, &enabled);
    printf("IsEnabledLanguageProfile -> 0x%08X, enabled=%d\n",
           (unsigned)hr, enabled);

    BSTR desc = nullptr;
    hr = p->GetLanguageProfileDescription(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                          GUID_HuiwenProfile, &desc);
    printf("GetLanguageProfileDescription -> 0x%08X", (unsigned)hr);
    if (SUCCEEDED(hr) && desc)
        wprintf(L", desc=\"%s\"\n", desc);
    else
        printf("（TSF 不认识这个档案）\n");
    if (desc) SysFreeString(desc);

    p->Release();

    int rc = (enabled && desc) ? 0 : 2;
    printf("\n结论：%s\n", rc == 0
           ? "TSF 已接受「洄文输入法」"
           : "TSF 尚未接受该档案（需要写 CTF 注册表）");
    return rc;
}

// ------------------------------------------------------------ list
class CEnumSink : public IEnumTfLanguageProfiles
{
public:
    CEnumSink() : m_cRef(1) {}
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override
    {
        if (!ppv) return E_INVALIDARG;
        *ppv = nullptr;
        if (IsEqualIID(riid, IID_IUnknown) ||
            IsEqualIID(riid, IID_IEnumTfLanguageProfiles))
        { *ppv = this; AddRef(); return S_OK; }
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_cRef); }
    STDMETHODIMP_(ULONG) Release() override
    {
        LONG c = InterlockedDecrement(&m_cRef);
        if (c == 0) delete this;
        return c;
    }
    // 这个类只作占位（真正枚举由系统给的枚举器完成），保留最小实现
    STDMETHODIMP Next(ULONG, TF_LANGUAGEPROFILE*, ULONG* n) override
    { if (n) *n = 0; return S_FALSE; }
    STDMETHODIMP Skip(ULONG) override { return S_FALSE; }
    STDMETHODIMP Reset() override { return S_OK; }
    STDMETHODIMP Clone(IEnumTfLanguageProfiles** pp) override
    { if (pp) *pp = nullptr; return E_NOTIMPL; }
private:
    LONG m_cRef;
};

// EnumLanguageProfiles 是**返回一个枚举器**让我们去 Next()，
// 不是让我们实现回调 sink。所以这里当调用方用。
static int DoListLang(LANGID langid, const char* label)
{
    printf("=== 输入法档案：%s ===\n", label);

    ITfInputProcessorProfiles* p = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfiles, (void**)&p);
    if (FAILED(hr) || !p) { printf("取接口失败 0x%08X\n", (unsigned)hr); return 1; }

    IEnumTfLanguageProfiles* pEnum = nullptr;
    hr = p->EnumLanguageProfiles(langid, &pEnum);
    if (FAILED(hr) || !pEnum)
    {
        printf("EnumLanguageProfiles(0x%04X) 失败 0x%08X\n",
               langid, (unsigned)hr);
        p->Release();
        return 1;
    }

    int n = 0, nMine = 0;
    TF_LANGUAGEPROFILE prof;
    ULONG fetched = 0;
    while (pEnum->Next(1, &prof, &fetched) == S_OK && fetched == 1)
    {
        ++n;
        wchar_t c[64] = { 0 };
        ToStr(prof.clsid, c, 64);
        bool mine = IsEqualCLSID(prof.clsid, CLSID_HuiwenTextService) != FALSE;
        if (mine) ++nMine;

        BSTR desc = nullptr;
        p->GetLanguageProfileDescription(prof.clsid, prof.langid,
                                         prof.guidProfile, &desc);
        // fActive 是「当前是否激活」；「是否启用」要另外问 IsEnabledLanguageProfile
        BOOL enabled = FALSE;
        p->IsEnabledLanguageProfile(prof.clsid, prof.langid, prof.guidProfile,
                                    &enabled);
        printf("  %s langid=0x%04X active=%d enabled=%d %ls  clsid=%ls\n",
               mine ? "★" : " ", prof.langid, prof.fActive, enabled,
               desc ? desc : L"(无描述)", c);
        if (desc) SysFreeString(desc);
    }
    pEnum->Release();
    p->Release();

    printf("  共 %d 个档案，其中洄文 %d 个\n\n", n, nMine);
    return nMine > 0 ? 0 : 2;
}

static int DoList()
{
    int a = DoListLang(0x0804, "0x0804 中文");
    DoListLang(0, "全部语言");
    return a;
}

// ------------------------------------------------------------ register-user
// 把 CTF 档案写到 HKCU。机器级（HKLM）需要管理员，用户级不需要。
static int DoRegisterUser(bool add)
{
    wchar_t clsid[64] = { 0 }, guid[64] = { 0 };
    ToStr(CLSID_HuiwenTextService, clsid, 64);
    ToStr(GUID_HuiwenProfile, guid, 64);
    wprintf(L"CLSID  = %s\nGUID   = %s\n", clsid, guid);

    std::wstring path = L"Software\\Microsoft\\CTF\\TIP\\";
    path += clsid;
    path += L"\\LanguageProfile\\0x00000804\\";
    path += guid;

    if (add)
    {
        HKEY hk = nullptr;
        LONG r = RegCreateKeyExW(HKEY_CURRENT_USER, path.c_str(), 0, nullptr, 0,
                                 KEY_WRITE, nullptr, &hk, nullptr);
        if (r != ERROR_SUCCESS)
        {
            printf("RegCreateKeyEx(HKCU) 失败，错误码 %ld\n", r);
            return 1;
        }
        DWORD one = 1;
        RegSetValueExW(hk, L"Enable", 0, REG_DWORD, (const BYTE*)&one, sizeof(one));
        const wchar_t* desc = L"洄文输入法";
        RegSetValueExW(hk, L"Description", 0, REG_SZ, (const BYTE*)desc,
                       (DWORD)((wcslen(desc) + 1) * sizeof(wchar_t)));
        DWORD zero = 0;
        RegSetValueExW(hk, L"IconIndex", 0, REG_DWORD, (const BYTE*)&zero,
                       sizeof(zero));
        RegCloseKey(hk);
        printf("已写入 HKCU\\%ls\n", path.c_str());
    }
    else
    {
        std::wstring root = L"Software\\Microsoft\\CTF\\TIP\\";
        root += clsid;
        LONG r = RegDeleteTreeW(HKEY_CURRENT_USER, root.c_str());
        printf("RegDeleteTree(HKCU) -> %ld\n", r);
    }
    return 0;
}

// ------------------------------------------------------------ selftest
// 不需要管理员的验证：把文本服务**当 COM 对象创建出来**，看它是不是
// 真的是一个 ITfTextInputProcessor。这一条能证明：
//   · DLL 能被系统加载
//   · 导出的 DllGetClassObject 工作正常
//   · 类工厂能造出对象，且实现了 TSF 要求的接口
// 注册系统输入法需要管理员，但「这个 DLL 是不是合格的 TSF 文本服务」
// 不需要 —— 所以这一条现在就能验。
static int DoSelfTest()
{
    printf("=== 洄文输入法文本服务 · COM 自检 ===\n");

    ITfTextInputProcessor* p = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_HuiwenTextService, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfTextInputProcessor, (void**)&p);
    printf("CoCreateInstance(CLSID_HuiwenTextService, ITfTextInputProcessor)\n");
    printf("  -> 0x%08X %s\n", (unsigned)hr,
           SUCCEEDED(hr) ? "成功" : "失败");
    if (FAILED(hr) || !p)
    {
        printf("\n判读：DLL 还没注册，或注册表里的路径不对。\n");
        printf("      先跑 hwimeinstall.py install（需要管理员才能注册输入法）。\n");
        return 1;
    }

    // 也查一下另外两个必需接口
    for (int i = 0; i < 2; ++i)
    {
        REFIID riid = (i == 0) ? IID_ITfKeyEventSink : IID_ITfThreadMgrEventSink;
        void* q = nullptr;
        HRESULT hr2 = p->QueryInterface(riid, &q);
        printf("  QueryInterface(%s) -> 0x%08X %s\n",
               (i == 0) ? "ITfKeyEventSink" : "ITfThreadMgrEventSink",
               (unsigned)hr2, SUCCEEDED(hr2) ? "成功" : "失败");
        if (q) ((IUnknown*)q)->Release();
    }

    p->Release();
    printf("\n结论：文本服务是合格的 COM 对象，接口齐全。\n");

    // 再看它在 TSF 里的处境
    ITfInputProcessorProfiles* pp = nullptr;
    if (SUCCEEDED(CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                   CLSCTX_INPROC_SERVER,
                                   IID_ITfInputProcessorProfiles,
                                   (void**)&pp)) && pp)
    {
        BOOL enabled = FALSE;
        pp->IsEnabledLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                     GUID_HuiwenProfile, &enabled);
        BSTR desc = nullptr;
        HRESULT hd = pp->GetLanguageProfileDescription(
            CLSID_HuiwenTextService, HUIWEN_LANGID, GUID_HuiwenProfile, &desc);
        printf("\nTSF 里：enabled=%d　描述读取=0x%08X\n", enabled, (unsigned)hd);
        if (SUCCEEDED(hd) && desc) { printf("  （描述非空，语言栏能看到它）\n"); SysFreeString(desc); }
        else printf("  （语言栏看不到它：档案没注册进 HKLM）\n");
        pp->Release();
    }
    return 0;
}

// ------------------------------------------------------------ activate
// 用 TSF 自己的接口把「洄文输入法」切成当前输入法。
// 有了它就能不改用户设置地验证「切上去之后到底工不工作」。
static int DoActivate(bool on)
{
    ITfInputProcessorProfiles* p = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfiles, (void**)&p);
    if (FAILED(hr) || !p) { printf("取接口失败 0x%08X\n", (unsigned)hr); return 1; }

    if (on)
    {
        hr = p->ActivateLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                        GUID_HuiwenProfile);
        printf("ActivateLanguageProfile(洄文输入法) -> 0x%08X %s\n",
               (unsigned)hr, SUCCEEDED(hr) ? "成功" : "失败");
        // 同时设为该语言的默认，减少被别的输入法抢回去的机会。
        // 参数顺序是 (langid, clsid, guidProfile) —— 以头文件为准，别凭记忆写。
        HRESULT h2 = p->SetDefaultLanguageProfile(
            HUIWEN_LANGID, CLSID_HuiwenTextService, GUID_HuiwenProfile);
        printf("SetDefaultLanguageProfile          -> 0x%08X %s\n",
               (unsigned)h2, SUCCEEDED(h2) ? "成功" : "失败");
    }
    else
    {
        // 切回空档案：交给系统挑一个默认的
        hr = p->ActivateLanguageProfile(CLSID_NULL, HUIWEN_LANGID, GUID_NULL);
        printf("ActivateLanguageProfile(空) -> 0x%08X\n", (unsigned)hr);
    }

    // 回读：签名是 GetActiveLanguageProfile(REFCLSID, LANGID*, GUID*)。
    // 传我们自己的 CLSID 还能读出来，就说明此刻激活的正是我们的档案。
    LANGID curLang = 0;
    GUID curGuid = GUID_NULL;
    HRESULT hg = p->GetActiveLanguageProfile(CLSID_HuiwenTextService,
                                             &curLang, &curGuid);
    if (SUCCEEDED(hg))
    {
        wchar_t g[64] = { 0 };
        StringFromGUID2(curGuid, g, 64);
        printf("GetActiveLanguageProfile(洄文) -> 成功　langid=0x%04X　%ls\n",
               curLang, g);
        printf("  → 「洄文输入法」此刻就是激活的输入法\n");
    }
    else
    {
        printf("GetActiveLanguageProfile(洄文) -> 0x%08X（此刻不是它）\n",
               (unsigned)hg);
    }
    p->Release();
    return SUCCEEDED(hr) ? 0 : 1;
}

// ------------------------------------------------------------ activate-test
// **本地可判定的关键实验**：在自己的进程里激活「洄文输入法」，
// 然后检查我们自己的 DLL 有没有被 TSF 加载进来。
//
// 这个实验的价值：它把「语言栏/其他应用」这些外部变量全排除掉，
// 只问一个问题 —— TSF 到底能不能把我们的文本服务拉起来。
//   加载了 → TSF 侧没问题，故障在语言栏切换或目标应用
//   没加载 → TSF 拒绝加载我们的组件（HKCU/HKLM 注册、CLSID、接口必有一处不对）
static bool SelfHasOurDll(std::wstring* found)
{
    HMODULE mods[1024];
    DWORD need = 0;
    HANDLE self = GetCurrentProcess();
    if (!EnumProcessModulesEx(self, mods, sizeof(mods), &need, LIST_MODULES_ALL))
        return false;
    DWORD n = need / sizeof(HMODULE);
    for (DWORD i = 0; i < n; ++i)
    {
        wchar_t path[MAX_PATH] = { 0 };
        if (GetModuleFileNameExW(self, mods[i], path, MAX_PATH))
        {
            std::wstring p = path;
            for (auto& c : p) c = towlower(c);
            if (p.find(L"huiwen_ime") != std::wstring::npos)
            {
                if (found) *found = path;
                return true;
            }
        }
    }
    return false;
}

static void Pump(DWORD ms)
{
    MSG m;
    DWORD t0 = GetTickCount();
    while (GetTickCount() - t0 < ms)
    {
        while (PeekMessageW(&m, nullptr, 0, 0, PM_REMOVE))
        {
            TranslateMessage(&m);
            DispatchMessageW(&m);
        }
        Sleep(10);
    }
}

// 一个真的能打字的窗口（RichEdit）。**必须有它实验才有效**：
// TSF 只在「线程上有文档、有焦点」时才真正去创建输入法组件；
// 没有可输入的控件时，ActivateLanguageProfile 会返回成功却什么也不做 ——
// 第一版实验就是这么拿到假阴性的（结论一度是错的）。
static HWND MakeRichEditWindow(HINSTANCE hInst, HWND* outEdit)
{
    LoadLibraryW(L"Msftedit.dll");
    WNDCLASSEXW wc = { 0 };
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = DefWindowProcW;
    wc.hInstance = hInst;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = L"HuiwenActivateTestWnd";
    RegisterClassExW(&wc);

    HWND h = CreateWindowExW(0, wc.lpszClassName, L"TSF 激活实验",
                             WS_OVERLAPPEDWINDOW, 100, 100, 520, 200,
                             nullptr, nullptr, hInst, nullptr);
    if (!h) return nullptr;
    HWND e = CreateWindowExW(WS_EX_CLIENTEDGE, L"RICHEDIT50W", L"",
                             WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE,
                             8, 8, 490, 150, h, nullptr, hInst, nullptr);
    if (!e) return nullptr;
    *outEdit = e;
    ShowWindow(h, SW_SHOW);
    SetForegroundWindow(h);
    SetFocus(e);
    return h;
}

static int DoActivateTest()
{
    printf("=== 本地实验：在真能打字的窗口里激活，TSF 会不会加载我们的 DLL ===\n\n");

    std::wstring before;
    printf("建窗口前，本进程加载了我们的 DLL：%s\n",
           SelfHasOurDll(&before) ? "是" : "否");

    HINSTANCE hInst = GetModuleHandleW(nullptr);
    HWND edit = nullptr;
    HWND wnd = MakeRichEditWindow(hInst, &edit);
    if (!wnd)
    {
        printf("创建 RichEdit 窗口失败（错误码 %lu）\n", GetLastError());
        return 1;
    }
    printf("已建 RichEdit 窗口并给焦点，先泵 1.5 秒消息让 TSF 初始化…\n");
    Pump(1500);

    ITfInputProcessorProfiles* p = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfiles, (void**)&p);
    if (FAILED(hr) || !p)
    {
        printf("取 ITfInputProcessorProfiles 失败 0x%08X\n", (unsigned)hr);
        return 1;
    }
    hr = p->ActivateLanguageProfile(CLSID_HuiwenTextService, HUIWEN_LANGID,
                                    GUID_HuiwenProfile);
    printf("ActivateLanguageProfile -> 0x%08X %s\n", (unsigned)hr,
           SUCCEEDED(hr) ? "成功" : "失败");
    p->Release();

    Pump(1500);          // 给 TSF 时间去加载组件

    std::wstring after;
    bool loaded = SelfHasOurDll(&after);
    printf("激活后，本进程加载了我们的 DLL：%s\n", loaded ? "是" : "否");
    if (loaded) wprintf(L"  路径：%s\n", after.c_str());

    DestroyWindow(wnd);

    printf("\n判读：\n");
    if (loaded)
        printf("  ✔ TSF 能加载并创建我们的文本服务\n"
               "    → 组件本身没问题，故障在语言栏切换或目标应用那一侧\n");
    else
        printf("  ✘ 有可输入窗口、TSF 也初始化了，仍未加载我们的组件\n"
               "    → 问题在注册项或接口，语言栏选中它也不会有反应\n");
    return loaded ? 0 : 2;
}

// ------------------------------------------------------------ switch
// 用 **会话级** 的方式把「洄文输入法」切成当前输入法 —— 这正是语言栏
// 选中一个输入法时该发生的事。
// `ActivateLanguageProfile` 只影响调用它的那个线程，所以它切不动别的程序；
// `ActivateProfile(..., TF_IPPMF_FORSESSION)` 才是全局的。
static int DoSwitch(bool on)
{
    ITfInputProcessorProfileMgr* pMgr = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                  CLSCTX_INPROC_SERVER,
                                  IID_ITfInputProcessorProfileMgr, (void**)&pMgr);
    if (FAILED(hr) || !pMgr)
    {
        printf("取 ITfInputProcessorProfileMgr 失败 0x%08X\n", (unsigned)hr);
        return 1;
    }

    DWORD flags = TF_IPPMF_FORSESSION;
    flags |= on ? TF_IPPMF_ENABLEPROFILE : TF_IPPMF_DISABLEPROFILE;

    hr = pMgr->ActivateProfile(TF_PROFILETYPE_INPUTPROCESSOR, HUIWEN_LANGID,
                               CLSID_HuiwenTextService, GUID_HuiwenProfile,
                               nullptr, flags);
    printf("ActivateProfile(%s, FORSESSION) -> 0x%08X %s\n",
           on ? "开" : "关", (unsigned)hr, SUCCEEDED(hr) ? "成功" : "失败");

    // 回读当前激活的是谁
    TF_INPUTPROCESSORPROFILE pip = { 0 };
    HRESULT hg = pMgr->GetActiveProfile(GUID_TFCAT_TIP_KEYBOARD, &pip);
    if (SUCCEEDED(hg))
    {
        wchar_t c[64] = { 0 };
        StringFromGUID2(pip.clsid, c, 64);
        printf("当前激活：langid=0x%04X clsid=%ls %s\n", pip.langid, c,
               IsEqualCLSID(pip.clsid, CLSID_HuiwenTextService) ? "← 就是洄文" : "");
    }
    else
        printf("GetActiveProfile -> 0x%08X\n", (unsigned)hg);

    pMgr->Release();
    return SUCCEEDED(hr) ? 0 : 1;
}

int wmain(int argc, wchar_t** argv)
{
    const wchar_t* cmd = (argc > 1) ? argv[1] : L"verify";

    HRESULT hr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool needUninit = SUCCEEDED(hr);

    int rc = 1;
    if (wcscmp(cmd, L"verify") == 0)          rc = DoVerify();
    else if (wcscmp(cmd, L"selftest") == 0)   rc = DoSelfTest();
    else if (wcscmp(cmd, L"activate") == 0)   rc = DoActivate(true);
    else if (wcscmp(cmd, L"deactivate") == 0) rc = DoActivate(false);
    else if (wcscmp(cmd, L"activate-test") == 0) rc = DoActivateTest();
    else if (wcscmp(cmd, L"switch-on") == 0)  rc = DoSwitch(true);
    else if (wcscmp(cmd, L"switch-off") == 0) rc = DoSwitch(false);
    else if (wcscmp(cmd, L"switch-away") == 0)
    {
        // 先切到「微软拼音」再切回我们 —— 强制 TSF 重新创建我们的组件。
        // 档案已经是激活状态时，再 switch-on 是空操作，不切走就看不到新 DLL 被加载。
        static const CLSID kPinyin =
        { 0x81d4e9c9, 0x1d3b, 0x41bc, { 0x9e, 0x6c, 0x4b, 0x40, 0xbf, 0x79, 0xe3, 0x5e } };
        static const GUID kPinyinProfile =
        { 0xfa550b04, 0x5ad7, 0x411f, { 0xa5, 0xac, 0xca, 0x03, 0x8e, 0xc5, 0x15, 0xd7 } };
        ITfInputProcessorProfileMgr* m = nullptr;
        if (SUCCEEDED(CoCreateInstance(CLSID_TF_InputProcessorProfiles, nullptr,
                                       CLSCTX_INPROC_SERVER,
                                       IID_ITfInputProcessorProfileMgr,
                                       (void**)&m)) && m)
        {
            HRESULT h = m->ActivateProfile(TF_PROFILETYPE_INPUTPROCESSOR,
                                           HUIWEN_LANGID, kPinyin, kPinyinProfile,
                                           nullptr, TF_IPPMF_FORSESSION);
            printf("切到微软拼音 -> 0x%08X %s\n", (unsigned)h,
                   SUCCEEDED(h) ? "成功" : "失败");
            m->Release();
        }
        Sleep(800);
        rc = DoSwitch(true);
    }
    else if (wcscmp(cmd, L"list") == 0)       rc = DoList();
    else if (wcscmp(cmd, L"register-user") == 0)   rc = DoRegisterUser(true);
    else if (wcscmp(cmd, L"unregister-user") == 0) rc = DoRegisterUser(false);
    else
    {
        printf("用法: hwimetool [verify|selftest|list|register-user|unregister-user]\n");
        rc = 1;
    }

    if (needUninit) CoUninitialize();
    return rc;
}

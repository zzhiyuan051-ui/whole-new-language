# 洄文输入法 · 系统级（TSF）与免安装（钩子）

这里是让洄文**在别的程序里直接打字**的两条实现。

| | TSF 版 | 钩子版 |
|---|---|---|
| 实现方式 | 正统 Windows 文本服务（Text Services Framework） | 全局低级键盘钩子 + 输入注入 |
| 被语言栏识别 | ✅ 可作为系统输入法选中 | ❌ 不出现 |
| 安装需要 | **管理员**（见下） | 不需要 |
| 对管理员程序有效 | ✅ | ❌（Windows 不允许低权限进程往高权限窗口注入） |
| 状态 | DLL 已编译、**COM 接口已验证**；注册差一次 UAC 确认 | 已编译；**本机无法端到端验证**（见「没能验证的部分」） |

---

## 一、TSF 版（正统、推荐）

### 它是什么

一个 COM 进程内服务器（`huiwen_ime.dll`），实现 TSF 的
`ITfTextInputProcessor` / `ITfKeyEventSink` / `ITfThreadMgrEventSink`。
注册后出现在语言栏里，被任意程序（微信 / Word / 浏览器）加载，
接系统真实按键，把洄文字形通过 `ITfInsertAtSelection` 写进文档。

3000 条词表**编进二进制**（`hwdata.h`，由 `tools/hwmake_tsf_data.py` 生成），
所以部署只有一个 dll，不会「找不到词表」。

### 已经验证的（不需要管理员）

```powershell
& .\huiwen\tsf\out\hwimetool.exe selftest
```

```
CoCreateInstance(CLSID_HuiwenTextService, ITfTextInputProcessor) -> 0x00000000 成功
  QueryInterface(ITfKeyEventSink)      -> 0x00000000 成功
  QueryInterface(ITfThreadMgrEventSink) -> 0x00000000 成功
结论：文本服务是合格的 COM 对象，接口齐全。
```

这一条证明：DLL 能被系统加载、`DllGetClassObject` 正常、类工厂造得出对象、
TSF 要求的三个接口都实现了。

### 安装：需要一次管理员确认

**这不是偷懒，是 Windows 的安全边界。** 实测依据：

- TSF 的语言档案存在 `HKLM\SOFTWARE\Microsoft\CTF\TIP\{CLSID}\...`（机器级）
- 非管理员写 HKLM 该键 → **错误码 5（拒绝访问）**
- 试过写到 `HKCU\...\CTF\TIP\...`：**写成功了，但 TSF 根本不读**
  （`GetLanguageProfileDescription` 仍返回 `E_FAIL`，`EnumLanguageProfiles` 里也没有我们）
- 结论：注册输入法必须提权，没有绕法

所以安装脚本会自己请求提权，你只要在 UAC 窗口点「是」：

```
双击（或右键"以管理员身份运行"）  huiwen\tsf\install_ime.bat
```

脚本做三件事：编译 → 复制 dll 到 `%LOCALAPPDATA%\GalHuiwenIME` →
调 `DllRegisterServer` 注册 → 验证。

装完按 **Win+Space**（或点任务栏语言栏）选到「洄文输入法」，
在记事本里敲 `za`，候选窗出现，按 `1` 上屏。

### 用法

| 操作 | 效果 |
| --- | --- |
| 敲字母 | 进缓冲区，出候选（声调可选，打了更准） |
| `1`–`9` | 选第 N 个候选 |
| `空格` / `回车` | 选第一个 |
| `退格` | 删一个字母 |
| `Esc` | 取消 |
| **Ctrl+Shift+H** | 开/关本输入法 |

### 卸载

```
右键"以管理员身份运行"后执行：  python huiwen\tsf\hwimeinstall.py uninstall
```

---

## 二、钩子版（免管理员）

`洄文输入法-免安装版.exe`。用 `WH_KEYBOARD_LL` 拦按键，用
`SendInput(KEYEVENTF_UNICODE)` 把字打进当前焦点窗口。双击即用，不写注册表。

适合：没有管理员权限、或者只是想在记事本里试试。

限制：**对「以管理员身份运行的程序」无效** —— Windows 的 UIPI 不允许
低权限进程往高权限窗口注入输入。这是设计使然，不是 bug。

```powershell
.\huiwen\hook\out\洄文输入法-免安装版.exe        # 正常用
.\huiwen\hook\out\洄文输入法-免安装版.exe --log <文件>   # 带诊断日志
```

### 怎么自己测它

```powershell
# 1) 起一个靶子窗口（会把编辑框内容写到文件）
.\huiwen\hook\out\huiwen_target.exe out.txt 60

# 2) 另开一个窗口起输入法
.\huiwen\hook\out\洄文输入法-免安装版.exe

# 3) 点回靶子窗口，敲 za，再按 1 —— 编辑框里应出现一个洄文字形
```

---

## 三、没能验证的部分（如实交代）

**钩子版在本机无法端到端验证。** 证据链：

1. 同进程里装 `WH_KEYBOARD_LL`，`SetWindowsHookEx` 返回有效句柄、错误码 0
2. `SendInput` 报告成功发出 2 个事件、错误码 0
3. **钩子命中 0 次**
4. 补充判别：同时装 `WH_KEYBOARD_LL` 与 `WH_MOUSE_LL`，发键盘 + 发鼠标
   → **两者都命中 0 次**
5. 靶子窗口编辑框收到 **0 个字符**（注入的按键也没到应用层）
6. 会话检查：会话 ID 1 = 活动控制台会话，桌面名为 `Default`
   （不是锁屏导致的）

结论：**这个运行环境不把事件派发给低级钩子，注入的输入也到不了应用层**
（DSH 的进程隔离）。所以「钩子版能不能打得出字」在这里测不出来 ——
我没有拿"编译通过"冒充"能用"。

**TSF 版不受影响**：它接的是系统真实按键，不依赖注入。
COM 部分已经验证；装上之后能否打字，需要你实际敲一下确认 ——
这一点我也不替你断言。

---

## 四、许可证与依赖

- 编译需要 Visual Studio Build Tools（含 C++ 工作负载），本机已装 VS 2022 BuildTools
- 编译脚本会自动找 `vcvars64.bat`
- 数据表由 `tools/hwmake_tsf_data.py` 从 `lexicon.tsv` 生成（改了词表要重跑）

```powershell
# 编译两个版本
python tools/hwmake_tsf_data.py                                    # 重生成数据表
powershell -NoProfile -ExecutionPolicy Bypass -File tsf/build.ps1   # TSF dll
powershell -NoProfile -ExecutionPolicy Bypass -File tsf/build_tool.ps1  # 诊断工具
powershell -NoProfile -ExecutionPolicy Bypass -File hook/build_hook.ps1 # 钩子版
```

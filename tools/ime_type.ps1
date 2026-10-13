param([Parameter(Mandatory = $true)][long]$Hwnd, [Parameter(Mandatory = $true)][string]$Keys, [string]$Log = "", [int]$DelayMs = 45)
# Types through the real Windows Korean IME into one window (used by game/tests/ime_typing.gd).
# $Keys is what the fingers press on a 2-beolsik keyboard: a-z (Shift for capitals: ㄲ ㄸ ㅃ ㅆ ㅉ ㅒ ㅖ),
# space, '>' Enter, '<' Backspace, '.' a short pause. "gksrmf dlqfur" types 한글 입력.
# The window is brought forward, switched to the Korean layout in Hangul mode, and every key is sent
# with SendInput only while that window is still in front, so nothing lands in another program.
# Exit 0 typed; 2 the window could not be brought forward or lost the front; 3 no Korean IME.
if (-not ('ImeTypeDriver' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
public static class ImeTypeDriver {
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("imm32.dll")] static extern IntPtr ImmGetDefaultIMEWnd(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder text, int size);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    const uint WM_INPUTLANGCHANGEREQUEST = 0x50, WM_IME_CONTROL = 0x283;
    const int IMC_GETCONVERSIONMODE = 1, IMC_SETCONVERSIONMODE = 2, IMC_GETOPENSTATUS = 5, IMC_SETOPENSTATUS = 6;
    const uint KEYUP = 2;
    public static string Report = "";

    static bool Front(IntPtr h) { return GetForegroundWindow() == h; }

    // Which window took the front (for the report).
    static string FrontName() {
        IntPtr f = GetForegroundWindow();
        var title = new System.Text.StringBuilder(128);
        GetWindowText(f, title, 128);
        uint pid; GetWindowThreadProcessId(f, out pid);
        string process = "?";
        try { process = System.Diagnostics.Process.GetProcessById((int)pid).ProcessName; } catch (Exception) {}
        return process + " '" + title + "'";
    }

    public static bool Forward(IntPtr h) {
        if (Front(h)) return true;
        uint mine = GetCurrentThreadId();
        uint front = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero);
        uint target = GetWindowThreadProcessId(h, IntPtr.Zero);
        AttachThreadInput(mine, front, true); AttachThreadInput(mine, target, true);
        BringWindowToTop(h); SetForegroundWindow(h);
        AttachThreadInput(mine, front, false); AttachThreadInput(mine, target, false);
        for (int i = 0; i < 40 && !Front(h); i++) Thread.Sleep(25);
        return Front(h);
    }

    static void Key(byte vk, bool up) { keybd_event(vk, (byte)MapVirtualKey(vk, 0), up ? KEYUP : 0, UIntPtr.Zero); }

    public static int Run(IntPtr h, string keys, int delay) {
        if (!Forward(h)) { Report = "not in front: " + FrontName(); return 2; }
        uint thread = GetWindowThreadProcessId(h, IntPtr.Zero);
        PostMessage(h, WM_INPUTLANGCHANGEREQUEST, IntPtr.Zero, (IntPtr)0x04120412);
        for (int i = 0; i < 40 && ((long)GetKeyboardLayout(thread) & 0xFFFF) != 0x0412; i++) Thread.Sleep(25);
        if (((long)GetKeyboardLayout(thread) & 0xFFFF) != 0x0412) { Report = "korean layout not active"; return 3; }
        IntPtr ime = ImmGetDefaultIMEWnd(h);
        IntPtr wasOpen = SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_GETOPENSTATUS, IntPtr.Zero);
        IntPtr wasMode = SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_GETCONVERSIONMODE, IntPtr.Zero);
        SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_SETOPENSTATUS, (IntPtr)1);
        SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_SETCONVERSIONMODE, (IntPtr)1);
        Thread.Sleep(80);
        long mode = (long)SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_GETCONVERSIONMODE, IntPtr.Zero);
        Report = "hangul_mode=" + ((mode & 1) != 0) + " ";
        int code = 0;
        foreach (char c in keys) {
            if (!Front(h)) { Report += "lost the front to " + FrontName(); code = 2; break; }
            if (c == '.') { Thread.Sleep(250); continue; }
            byte vk; bool shift = false;
            if (c >= 'a' && c <= 'z') vk = (byte)(c - 'a' + 'A');
            else if (c >= 'A' && c <= 'Z') { vk = (byte)c; shift = true; }
            else if (c == ' ') vk = 0x20;
            else if (c == '>') vk = 0x0D;
            else if (c == '<') vk = 0x08;
            else continue;
            if (shift) Key(0x10, false);
            Key(vk, false); Thread.Sleep(12); Key(vk, true);
            if (shift) Key(0x10, true);
            Thread.Sleep(delay);
        }
        SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_SETCONVERSIONMODE, wasMode);
        SendMessage(ime, WM_IME_CONTROL, (IntPtr)IMC_SETOPENSTATUS, wasOpen);
        if (code == 0) Report += "typed";
        return code;
    }
}
'@
}
$code = [ImeTypeDriver]::Run([IntPtr]$Hwnd, $Keys, $DelayMs)
if ($Log) { [IO.File]::WriteAllText($Log, "$code $([ImeTypeDriver]::Report)") }
exit $code

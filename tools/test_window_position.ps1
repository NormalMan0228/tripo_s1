param([string]$Monitor = $(if ($env:TRIPOTHON_TEST_MONITOR) { $env:TRIPOTHON_TEST_MONITOR } else { 'BNQ' }), [int]$Width = 1280, [int]$Height = 800)
# Where windowed test runs open: centred on the monitor whose hardware id contains $Monitor
# (default BNQ, the BenQ screen on the developer PC). Prints "X,Y" for Godot's --position, or
# nothing when no such monitor is connected (Godot then uses its default screen).
Add-Type -AssemblyName System.Windows.Forms
if (-not ('TestWindowDisplay' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TestWindowDisplay {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct DISPLAY_DEVICE {
        public int cb;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string DeviceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceString;
        public int StateFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceID;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceKey;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern bool EnumDisplayDevices(string device, uint index, ref DISPLAY_DEVICE info, uint flags);
    public static string MonitorIds(string adapter) {
        var ids = "";
        var info = new DISPLAY_DEVICE();
        info.cb = Marshal.SizeOf(info);
        for (uint i = 0; EnumDisplayDevices(adapter, i, ref info, 0); i++) { ids += info.DeviceID + ";"; info.cb = Marshal.SizeOf(info); }
        return ids;
    }
}
'@
}
foreach ($screen in [System.Windows.Forms.Screen]::AllScreens) {
    if ([TestWindowDisplay]::MonitorIds($screen.DeviceName) -match [regex]::Escape($Monitor)) {
        $b = $screen.Bounds
        $x = $b.X + [Math]::Max(0, [int](($b.Width - $Width) / 2))
        $y = $b.Y + [Math]::Max(0, [int](($b.Height - $Height) / 2))
        Write-Output ("{0},{1}" -f $x, $y)
        return
    }
}

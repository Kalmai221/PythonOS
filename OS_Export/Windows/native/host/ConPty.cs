// A pseudo console (ConPTY): runs a program as if it had a real Windows console, but we hold both ends of the pipes.
// That is what lets PythonOS.exe show the program's output in its own window instead of the default Command Prompt.
// Needs Windows 10 version 1809 or newer. Written in C# 5 so it builds with the compiler that ships with Windows.
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using Microsoft.Win32.SafeHandles;

namespace PythonOS
{
    public sealed class ConPtySession : IDisposable
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct COORD { public short X; public short Y; }

        [StructLayout(LayoutKind.Sequential)]
        private struct STARTUPINFO
        {
            public int cb;
            public IntPtr lpReserved;
            public IntPtr lpDesktop;
            public IntPtr lpTitle;
            public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
            public short wShowWindow, cbReserved2;
            public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct STARTUPINFOEX
        {
            public STARTUPINFO StartupInfo;
            public IntPtr lpAttributeList;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_INFORMATION
        {
            public IntPtr hProcess, hThread;
            public int dwProcessId, dwThreadId;
        }

        private const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
        private const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
        private static readonly IntPtr PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = (IntPtr)0x00020016;

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CreatePipe(out IntPtr hReadPipe, out IntPtr hWritePipe, IntPtr lpPipeAttributes, uint nSize);

        [DllImport("kernel32.dll")]
        private static extern int CreatePseudoConsole(COORD size, IntPtr hInput, IntPtr hOutput, uint dwFlags, out IntPtr phPC);

        [DllImport("kernel32.dll")]
        private static extern int ResizePseudoConsole(IntPtr hPC, COORD size);

        [DllImport("kernel32.dll")]
        private static extern void ClosePseudoConsole(IntPtr hPC);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool InitializeProcThreadAttributeList(IntPtr lpAttributeList, int dwAttributeCount, int dwFlags, ref IntPtr lpSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool UpdateProcThreadAttribute(IntPtr lpAttributeList, uint dwFlags, IntPtr attribute, IntPtr lpValue,
            IntPtr cbSize, IntPtr lpPreviousValue, IntPtr lpReturnSize);

        [DllImport("kernel32.dll")]
        private static extern void DeleteProcThreadAttributeList(IntPtr lpAttributeList);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool CreateProcessW(string lpApplicationName, StringBuilder lpCommandLine, IntPtr lpProcessAttributes,
            IntPtr lpThreadAttributes, bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory,
            ref STARTUPINFOEX lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetExitCodeProcess(IntPtr hProcess, out uint lpExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr hProcess, uint uExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private IntPtr pseudoConsole = IntPtr.Zero;
        private IntPtr processHandle = IntPtr.Zero;
        private IntPtr attributeList = IntPtr.Zero;
        private FileStream input;     // what we type into the program
        private FileStream output;    // what the program prints
        private bool disposed;

        /// <summary>Raw bytes the program printed (UTF-8 and escape sequences), on a background thread.</summary>
        public event Action<byte[], int> Output;
        /// <summary>The program ended; the argument is its exit code.</summary>
        public event Action<int> Exited;

        [StructLayout(LayoutKind.Sequential)]
        private struct OSVERSIONINFO
        {
            public int dwOSVersionInfoSize;
            public int dwMajorVersion, dwMinorVersion, dwBuildNumber, dwPlatformId;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
            public string szCSDVersion;
        }

        [DllImport("ntdll.dll")]
        private static extern int RtlGetVersion(ref OSVERSIONINFO info);

        /// <summary>
        /// Windows 10 version 1809 (build 17763) or newer. Environment.OSVersion cannot be trusted here: without a manifest that
        /// declares Windows 10 it reports an older version, so ask the kernel directly.
        /// </summary>
        public static bool IsSupported()
        {
            try
            {
                OSVERSIONINFO info = new OSVERSIONINFO();
                info.dwOSVersionInfoSize = Marshal.SizeOf(typeof(OSVERSIONINFO));
                if (RtlGetVersion(ref info) != 0) return true;       // cannot tell: let the pseudo console call decide
                return info.dwMajorVersion > 10 || (info.dwMajorVersion == 10 && info.dwBuildNumber >= 17763);
            }
            catch (Exception) { return true; }
        }

        public void Start(string commandLine, string workingDirectory, int columns, int rows)
        {
            IntPtr inRead, inWrite, outRead, outWrite;
            if (!CreatePipe(out inRead, out inWrite, IntPtr.Zero, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
            if (!CreatePipe(out outRead, out outWrite, IntPtr.Zero, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());

            COORD size = new COORD();
            size.X = (short)Math.Max(1, columns);
            size.Y = (short)Math.Max(1, rows);
            int hr = CreatePseudoConsole(size, inRead, outWrite, 0, out pseudoConsole);
            if (hr != 0) throw new Win32Exception(hr, "The pseudo console could not be created.");
            CloseHandle(inRead);       // the pseudo console owns its ends now
            CloseHandle(outWrite);

            IntPtr listSize = IntPtr.Zero;
            InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref listSize);
            attributeList = Marshal.AllocHGlobal(listSize);
            if (!InitializeProcThreadAttributeList(attributeList, 1, 0, ref listSize)) throw new Win32Exception(Marshal.GetLastWin32Error());
            if (!UpdateProcThreadAttribute(attributeList, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, pseudoConsole,
                (IntPtr)IntPtr.Size, IntPtr.Zero, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());

            STARTUPINFOEX startup = new STARTUPINFOEX();
            startup.StartupInfo.cb = Marshal.SizeOf(typeof(STARTUPINFOEX));
            startup.lpAttributeList = attributeList;
            PROCESS_INFORMATION info;
            StringBuilder cmd = new StringBuilder(commandLine);
            if (!CreateProcessW(null, cmd, IntPtr.Zero, IntPtr.Zero, false, EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
                IntPtr.Zero, workingDirectory, ref startup, out info))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "The program could not be started.");
            CloseHandle(info.hThread);
            processHandle = info.hProcess;

            input = new FileStream(new SafeFileHandle(inWrite, true), FileAccess.Write, 4096, false);
            output = new FileStream(new SafeFileHandle(outRead, true), FileAccess.Read, 4096, false);

            Thread reader = new Thread(ReadLoop);
            reader.IsBackground = true;
            reader.Name = "pty-read";
            reader.Start();
            Thread waiter = new Thread(WaitLoop);
            waiter.IsBackground = true;
            waiter.Name = "pty-wait";
            waiter.Start();
        }

        private void ReadLoop()
        {
            byte[] buffer = new byte[16384];
            try
            {
                while (true)
                {
                    int n = output.Read(buffer, 0, buffer.Length);
                    if (n <= 0) break;
                    Action<byte[], int> handler = Output;
                    if (handler != null)
                    {
                        byte[] copy = new byte[n];
                        Buffer.BlockCopy(buffer, 0, copy, 0, n);
                        handler(copy, n);
                    }
                }
            }
            catch (Exception) { /* the pipe closed: the program is gone */ }
        }

        private void WaitLoop()
        {
            WaitForSingleObject(processHandle, 0xFFFFFFFF);
            uint code;
            GetExitCodeProcess(processHandle, out code);
            // Let the reader drain what is left, then say we are done
            Thread.Sleep(300);
            Action<int> handler = Exited;
            if (handler != null) handler((int)code);
        }

        public void Write(string text)
        {
            if (disposed || input == null) return;
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            try
            {
                input.Write(bytes, 0, bytes.Length);
                input.Flush();
            }
            catch (Exception) { /* the program has ended */ }
        }

        public void Resize(int columns, int rows)
        {
            if (disposed || pseudoConsole == IntPtr.Zero) return;
            COORD size = new COORD();
            size.X = (short)Math.Max(1, columns);
            size.Y = (short)Math.Max(1, rows);
            ResizePseudoConsole(pseudoConsole, size);
        }

        public void Kill()
        {
            if (processHandle != IntPtr.Zero) TerminateProcess(processHandle, 1);
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            try { if (input != null) input.Dispose(); } catch (Exception) { }
            if (pseudoConsole != IntPtr.Zero)
            {
                IntPtr pc = pseudoConsole;
                pseudoConsole = IntPtr.Zero;
                // Closing can block until the output is drained, so do it off the UI thread
                Thread closer = new Thread(delegate () { ClosePseudoConsole(pc); });
                closer.IsBackground = true;
                closer.Start();
            }
            if (attributeList != IntPtr.Zero)
            {
                DeleteProcThreadAttributeList(attributeList);
                Marshal.FreeHGlobal(attributeList);
                attributeList = IntPtr.Zero;
            }
            if (processHandle != IntPtr.Zero) { CloseHandle(processHandle); processHandle = IntPtr.Zero; }
        }
    }
}

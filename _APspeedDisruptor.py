import ctypes
import os
import sys
import time
import random
from datetime import datetime

# Force Working Directory to Script Folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# Self-Elevating Admin Wrapper
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    print("Requesting Administrator privileges to hook into FSUIPC7...")
    script_path = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script_path}"', SCRIPT_DIR, 1)
    sys.exit(0)


class FSUIPC7Direct:
    """Pure Python FSUIPC7 IPC connector using Windows Shared Memory (ctypes)."""
    FILE_MAP_WRITE = 0x0002
    WM_USER = 0x0400

    def __init__(self):
        self.hwnd = None
        self.h_map = None
        self.p_view = None
        self.msg_id = None

    def connect(self):
        # 1. Find FSUIPC7 Window
        self.hwnd = ctypes.windll.user32.FindWindowA(b"FS98MAIN", None)
        if not self.hwnd:
            return False

        # 2. Register FSUIPC Message ID
        self.msg_id = ctypes.windll.user32.RegisterWindowMessageA(b"FSUIPC_MSG")
        if not self.msg_id:
            self.msg_id = self.WM_USER + 1

        # 3. Open Memory Mapping (FSUIPC64_Memory)
        self.h_map = ctypes.windll.kernel32.OpenFileMappingA(self.FILE_MAP_WRITE, False, b"FSUIPC64_Memory")
        if not self.h_map:
            self.h_map = ctypes.windll.kernel32.OpenFileMappingA(self.FILE_MAP_WRITE, False, b"FSUIPC_Memory")

        if not self.h_map:
            return False

        # 4. Map View of Memory
        self.p_view = ctypes.windll.kernel32.MapViewOfFile(self.h_map, self.FILE_MAP_WRITE, 0, 0, 0)
        return bool(self.p_view)

    def send_rpn(self, rpn_str: str):
        """Sends RPN Calculator Code string to Offset 0x0D70."""
        if not self.p_view:
            return

        code_bytes = rpn_str.encode("utf-8") + b"\x00"
        data_len = len(code_bytes)

        # FSUIPC Write Data Block Header
        # Header size = 16 bytes: [Total Data Size, Error, Offset (0x0D70), Data Size]
        header = (ctypes.c_uint32 * 4)(
            16 + data_len + 8,
            0,
            0x0D70,
            data_len
        )

        # Write Header and String to Shared Memory
        ctypes.memmove(self.p_view, header, 16)
        ctypes.memmove(self.p_view + 16, code_bytes, data_len)

        # Write 8-byte Terminator (Offset 0, Size 0)
        terminator = (ctypes.c_uint32 * 2)(0, 0)
        ctypes.memmove(self.p_view + 16 + data_len, terminator, 8)

        # Send WM_IPCUIPC Message to FSUIPC7
        ctypes.windll.user32.SendMessageA(self.hwnd, self.msg_id, 1, 0)

    def close(self):
        if self.p_view:
            ctypes.windll.kernel32.UnmapViewOfFile(self.p_view)
        if self.h_map:
            ctypes.windll.kernel32.CloseHandle(self.h_map)


def main():
    print("MSFS2020 Dynamic Speed Disruptor (A310 / Pure Python FSUIPC)")
    print("Attempting to connect to FSUIPC7...")

    fsuipc = FSUIPC7Direct()
    connected = False

    for attempt in range(1, 6):
        if fsuipc.connect():
            print("-> Connected to FSUIPC7 successfully!")
            connected = True
            break
        print(f"   [Attempt {attempt}/5] Waiting for FSUIPC7.exe...")
        time.sleep(2.0)

    if not connected:
        print("\n[CONNECTION FAILED]")
        print("Ensure MSFS2020 and FSUIPC7.exe are both running.")
        input("\nPress Enter to exit...")
        return

    # Startup pause setup
    STARTUP_DELAY_SEC = 60
    print(f"\n[STARTUP PAUSE] Holding for {STARTUP_DELAY_SEC} seconds to allow cockpit setup...")

    try:
        for remaining in range(STARTUP_DELAY_SEC, 0, -1):
            sys.stdout.write(f"\r  Disruptor active in: {remaining:2d}s (Press Ctrl+C to cancel)... ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n")
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Script aborted during setup pause.")
        fsuipc.close()
        return

    # Configuration for A310 (FL120 - FL240)
    MIN_SPEED_KTS = 250
    MAX_SPEED_KTS = 315
    MIN_SPEED_DELTA = 12       # Minimum change required per event
    SEC_PER_KNOT_DELTA = 1.2   # ~30s for a 25kt shift in an A310
    MIN_PAD_SEC = 15           # Buffer hold time after target is reached
    MAX_PAD_SEC = 45

    # Initial state setup
    current_target_speed = 293
    fsuipc.send_rpn(f"{current_target_speed} (>L:A310_FCU_SPEED_SELECT_VALUE)")

    print(f"[DISRUPTOR ACTIVE]")
    print(f"  Initial AP Speed set to: {current_target_speed} kts")
    print("\nPress Ctrl+C in this window to stop.\n")

    event_count = 0
    try:
        while True:
            # 1. Pick a new speed with a meaningful delta
            new_speed = current_target_speed
            while abs(new_speed - current_target_speed) < MIN_SPEED_DELTA:
                new_speed = random.randint(MIN_SPEED_KTS, MAX_SPEED_KTS)

            speed_delta = abs(new_speed - current_target_speed)

            # 2. Calculate dynamic delay: transition time + random buffer
            transition_time = speed_delta * SEC_PER_KNOT_DELTA
            random_buffer = random.randint(MIN_PAD_SEC, MAX_PAD_SEC)
            total_interval = round(transition_time + random_buffer, 1)

            # 3. Fire RPN code to A310 FCU via FSUIPC7
            rpn_cmd = f"{new_speed} (>L:A310_FCU_SPEED_SELECT_VALUE)"
            fsuipc.send_rpn(rpn_cmd)

            now = datetime.now().strftime("%H:%M:%S")
            event_count += 1
            print(f"[{now}] Event #{event_count}: Target Speed -> {new_speed} kts (Δ {speed_delta} kts) | Holding {total_interval}s")

            current_target_speed = new_speed

            # 4. Non-blocking delay loop for responsive Ctrl+C exit
            start_hold = time.time()
            while (time.time() - start_hold) < total_interval:
                time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n\n[STOPPED] Disruptor closed after {event_count} speed changes.")
    finally:
        fsuipc.close()
        input("\nPress Enter to close this window...")

if __name__ == "__main__":
    try:
        main()
    except BaseException as err:
        print(f"\n\n[CRITICAL ERROR] The script encountered a fatal crash:")
        print(f"Details: {err}")
        input("\nPress Enter to exit...")

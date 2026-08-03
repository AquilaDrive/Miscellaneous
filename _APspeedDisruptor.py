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

# Dependency Check
try:
    import fsuipc
except ImportError:
    print("\n[ERROR] The 'fsuipc' library is not installed.")
    print("Please open Command Prompt and run: pip install fsuipc")
    input("\nPress Enter to exit...")
    sys.exit(1)


def main():
    print("MSFS2020 Dynamic Speed Disruptor (A310 / FSUIPC7)")
    print("Attempting to connect to FSUIPC7...")

    ipc = None
    for attempt in range(1, 6):
        try:
            # Initialize FSUIPC IPC Connection
            ipc = fsuipc.FSUIPC()
            print("-> Connected to FSUIPC7 successfully!")
            break
        except Exception as e:
            print(f"   [Attempt {attempt}/5] Waiting for FSUIPC7... ({e})")
            time.sleep(2.0)

    if ipc is None:
        print("\n[CONNECTION FAILED]")
        print("Ensure MSFS2020 and FSUIPC7.exe are both running.")
        input("\nPress Enter to exit...")
        return

    def send_fsuipc_rpn(rpn_code: str):
        """Sends RPN Calculator Code to MSFS via FSUIPC7 Offset 0x0D70."""
        try:
            code_bytes = rpn_code.encode("utf-8") + b"\x00"
            # 0x0D70 executes string as MSFS Calculator Code
            ipc.write([(0x0D70, f"{len(code_bytes)}s", code_bytes)])
        except Exception as err:
            print(f"[ERROR] FSUIPC write failed: {err}")

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
        ipc.close()
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
    send_fsuipc_rpn(f"{current_target_speed} (>L:A310_FCU_SPEED_SELECT_VALUE)")

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
            send_fsuipc_rpn(rpn_cmd)

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
        try:
            ipc.close()
        except Exception:
            pass
        input("\nPress Enter to close this window...")

if __name__ == "__main__":
    try:
        main()
    except BaseException as err:
        print(f"\n\n[CRITICAL ERROR] The script encountered a fatal crash:")
        print(f"Details: {err}")
        input("\nPress Enter to exit...")

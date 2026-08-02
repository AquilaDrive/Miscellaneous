import csv
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
    print("Requesting Administrator privileges to hook into MSFS2020...")
    script_path = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script_path}"', SCRIPT_DIR, 1)
    sys.exit(0)

# Dependency Check
try:
    from SimConnect import SimConnect, AircraftEvents
except ImportError:
    print("\n[ERROR] The 'SimConnect' library is not installed.")
    print("Please open Command Prompt and run: pip install SimConnect")
    input("\nPress Enter to exit...")
    sys.exit(1)


def main():
    print("MSFS2020 Dynamic Speed Disruptor")
    print("Attempting to connect to MSFS2020...")

    sm = None
    ae = None
    set_ap_speed = None
    
    for attempt in range(1, 6):
        try:
            sm = SimConnect()
            ae = AircraftEvents(sm)
            set_ap_speed = ae.find("AP_SPD_VAR_SET")
            print("-> Connected to Flight Simulator successfully!")
            break
        except Exception as e:
            print(f"   [Attempt {attempt}/5] Waiting for sim... ({e})")
            time.sleep(2.0)

    if sm is None or set_ap_speed is None:
        print("\n[CONNECTION FAILED]")
        print("Ensure MSFS2020 is running and you are inside an active flight.")
        input("\nPress Enter to exit...")
        return

    # Configuration for A310 (FL120 - FL240)
    MIN_SPEED_KTS = 250
    MAX_SPEED_KTS = 315
    MIN_SPEED_DELTA = 12       # Minimum change required per event
    SEC_PER_KNOT_DELTA = 1.2   # ~30s for a 25kt shift in an A310
    MIN_PAD_SEC = 15           # Buffer hold time after target is reached
    MAX_PAD_SEC = 45

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(SCRIPT_DIR, f"speed_events_{timestamp_str}.csv")

    headers = ["Timestamp", "Target_Speed_Kts", "Previous_Speed_Kts", "Speed_Delta_Kts", "Hold_Interval_Sec"]

    # Initial state
    current_target_speed = 293
    set_ap_speed(current_target_speed)

    with open(csv_filename, mode='w', newline='', buffering=1) as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)
        
        print(f"\n[DISRUPTOR STARTED]")
        print(f"  CSV: {os.path.basename(csv_filename)}")
        print(f"  Initial AP Speed set to: {current_target_speed} kts")
        print("\nPress Ctrl+C in this window to stop.\n")

        event_count = 0
        try:
            while not sm.quit:
                # 1. Pick a new speed with a meaningful delta
                new_speed = current_target_speed
                while abs(new_speed - current_target_speed) < MIN_SPEED_DELTA:
                    new_speed = random.randint(MIN_SPEED_KTS, MAX_SPEED_KTS)
                
                speed_delta = abs(new_speed - current_target_speed)
                
                # 2. Calculate dynamic delay: transition time + random buffer
                transition_time = speed_delta * SEC_PER_KNOT_DELTA
                random_buffer = random.randint(MIN_PAD_SEC, MAX_PAD_SEC)
                total_interval = round(transition_time + random_buffer, 1)

                # 3. Fire event to MSFS
                set_ap_speed(new_speed)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # 4. Write to CSV
                csv_writer.writerow([now, new_speed, current_target_speed, speed_delta, total_interval])
                csv_file.flush()

                event_count += 1
                print(f"[{now}] Target Speed -> {new_speed} kts (Delta: {speed_delta} kts) | Holding for {total_interval}s")

                current_target_speed = new_speed

                # 5. Non-blocking sleep loop for clean Ctrl+C interruption
                start_hold = time.time()
                while (time.time() - start_hold) < total_interval:
                    time.sleep(0.5)

        except KeyboardInterrupt:
            print(f"\n\n[STOPPED] Logged {event_count} speed changes to CSV.")
        finally:
            input("\nPress Enter to close this window...")

if __name__ == "__main__":
    try:
        main()
    except BaseException as err:
        print(f"\n\n[CRITICAL ERROR] The script encountered a fatal crash:")
        print(f"Details: {err}")
        input("\nPress Enter to exit...")

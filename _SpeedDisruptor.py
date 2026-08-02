import csv
import ctypes
import os
import sys
import time
import random
from datetime import datetime

# ==============================================================================
# 1. FORCE WORKING DIRECTORY TO SCRIPT FOLDER
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# ==============================================================================
# 2. SELF-ELEVATING ADMIN WRAPPER
# ==============================================================================
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

# ==============================================================================
# 3. DEPENDENCY CHECK
# ==============================================================================
try:
    from SimConnect import SimConnect, AircraftEvents
except ImportError:
    print("\n[ERROR] The 'SimConnect' library is not installed.")
    print("Please open Command Prompt and run: pip install SimConnect")
    input("\nPress Enter to exit...")
    sys.exit(1)


def main():
    print("==========================================")
    print("   MSFS2020 Dynamic Speed Disruptor")
    print("==========================================")
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
    MIN_SPEED_DELTA = 12       # Ensure new speed is at least 12 kts different from current
    SEC_PER_KNOT_DELTA = 1.2   # ~30s required for a 25kt change in an A310
    MIN_PAD_SEC = 15           # Random hold time after speed is reached
    MAX_PAD_SEC = 45

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(SCRIPT_DIR, f"speed_events_{timestamp_str}.csv")
    log_filename = os.path.join(SCRIPT_DIR, f"speed_events_{timestamp_str}.log")

    headers = ["Timestamp", "Target_Speed_Kts", "Previous_Speed_Kts", "Speed_Delta_Kts", "Hold_Interval_Sec"]

    log_header = f"{'Timestamp':<23} | {'Target (kts)':>12} | {'Prev (kts)':>10} | {'Delta':>7} | {'Hold (s)':>8}\n"
    log_divider = "-" * (len(log_header) - 1) + "\n"

    # Initial state
    current_target_speed = 293
    # Set initial baseline speed
    set_ap_speed(current_target_speed)

    with open(csv_filename, mode='w', newline='', buffering=1) as csv_file, \
         open(log_filename, mode='w', buffering=1) as log_file:
        
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)
        
        log_file.write(log_header)
        log_file.write(log_divider)
        
        print(f"\n[DISRUPTOR STARTED]")
        print(f"  CSV: {os.path.basename(csv_filename)}")
        print(f"  LOG: {os.path.basename(log_filename)}")
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

                # 4. Write to CSV and LOG
                csv_writer.writerow([now, new_speed, current_target_speed, speed_delta, total_interval])
                
                log_line = (
                    f"{now:<23} | "
                    f"{new_speed:>12} | "
                    f"{current_target_speed:>10} | "
                    f"{speed_delta:>7} | "
                    f"{total_interval:>8.1f}\n"
                )
                log_file.write(log_line)
                csv_file.flush()
                log_file.flush()

                event_count += 1
                print(f"[{now}] Target Speed -> {new_speed} kts (Delta: {speed_delta} kts) | Holding for {total_interval}s")

                current_target_speed = new_speed

                # 5. Non-blocking sleep loop to allow smooth Ctrl+C interruption
                start_hold = time.time()
                while (time.time() - start_hold) < total_interval:
                    time.sleep(0.5)

        except KeyboardInterrupt:
            print(f"\n\n[STOPPED] Logged {event_count} speed changes to CSV and LOG files.")
        finally:
            input("\nPress Enter to close this window...")

if __name__ == "__main__":
    try:
        main()
    except BaseException as err:
        print(f"\n\n[CRITICAL ERROR] The script encountered a fatal crash:")
        print(f"Details: {err}")
        input("\nPress Enter to exit...")

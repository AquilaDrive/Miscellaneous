import csv
import ctypes
import os
import sys
import time
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
    from SimConnect import SimConnect, AircraftRequests
except ImportError:
    print("\n[ERROR] The 'SimConnect' library is not installed.")
    print("Please open Command Prompt and run: pip install SimConnect")
    input("\nPress Enter to exit...")
    sys.exit(1)


def main():
    print("==========================================")
    print("   MSFS2020 Dual Telemetry Logger")
    print("==========================================")
    print("Attempting to connect to MSFS2020...")

    sm = None
    aq = None
    
    for attempt in range(1, 6):
        try:
            sm = SimConnect()
            aq = AircraftRequests(sm) 
            print("-> Connected to Flight Simulator successfully!")
            break
        except Exception as e:
            print(f"   [Attempt {attempt}/5] Waiting for sim... ({e})")
            time.sleep(2.0)

    if sm is None or aq is None:
        print("\n[CONNECTION FAILED]")
        print("Troubleshooting steps:")
        print("  1. Make sure you are spawned inside an ACTIVE flight (not main menu).")
        print("  2. Ensure MSFS2020 is fully loaded on screen.")
        input("\nPress Enter to exit...")
        return

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(SCRIPT_DIR, f"flight_telemetry_{timestamp_str}.csv")
    log_filename = os.path.join(SCRIPT_DIR, f"flight_telemetry_{timestamp_str}.log")

    headers = [
        "Timestamp", "Altitude_Ft", "VerticalSpeed_FPM", 
        "Pitch_Deg", "Bank_Deg", "Heading_Deg", "Yoke_Roll_Pct", "Yoke_Pitch_Pct", "Rudder_Pct"
    ]

    # Fixed-width header string for the human-readable .log file
    log_header = (
        f"{'Timestamp':<23} | {'Alt (ft)':>8} | {'VS (fpm)':>8} | "
        f"{'Pitch':>7} | {'Bank':>7} | {'Hdg':>5} | "
        f"{'Roll_In':>7} | {'Ptch_In':>7} | {'Rud_In':>7}\n"
    )
    log_divider = "-" * (len(log_header) - 1) + "\n"

    RAD_TO_DEG = 180.0 / 3.1415926535

    # Open both CSV and LOG files simultaneously
    with open(csv_filename, mode='w', newline='', buffering=1) as csv_file, \
         open(log_filename, mode='w', buffering=1) as log_file:
        
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)
        
        log_file.write(log_header)
        log_file.write(log_divider)
        
        print(f"\n[LOGGING STARTED]")
        print(f"  CSV: {os.path.basename(csv_filename)}")
        print(f"  LOG: {os.path.basename(log_filename)}")
        print("\nPress Ctrl+C in this window when finished flying.\n")
        
        row_count = 0
        try:
            while not sm.quit:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                alt = aq.get("INDICATED_ALTITUDE")
                vs = aq.get("VERTICAL_SPEED")
                pitch_raw = aq.get("PLANE_PITCH_DEGREES")
                bank_raw = aq.get("PLANE_BANK_DEGREES")
                hdg_raw = aq.get("PLANE_HEADING_DEGREES_MAGNETIC")
                
                yoke_x = aq.get("YOKE_X_POSITION")
                yoke_y = aq.get("YOKE_Y_POSITION")
                rudder = aq.get("RUDDER_PEDAL_POSITION")
                
                alt_ft = alt if alt is not None else 0.0
                vs_fpm = vs if vs is not None else 0.0
                p_deg = (pitch_raw * RAD_TO_DEG) if pitch_raw is not None else 0.0
                b_deg = (bank_raw * RAD_TO_DEG) if bank_raw is not None else 0.0
                hdg_deg = ((hdg_raw * RAD_TO_DEG) % 360) if hdg_raw is not None else 0.0
                
                roll_input = yoke_x if yoke_x is not None else 0.0
                pitch_input = yoke_y if yoke_y is not None else 0.0
                rudder_input = rudder if rudder is not None else 0.0

                # 1. Write clean machine-parsable CSV row
                csv_writer.writerow([
                    now,
                    round(alt_ft, 1),
                    round(vs_fpm, 1),
                    round(p_deg, 2),
                    round(b_deg, 2),
                    round(hdg_deg, 1),
                    round(roll_input, 2),
                    round(pitch_input, 2),
                    round(rudder_input, 2)
                ])
                
                # 2. Write aligned fixed-width LOG row
                formatted_log_line = (
                    f"{now:<23} | "
                    f"{alt_ft:>8.1f} | "
                    f"{vs_fpm:>8.1f} | "
                    f"{p_deg:>7.2f} | "
                    f"{b_deg:>7.2f} | "
                    f"{hdg_deg:>5.1f} | "
                    f"{roll_input:>7.2f} | "
                    f"{pitch_input:>7.2f} | "
                    f"{rudder_input:>7.2f}\n"
                )
                log_file.write(formatted_log_line)
                
                # Ensure data hits disk instantly
                csv_file.flush()
                log_file.flush()
                
                row_count += 1
                
                print(
                    f"\r> Logging... Rows: {row_count:<5} | Alt: {round(alt_ft):>5}ft | Hdg: {round(hdg_deg):>3}° | Pitch: {round(p_deg, 1):>5}°", 
                    end="", 
                    flush=True
                )
                
                time.sleep(0.25)
                
        except KeyboardInterrupt:
            print(f"\n\n[STOPPED] Saved {row_count} rows to both .csv and .log files.")
        finally:
            input("\nPress Enter to close this window...")

if __name__ == "__main__":
    try:
        main()
    except BaseException as err:
        print(f"\n\n[CRITICAL ERROR] The script encountered a fatal crash:")
        print(f"Details: {err}")
        input("\nPress Enter to exit...")

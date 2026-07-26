import csv
from datetime import datetime
import os
import random
import sys
import time

try:
    import pyttsx3
except ImportError:
    print("\n[ERROR] 'pyttsx3' library is missing.")
    print("Please run: pip install pyttsx3")
    input("\nPress Enter to exit...")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

ICAO_DIGITS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "tree",
    "4": "fower",
    "5": "fife",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "niner",
}


def speak(text):
    print(f"\n[ATC TRANSMISSION] {text}")
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"[TTS ERROR] Failed to synthesize speech: {e}")


def format_heading_speech(hdg):
    return " ".join([ICAO_DIGITS[d] for d in f"{hdg:03d}"])


def format_altitude_speech(alt):
    thousands = alt // 1000
    hundreds = (alt % 1000) // 100
    parts = []

    if thousands >= 10:
        digits_str = " ".join([ICAO_DIGITS[d] for d in str(thousands)])
        parts.append(f"{digits_str} thousand")
    elif thousands > 0:
        parts.append(f"{ICAO_DIGITS[str(thousands)]} thousand")

    if hundreds > 0:
        parts.append(f"{ICAO_DIGITS[str(hundreds)]} hundred")

    return " ".join(parts)


def format_vsi_speech(vsi):
    if vsi >= 1000:
        return f"{ICAO_DIGITS[str(vsi // 1000)]} thousand"
    return f"{ICAO_DIGITS[str(vsi // 100)]} hundred"


def generate_target(current_hdg, current_alt):
    new_hdg = random.choice(range(10, 370, 10))
    hdg_diff = abs(new_hdg - current_hdg)
    if hdg_diff > 180:
        hdg_diff = 360 - hdg_diff

    hdg_speech = format_heading_speech(new_hdg)

    if random.random() < 0.6:
        possible_alts = [
            a for a in range(12000, 22500, 500) if a != current_alt
        ]
        new_alt = random.choice(possible_alts)
        alt_diff = abs(new_alt - current_alt)

        if alt_diff >= 2000:
            vsi = random.choice([1000, 1200, 1500])
        elif alt_diff >= 1000:
            vsi = random.choice([700, 1000])
        else:
            vsi = random.choice([500, 700])

        alt_speech = format_altitude_speech(new_alt)
        vsi_speech = format_vsi_speech(vsi)

        if new_alt > current_alt:
            alt_cmd = f"climb and maintain {alt_speech} feet, vertical speed {vsi_speech} feet per minute."
        else:
            alt_cmd = f"descend and maintain {alt_speech} feet, vertical speed {vsi_speech} feet per minute."

        transit_time = int((alt_diff / vsi) * 60) + random.randint(15, 30)
    else:
        new_alt = current_alt
        vsi = 0
        alt_speech = format_altitude_speech(current_alt)
        alt_cmd = f"maintain level flight at {alt_speech} feet."
        transit_time = random.randint(35, 65)

    turn_time = int(hdg_diff / 3.0) + random.randint(10, 20)
    required_wait = max(transit_time, turn_time, 35)

    command_text = f"Fly heading {hdg_speech}, {alt_cmd}"
    return command_text, new_hdg, new_alt, vsi, required_wait


def log_event(
    csv_writer, csv_file, log_file, timestamp, event_type, hdg, alt, vsi, text
):
    csv_writer.writerow([timestamp, event_type, f"{hdg:03d}", alt, vsi, text])
    log_line = f"{timestamp:<23} | {event_type:<12} | {hdg:03d} | {alt:>8} | {vsi:>8} | {text}\n"
    log_file.write(log_line)
    csv_file.flush()
    log_file.flush()


def main():
    print("==========================================")
    print("   ICAO ATC Target Generator + Logging")
    print("==========================================")

    current_alt = 16500
    current_hdg = 0

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(
        SCRIPT_DIR, f"atc_events_{timestamp_str}.csv"
    )
    log_filename = os.path.join(
        SCRIPT_DIR, f"atc_events_{timestamp_str}.log"
    )

    headers = [
        "Timestamp",
        "Event_Type",
        "Target_Hdg",
        "Target_Alt_Ft",
        "Target_VSI_FPM",
        "Command_Spoken",
    ]
    log_header = f"{'Timestamp':<23} | {'Event_Type':<12} | {'Hdg':>3} | {'Alt (ft)':>8} | {'VSI (fpm)':>8} | Command Spoken\n"
    log_divider = "-" * 110 + "\n"

    with open(csv_filename, mode="w", newline="", buffering=1) as csv_file, open(
        log_filename, mode="w", buffering=1
    ) as log_file:

        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)
        log_file.write(log_header)
        log_file.write(log_divider)

        print("\n[LOGGING STARTED]")
        print(f"  CSV: {os.path.basename(csv_filename)}")
        print(f"  LOG: {os.path.basename(log_filename)}\n")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        init_msg = f"Control online. Initial altitude {format_altitude_speech(current_alt)} feet. Standby for vectoring."

        log_event(
            csv_writer,
            csv_file,
            log_file,
            now,
            "INIT_STATE",
            current_hdg,
            current_alt,
            0,
            init_msg,
        )
        speak(init_msg)

        # Fixed 15-second standby buffer before first command
        INITIAL_STANDBY_SEC = 15
        print(
            f"\n[STANDBY] First ATC vector in {INITIAL_STANDBY_SEC} seconds..."
        )
        time.sleep(INITIAL_STANDBY_SEC)

        try:
            while True:
                # 1. Generate target
                command, current_hdg, current_alt, vsi, wait_time = (
                    generate_target(current_hdg, current_alt)
                )

                # 2. Log & Speak IMMEDIATELY
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_event(
                    csv_writer,
                    csv_file,
                    log_file,
                    now,
                    "ATC_TARGET",
                    current_hdg,
                    current_alt,
                    vsi,
                    command,
                )
                speak(command)

                # 3. Sleep WHILE you perform the maneuver
                print(
                    f"\n[MANEUVER IN PROGRESS] Next vector in {wait_time} seconds..."
                )
                time.sleep(wait_time)

        except KeyboardInterrupt:
            print("\n\n[SESSION TERMINATED]")
        finally:
            input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

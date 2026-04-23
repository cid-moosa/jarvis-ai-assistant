"""
skills/sysinfo/skill.py
=======================
System resource monitoring via psutil — fully local, zero API.
"""
import psutil
import platform
from core import voice, intent, logger


def handle(cmd: str, config: dict):
    c = cmd.lower()

    if "cpu" in c or "processor" in c:
        usage = psutil.cpu_percent(interval=1)
        freq  = psutil.cpu_freq()
        freq_str = f" at {freq.current:.0f} megahertz" if freq else ""
        voice.speak(f"CPU usage is {usage:.0f} percent{freq_str}.")

    elif "ram" in c or "memory" in c:
        vm = psutil.virtual_memory()
        used = vm.used // (1024**3)
        total = vm.total // (1024**3)
        voice.speak(f"RAM: {used} of {total} gigabytes used ({vm.percent:.0f} percent).")

    elif "disk" in c or "storage" in c or "drive" in c:
        du = psutil.disk_usage("/")
        free = du.free // (1024**3)
        total = du.total // (1024**3)
        voice.speak(f"Disk: {free} gigabytes free of {total} gigabytes total.")

    elif "battery" in c:
        batt = psutil.sensors_battery()
        if batt:
            state = "charging" if batt.power_plugged else "on battery"
            voice.speak(f"Battery is at {batt.percent:.0f} percent, {state}.")
        else:
            voice.speak("No battery detected.")

    elif "network" in c or "internet" in c or "connection" in c:
        net = psutil.net_io_counters()
        sent = net.bytes_sent // (1024**2)
        recv = net.bytes_recv // (1024**2)
        voice.speak(f"Network: {sent} megabytes sent, {recv} megabytes received this session.")

    elif "uptime" in c or "how long" in c:
        import time
        boot = psutil.boot_time()
        uptime_sec = int(time.time() - boot)
        h = uptime_sec // 3600
        m = (uptime_sec % 3600) // 60
        voice.speak(f"System has been running for {h} hours and {m} minutes.")

    elif "processes" in c or "running" in c:
        count = len(psutil.pids())
        voice.speak(f"There are {count} processes running.")

    elif "system" in c or "info" in c or "specs" in c:
        cpu_count = psutil.cpu_count(logical=True)
        vm = psutil.virtual_memory()
        ram = vm.total // (1024**3)
        voice.speak(f"System has {cpu_count} CPU threads and {ram} gigabytes of RAM. Platform: {platform.system()} {platform.release()}.")

    else:
        voice.speak("What system info do you want? CPU, RAM, disk, battery, network, uptime, or processes?")


SKILL = intent.Skill(
    name        = "sysinfo",
    handler     = handle,
    description = "Local system monitoring via psutil. CPU, RAM, disk, battery, network, uptime.",
    keywords    = ["cpu", "ram", "memory", "disk", "battery", "network", "uptime", "processes", "specs", "system info"],
    patterns    = [
        intent.IntentPattern("cpu usage",             95),
        intent.IntentPattern("how much cpu",          92),
        intent.IntentPattern("ram usage",             95),
        intent.IntentPattern("how much ram",          92),
        intent.IntentPattern("memory usage",          92),
        intent.IntentPattern("disk space",            92),
        intent.IntentPattern("storage",               80),
        intent.IntentPattern("battery",               90),
        intent.IntentPattern("network usage",         88),
        intent.IntentPattern("uptime",                88),
        intent.IntentPattern("system info",           90),
        intent.IntentPattern("system specs",          88),
        intent.IntentPattern("how long has the computer been on", 88),
        intent.IntentPattern("how many processes",    85),
    ],
)
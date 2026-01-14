# ---------------------------
# Weather Station v1.0.2
# ---------------------------
import asyncio
import time, math, struct, socket
from machine import Pin, I2C, PWM, RTC, reset
import network

import st7789py as st7789
import bme280_float as bme280
import tft_config1
import tft_buttons as Buttons
import vga2_bold_16x32 as font
import vga2_bold_16x16 as font1
import vga2_8x8 as font2
from secrets import secrets

# ---------------------------
# Global Setup
# ---------------------------
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000)
led = Pin("LED", Pin.OUT)
tft = tft_config1.config(tft_config1.WIDE)
buttons = Buttons.Buttons()
rtc = RTC()
wlan = network.WLAN(network.STA_IF)
ssid = secrets["ssid"]
pw = secrets["pw"]
DEG = chr(248)  

class State:
    def __init__(self):
        self.wifi_ok = False
        self.ntp_ok = False
        self.time_ready = False
        self.status = ("no IP", "", "", "")
        self.fog_t = 0
        self.temp_current = None
        self.pres_current = None
        self.hum_current = None
        self.dew_point = None
        self.temp_min = None
        self.temp_max = None
        self.pres_min = None
        self.pres_max = None
        self.hum_min = None
        self.hum_max = None
        self.manual_override = False
        self.manual_brightness = 0
        self.last_mode = None   # "day" / "night"

state = State()

COL = {
    "white": st7789.color565(255, 255, 255),
    "yellow": st7789.color565(255, 255, 102),
    "cyan": st7789.color565(0, 255, 255),
    "fog": st7789.color565(220, 220, 220),
    "red": st7789.color565(255,0,0),
    "green": st7789.color565(0,255,0),
}

temp_colors = [
    (-100, st7789.color565(122, 89, 232)),   
    (-10, COL["cyan"]),     
    (0, COL["white"]),    
    (10, st7789.color565(255, 255, 0)),    
    (20, st7789.color565(255, 127, 80)),   
    (30, st7789.color565(255, 51, 51)),     
]

_text_cache = {}
def tft_text_cached(font, txt, x, y, col, bg=0):
    key = (x, y)
    if _text_cache.get(key) != txt:
        _text_cache[key] = txt
        tft.text(font, txt, x, y, col, bg)
        
def get_temp_color(temp):
    color = temp_colors[0][1]  
    for t, c in temp_colors:
        if temp >= t:
            color = c
        else:
            break
    return color

# ---------------------------
# WiFi + NTP + RTC
# ---------------------------
async def connect_wifi():
    global wlan
    wlan.active(True)
    wlan.connect(ssid, pw)
    for _ in range(10):
        if wlan.status() >= 3:
            state.wifi_ok = True
            state.status = wlan.ifconfig()
            break
        await asyncio.sleep(1)
    else:
        state.wifi_ok = False
    return wlan

def last_sunday(year, month):
    first_wd = time.localtime(time.mktime((year, month, 1,0,0,0,0,0)))[6]
    next_month = time.mktime((year, month % 12 + 1, 1,0,0,0,0,0)) if month !=12 else time.mktime((year+1,1,1,0,0,0,0,0))
    days = int((next_month - time.mktime((year, month,1,0,0,0,0,0))) / 86400)
    last_wd = (first_wd + days - 1) % 7
    return days - last_wd

def is_dst_eu(y,m,d,h):
    start, end = last_sunday(y,3), last_sunday(y,10)
    if 3 < m < 10: return True
    if m==3: return d>start or (d==start and h>=2)
    if m==10: return d<end or (d==end and h<3)
    return False

def get_tm_offset(y,m,d,h):
    return 7200 if is_dst_eu(y,m,d,h) else 3600

def set_time():
    try:
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1B

        addr = socket.getaddrinfo("pool.ntp.org", 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)

        s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
        s.close()

        t_utc = struct.unpack("!I", msg[40:44])[0] - 2208988800
        tm = time.gmtime(t_utc)

        tm_local = time.gmtime(t_utc + get_tm_offset(tm[0], tm[1], tm[2], tm[3]))

        rtc.datetime((
            tm_local[0], tm_local[1], tm_local[2], tm_local[6]+1,
            tm_local[3], tm_local[4], tm_local[5], 0
        ))

        state.ntp_ok = True
        state.time_ready = True

        print("NTP sync OK:", tm_local)

    except Exception as e:
        state.ntp_ok = False
        state.time_ready = False
        print("NTP sync failed:", e)

# -----------------------------
# WiFi Reconnect + NTP sync
# -----------------------------
async def reconnect_wifi_and_time():
    if wlan is None:
        tft_text(font2,"WiFi not ready",10,230,COL["red"])
        await asyncio.sleep(1)
        return

    tft_text(font2,"Reconnecting WiFi",10,230,COL["yellow"])
    state.time_ready = False
    state.wifi_ok = False
    try: wlan.disconnect()
    except: pass
    wlan.active(False)
    await asyncio.sleep(1)
    wlan.active(True)
    wlan.connect(ssid,pw)

    for _ in range(50):
        if wlan.isconnected():
            state.wifi_ok = True
            break
        await asyncio.sleep(0.1)

    if state.wifi_ok:
        state.status = wlan.ifconfig()
        tft_text(font2,"WiFi OK",10,230,COL["green"])
        await asyncio.sleep(1)
        try:
            set_time()
            tft_text(font2,"Time OK",10,230,COL["green"])
        except:
            tft_text(font2,"Time FAIL",10,230,COL["red"])
        _text_cache.pop((10,230), None)
        show_ip()
    else:
        tft_text(font2,"WiFi FAIL",10,230,COL["red"])
        tft_text(font2,"IP = none",10,230,COL["white"])

    await asyncio.sleep(2)

# ---------------------------
# TFT Utilities
# ---------------------------
def draw_background():
    r2, g2, b2 = 0, 16, 48    
    r1, g1, b1 = 0, 48, 96

    for y in range(240):  
        t = y / 239
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)

        color = st7789.color565(r, g, b)
        tft.hline(0, y, 320, color)
"""
def draw_background():
    tft.fill_rect(0,0,320,240,0)
    for i in range(0,320,8):
        j = i+1 if i+1<240 else 239
        tft.line(0,j,j,239,st7789.color565(255,0,0))
        tft.line(319,239-j,319-i-1,0,st7789.color565(0,0,255))"""

def tft_text(font, text, x, y, color, bgcolor=0):
    try: tft.text(font, text, x, y, color, bgcolor)
    except: pass

def show_ip():
    ip = state.status[0] if state.wifi_ok else "none"
    tft_text_cached(font2, f"IP = {ip}", 10, 230, COL["white"])

async def wait_for_time_ready():
    while not state.time_ready:
        await asyncio.sleep(0.2)
        
def draw_sensor_screen(state: State):
    t, p, h, d = state.temp_current, state.pres_current, state.hum_current, state.dew_point

    if None in (t, p, h, d, state.temp_min, state.temp_max, state.pres_min, state.pres_max, state.hum_min, state.hum_max):
        return  

    tft_text_cached(font, f"{t:.1f}{DEG}C", 10, 10, get_temp_color(t))
    tft_text_cached(font, f"{p:.1f}hPa", 10, 80, COL["yellow"])
    tft_text_cached(font, f"{h:.0f}%", 10, 120, COL["yellow"])
    tft_text_cached(font, f"DP:{d:.1f}{DEG}C", 10, 160, COL["yellow"])
    
    tft_text_cached(font1, f"Min:{state.temp_min:.0f}{DEG}C Max:{state.temp_max:.0f}{DEG}C", 10, 53, COL["cyan"])
    avgP = (state.pres_min + state.pres_max) / 2
    tft_text_cached(font1, f"{chr(230)}:{avgP:.0f}hPa", 160, 90, COL["cyan"])
    tft_text_cached(font1, f"({state.hum_min:.0f}%-{state.hum_max:.0f}%)", 80, 130, COL["cyan"])

    if d >= t:
        state.fog_t += 0.2
        for i, y in enumerate((160, 175, 190)):
            dx = int(5 * math.sin(state.fog_t + i))
            tft.hline(205 + dx, y, 40, COL["fog"])
    else:
        state.fog_t = 0

def ema(old, new, a=0.2):
    if old is None:
        return new
    return old * (1 - a) + new * a

def load_file(path, binary=False):
    try:
        mode = "rb" if binary else "r"
        with open(path, mode) as f:
            return f.read()
    except:
        return None
    
# ---------------------------
# PWM / Brightness Control
# ---------------------------
def brightness_mode(hour):
    return "night" if 1 <= hour < 8 else "day"

def do_clean_screen():
    try:
        draw_background()
        _text_cache.pop((10,230), None)
        _text_cache.pop((10,10), None)
        _text_cache.pop((10,80), None)
        _text_cache.pop((10,120), None)
        _text_cache.pop((10,160), None)
        _text_cache.pop((10,53), None)
        _text_cache.pop((160,90), None)
        _text_cache.pop((80,130), None)
        show_ip()
    except Exception:
        pass

async def pwm_task():
    global manual_override, manual_brightness, last_mode

    try:
        pwm = PWM(Pin(13))
        pwm.freq(1000)
    except:
        pwm = None

    def apply_auto_brightness(mode):
        if not pwm:
            return
        if mode == "night":
            pwm.duty_u16(0)
        else:
            pwm.duty_u16(10000)

    # initialize
    hour = time.localtime()[3]
    last_mode = brightness_mode(hour)
    apply_auto_brightness(last_mode)

    while True:
        y, m, d, h, mn, s, wd, yd = time.localtime()
        tft_text_cached(
            font1,
            f"{y}/{m}/{d} {h:02d}:{mn:02d}:{s:02d}",
            10, 205, COL["white"]
        )

        current_mode = brightness_mode(h)

        # zmiana trybu czasowego (dzień/noc)
        if current_mode != last_mode:
            manual_override = False   # zwolnij ręczny override
            apply_auto_brightness(current_mode)
            last_mode = current_mode

        # ręczna zmiana jasności
        if pwm and buttons.left.value() == 0:
            cur = pwm.duty_u16()
            manual_brightness = (
                10000 if cur == 0 else
                65000 if cur == 10000 else
                0
            )
            pwm.duty_u16(manual_brightness)
            manual_override = True
            await asyncio.sleep(0.3)

        # reconnect + NTP
        if buttons.right.value() == 0:
            await reconnect_wifi_and_time()

        if buttons.fire.value() == 0:
            do_clean_screen()    

        # reboot
        if buttons.thrust.value() == 0:
            tft_text(font, "Rebooting...", 80, 100, COL["white"])
            await asyncio.sleep(2)
            reset()

        await asyncio.sleep(1)

# ---------------------------
# Sensor Task
# ---------------------------
async def sensor_task():
    bme = None
    while not bme:
        try:
            bme = bme280.BME280(i2c=i2c)
        except:
            tft_text(font1, "Error", 10, 10, COL["red"])
            await asyncio.sleep(2)

    t, p, h = map(float, bme.values)

    state.temp_current = t
    state.pres_current = p
    state.hum_current  = h
    state.temp_min = state.temp_max = t
    state.pres_min = state.pres_max = p
    state.hum_min  = state.hum_max  = h

    while True:
        try:
            t, p, h = map(float, bme.values)
        except:
            tft_text(font1, "Error", 10, 10, COL["red"])
            await asyncio.sleep(2)
            continue

        state.temp_current = ema(state.temp_current, t, 0.2)
        state.pres_current = ema(state.pres_current, p, 0.05)
        state.hum_current  = ema(state.hum_current, h, 0.15)

        T = state.temp_current
        RH = state.hum_current
        gamma = (17.62 * T / (243.12 + T)) + math.log(RH / 100.0)
        state.dew_point = 243.12 * gamma / (17.62 - gamma)

        state.temp_min = min(state.temp_min, state.temp_current)
        state.temp_max = max(state.temp_max, state.temp_current)

        state.pres_min = min(state.pres_min, state.pres_current)
        state.pres_max = max(state.pres_max, state.pres_current)

        state.hum_min = min(state.hum_min, state.hum_current)
        state.hum_max = max(state.hum_max, state.hum_current)

        draw_sensor_screen(state)
        await asyncio.sleep(15)


# ---------------------------
# HTTP Server using status.html
# ---------------------------
async def handle_request(reader, writer):
    try:
        request_line = await reader.readline()
        if not request_line:
            await writer.aclose()
            return

        try:
            method, path, proto = request_line.decode().strip().split(" ")
        except:
            method = "GET"
            path = "/"

        headers = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            line = line.decode().strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.lower()] = v.strip()

        body = b""
        if "content-length" in headers:
            try:
                length = int(headers["content-length"])
                if length > 0:
                    body = await reader.read(length)
            except:
                pass

        html_template = load_file("status.html")
        if html_template is None:
            html_template = "<html><body><h1>Status page missing!</h1></body></html>"

        y, m, d, h, mn, s, wd, yd = time.localtime()
        now_str = f"{y:04d}-{m:02d}-{d:02d} {h:02d}:{mn:02d}:{s:02d}"
        ip_str = state.status[0] if state.wifi_ok else "No IP"

        avgP = (
            (state.pres_min + state.pres_max) / 2
            if state.pres_min is not None and state.pres_max is not None
            else 0
        )
        logged_data = load_file("temperature_data.txt") or "No log data available."

        html = (
            html_template
            .replace("{{IP}}", ip_str)
            .replace("{{TIME}}", now_str)
            .replace("{{TEMP}}", f"{state.temp_current:.1f}" if state.temp_current else "-")
            .replace("{{PRESS}}", f"{state.pres_current:.1f}" if state.pres_current else "-")
            .replace("{{HUM}}", f"{state.hum_current:.0f}" if state.hum_current else "-")
            .replace("{{TMIN}}", f"{state.temp_min:.1f}" if state.temp_min else "-")
            .replace("{{TMAX}}", f"{state.temp_max:.1f}" if state.temp_max else "-")
            .replace("{{AVG_PRESS}}", f"{avgP:.1f}")
            .replace("{{LOGGED}}", logged_data)
        ).encode()

        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html; charset=UTF-8\r\n"
            b"Connection: close\r\n"
            b"Content-Length: " + str(len(html)).encode() + b"\r\n"
            b"\r\n"
        )
        writer.write(html)
        await writer.drain()

    except Exception as e:
        print("HTTP error:", e)

    finally:
        try:
            await writer.aclose()  
        except:
            pass

async def start_server(): 
    server = await asyncio.start_server(handle_request, "0.0.0.0", 80)
    print("HTTP server running on port 80...")
    async with server:
        await server.wait_closed()

# ---------------------------
# Daily Reset
# ---------------------------
async def daily_reset_task():
    await wait_for_time_ready()
    daily_reset_done = False

    while True:
        y, m, d, h, mn, s, w, yd = time.localtime()
        if h == 23 and mn == 59 and not daily_reset_done:
            try:
                avgP = (state.pres_min + state.pres_max) / 2
                with open("temperature_data.txt", "a") as f:
                    f.write(
                        f"{y}-{m:02d}-{d:02d} | "
                        f"Min Temp: {round(state.temp_min,1)}&deg;C | "
                        f"Max Temp: {round(state.temp_max,1)}&deg;C | "
                        f"Avg Pressure: {round(avgP,1)} hPa\n"
                    )
            except Exception as e:
                print("File write error:", e)

            state.temp_min = state.temp_max = state.temp_current
            state.pres_min = state.pres_max = state.pres_current
            state.hum_min = state.hum_max = state.hum_current

            daily_reset_done = True 
        elif mn != 59:
            daily_reset_done = False 

        await asyncio.sleep(30) 

# ---------------------------
# Screen Cleanup
# ---------------------------
async def clean_screen(): 
    while True:
        await asyncio.sleep(1800)
        do_clean_screen()

# ---------------------------
# NTP Periodic Sync Task
# ---------------------------
async def ntp_task(interval_hours=6):
    await wait_for_time_ready()

    while True:
        if state.wifi_ok:
            try:
                set_time()
                print("NTP task: time updated.")
            except Exception as e:
                print("NTP task error:", e)
        else:
            print("NTP task skipped (WiFi offline).")

        await asyncio.sleep(interval_hours * 3600)

        print("\n--- RTC SANITY CHECK ---")
        y, m, d, hh, mm, ss, wd, yd = time.localtime()

        rtc_ok = (
            2000 <= y <= 2050 and
            1 <= m <= 12 and
            1 <= d <= 31 and
            0 <= hh < 24 and
            0 <= mm < 60 and
            0 <= ss < 60
        )

        if not rtc_ok:
            print("RTC invalid, attempting repair...")

            if state.wifi_ok:
                try:
                    set_time()
                    print("RTC fixed by NTP.")
                    continue
                except:
                    print("NTP failed while fixing RTC.")
            
            print("RTC fallback to failsafe time.")
            rtc.datetime((2025, 1, 1, 1, 0, 0, 1, 0))

        else:
            print("RTC OK:", y, m, d, hh, mm, ss)

# ---------------------------
# Main
# ---------------------------
async def async_set_time():
    try:
        set_time()
    except Exception as e:
        print("Initial NTP sync failed:", e)

async def init_system():
    draw_background()
    rtc.datetime((2025, 1, 1, 3, 0, 0, 0, 0))
    wlan = await connect_wifi()
    show_ip()
    if state.wifi_ok:
        asyncio.create_task(async_set_time())

async def main():
    await init_system()
    await asyncio.gather(
        sensor_task(),
        pwm_task(),
        daily_reset_task(),
        start_server(),
        clean_screen(),
        ntp_task(),
    )

print("System OK. Starting tasks.")
asyncio.run(main())

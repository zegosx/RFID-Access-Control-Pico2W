from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from mfrc522 import MFRC522
import network
import socket
import time
import ntptime

SSID = "your_wifi_ssid"
PASSWORD = "your_wifi_password"

GRANTED_UID = [89, 109, 37, 0, 17]

# OLED
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=50000)
oled = SSD1306_I2C(128, 64, i2c)

# RFID
reader = MFRC522(spi_id=0, sck=18, miso=16, mosi=19, cs=17, rst=20)

# LED + BUZZER
buzzer = Pin(13, Pin.OUT)
green = Pin(14, Pin.OUT)
red = Pin(15, Pin.OUT)

def screen(a, b=""):
    oled.fill(0)
    oled.text(a, 0, 15)
    oled.text(b, 0, 35)
    oled.show()

def beep(times):
    for _ in range(times):
        buzzer.on()
        time.sleep(0.15)
        buzzer.off()
        time.sleep(0.15)

def reset_outputs():
    green.off()
    red.off()
    buzzer.off()

def get_time():
    t = time.localtime(time.time() + 3 * 3600)
    return "%04d-%02d-%02d %02d:%02d:%02d" % (
        t[0], t[1], t[2], t[3], t[4], t[5]
    )

def log_access(uid, result):
    with open("access_log.txt", "a") as f:
        f.write(get_time() + "|" + result + "|" + str(uid) + "\n")

def read_logs():
    try:
        with open("access_log.txt", "r") as f:
            return f.readlines()
    except:
        return []

def clear_logs():
    with open("access_log.txt", "w") as f:
        f.write("")

def connect_wifi():
    screen("Connecting", "WiFi")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("IP:", ip)
        screen("WiFi OK", ip)

        try:
            ntptime.settime()
            print("Time synced")
        except:
            print("NTP failed")

        return ip
    else:
        screen("WiFi", "FAILED")
        return "0.0.0.0"

def make_page():
    rows = ""

    for line in read_logs():
        parts = line.strip().split("|")
        if len(parts) == 3:
            dt, result, uid = parts
            color = "#d4edda" if result == "GRANTED" else "#f8d7da"
            rows += "<tr style='background:%s'><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                color, dt, result, uid
            )

    if rows == "":
        rows = "<tr><td colspan='3'>No logs yet</td></tr>"

    return """HTTP/1.1 200 OK
Content-Type: text/html

<html>
<head>
<title>RFID Dashboard</title>
<style>
body {{ font-family: Arial; background:#f4f4f4; padding:20px; }}
h1 {{ color:#222; }}
table {{ border-collapse: collapse; width:100%; background:white; }}
td, th {{ border:1px solid #ccc; padding:10px; text-align:left; }}
button {{ padding:10px 15px; background:#222; color:white; border:0; }}
</style>
</head>
<body>
<h1>RFID Access Dashboard</h1>

<form action="/clear">
<button type="submit">Clear Logs</button>
</form>

<br>

<table>
<tr><th>Time</th><th>Result</th><th>UID</th></tr>
{}
</table>

</body>
</html>
""".format(rows)
ip = connect_wifi()

addr = socket.getaddrinfo("0.0.0.0", 8080)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)
s.settimeout(0.1)

print("Dashboard ready")
print("Open: http://%s:8080/" % ip)

reset_outputs()
screen("RFID ACCESS", "Scan Card...")

while True:
    # WEB DASHBOARD
    try:
        conn, addr = s.accept()
        request = conn.recv(1024).decode()

        if "GET /clear" in request:
            clear_logs()
            response = "HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n"
        else:
            response = make_page()

        conn.send(response.encode())
        conn.close()

    except OSError:
        pass

    # RFID SCAN
    reader.init()
    stat, tag_type = reader.request(reader.REQIDL)

    if stat == reader.OK:
        stat, uid = reader.SelectTagSN()

        if stat == reader.OK:
            print("Card UID:", uid)
            reset_outputs()

            if uid == GRANTED_UID:
                log_access(uid, "GRANTED")
                green.on()
                screen("ACCESS", "GRANTED")
                beep(1)
            else:
                log_access(uid, "DENIED")
                red.on()
                screen("ACCESS", "DENIED")
                beep(3)

            time.sleep(2)
            reset_outputs()
            screen("RFID ACCESS", "Scan Card...")

    time.sleep(0.1)

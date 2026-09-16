import socket, subprocess, json

s = socket.socket()
try:
    s.connect(("127.0.0.1", 5000))
    print("PORT 5000: in use")
except Exception as e:
    print("PORT 5000: free -", e)
finally:
    s.close()

# find python processes touching port 5000
try:
    out = subprocess.check_output(["netstat", "-ano"], stderr=subprocess.STDOUT).decode("utf-8", "replace")
    for line in out.splitlines():
        if ":5000" in line and ("LISTENING" in line or "UDP" in line):
            print(line.strip())
except Exception as e:
    print("netstat failed:", e)
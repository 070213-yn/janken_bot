import subprocess

scripts = [
    "hit_and_blow.py",
    "janken_bot.py",
    "jankenhoitour_bot.py",
    "osero.py"
]

processes = []

for script in scripts:
    proc = subprocess.Popen(["python", script])
    processes.append(proc)

for proc in processes:
    proc.wait()

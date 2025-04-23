import subprocess

# 起動するスクリプトのリスト
scripts = ["hit_and_blow.py", "janken_bot.py", "jankenhoitour_bot.py"]

# 各スクリプトを並列で起動
processes = []
try:
    for script in scripts:
        print(f"Starting {script}...")
        process = subprocess.Popen(["python", script])
        processes.append(process)

    # 全てのプロセスが終了するのを待機
    for process in processes:
        process.wait()
except KeyboardInterrupt:
    print("Shutting down all scripts...")
    for process in processes:
        process.terminate()
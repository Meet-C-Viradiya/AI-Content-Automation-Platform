import subprocess
import sys
import time

def main():
    print("Starting AI Content Automation Platform...")
    print("=" * 50)

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload"],
    )

    time.sleep(3)

    dashboard = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/dashboard.py"],
    )

    print("\n" + "=" * 50)
    print("API:       http://127.0.0.1:8000/docs")
    print("Dashboard: http://127.0.0.1:8501")
    print("Press Ctrl+C to stop both")
    print("=" * 50)

    try:
        api.wait()
        dashboard.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api.terminate()
        dashboard.terminate()

if __name__ == "__main__":
    main()
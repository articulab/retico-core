import sys
import subprocess


def install_pyaudio():
    # print(f"System OS : {platform.system()}")
    # is_linux = platform.system().lower() == "linux"
    print(f"System OS : {sys.platform}")
    if sys.platform.startswith("linux"):
        print("Detected Linux: Installing pyaudio via Conda...")
        subprocess.run(["conda", "install", "-y", "pyaudio"], check=True)
    else:
        print("Detected non-Linux: Installing pyaudio via pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyaudio"], check=True)


if __name__ == "__main__":
    install_pyaudio()

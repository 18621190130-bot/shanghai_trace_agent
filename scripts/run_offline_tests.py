"""Default automated suite: clear live configuration, including child CLIs."""
import os
import subprocess
import sys


if __name__ == '__main__':
    env = dict(os.environ, PYTHONUTF8='1', AMAP_WEB_SERVICE_KEY='', RUN_LIVE_AMAP_TESTS='0')
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-q'], env=env)
    raise SystemExit(result.returncode)

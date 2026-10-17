"""Start the local TraceMate website and open the browser after readiness checks."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def available_port(first):
    for port in range(first, min(first + 50, 65536)):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError('No free local port. Close an older website window and try again.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--standard', action='store_true', help='Hide developer location simulation')
    parser.add_argument('--offline', action='store_true', help='Disable external API integrations')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required.')
    port = available_port(args.port)
    url = f'http://127.0.0.1:{port}/'
    command = [sys.executable, '-u', str(ROOT / 'web_server.py'), '--port', str(port)]
    if not args.standard:
        command.append('--demo')
    if args.offline:
        command.append('--offline')
    env = os.environ.copy()
    # Cloud sharing configuration must not force Secure cookies on local HTTP.
    for name in ('TRACEMATE_PUBLIC_HOST', 'TRACEMATE_PUBLIC_HOST_FILE'):
        env.pop(name, None)
    env['PYTHONUTF8'] = '1'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    expected = (ROOT / 'frontend/app.js').read_bytes()
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('The website server exited before it was ready.')
            try:
                with opener.open(url + 'app.js', timeout=2) as response:
                    correct = response.read() == expected
                with opener.open(url + 'api/bootstrap', timeout=2) as response:
                    ready = response.status == 200
                if correct and ready:
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError('Website startup timed out.')
        print(f'\nTraceMate is ready: {url}', flush=True)
        print('Keep this window open. Press Ctrl+C to stop the website.', flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return process.wait()
    except KeyboardInterrupt:
        print('\nStopping TraceMate...', flush=True)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print(f'Startup failed: {error}', file=sys.stderr)
        sys.exit(1)

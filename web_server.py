"""Run TraceMate locally: python web_server.py --port 8765 [--offline]."""
from dataclasses import asdict
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from src.web_app import WebApplication
from src.web_map import StaticMapService
from src.web_sdk import load_local_environment, proxy_sdk
from src.providers.base import ExternalProviderError
from src.llm_client import LLMClientError

PUBLIC=Path(__file__).resolve().parent/'frontend'


def handler_for(app,map_service=None):
    maps=map_service or StaticMapService()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def send(self,status,body,mime='application/json; charset=utf-8',cookie=None):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store' if mime.startswith('application/json') else 'private, max-age=60')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','same-origin')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' https://webapi.amap.com https://*.amap.com 'unsafe-eval'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://*.amap.com https://*.autonavi.com; connect-src 'self' https://*.amap.com https://*.autonavi.com; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
            if cookie:
                secure='; Secure' if self.public_host() else ''
                self.send_header('Set-Cookie',f'tm_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+secure)
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass

        def session(self):
            cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
            return app.session(cookies['tm_session'].value if 'tm_session' in cookies else None)

        def public_host(self):
            configured=os.environ.get('TRACEMATE_PUBLIC_HOST_FILE')
            if configured:
                try:return Path(configured).read_text(encoding='utf-8').strip().lower()
                except OSError:return ''
            return os.environ.get('TRACEMATE_PUBLIC_HOST','').strip().lower()

        def valid_host(self):
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            public_host=self.public_host()
            if public_host:allowed.add(public_host)
            return self.headers.get('Host','').lower() in allowed

        def do_GET(self):
            if not self.valid_host():return self.send(403,{'error':'invalid_host'})
            url=urlsplit(self.path)
            try:
                if url.path.startswith('/_AMapService/'):
                    body,mime=proxy_sdk(url.path.removeprefix('/_AMapService'),url.query);return self.send(200,body,mime)
                if url.path=='/api/poi-images':
                    path=PUBLIC.parent/'data/poi_images.json'
                    return self.send(200,json.loads(path.read_text(encoding='utf-8')))
                if url.path.startswith('/image-review/'):
                    name=url.path.removeprefix('/image-review/') or 'image_audit.html'
                    if name not in {'image_audit.html','image_audit.json','review_template.json','review.js','review.css'}:return self.send(404,{'error':'not_found'})
                    path=PUBLIC.parent/'examples/poi_images'/name
                    mime='text/javascript' if name.endswith('.js') else mimetypes.guess_type(name)[0] or 'application/json'
                    return self.send(200,path.read_bytes(),mime+'; charset=utf-8')
                if url.path=='/api/bootstrap':
                    token,session=self.session();return self.send(200,app.bootstrap(session),cookie=token)
                if url.path=='/api/map':
                    query={k:v[0] for k,v in parse_qs(url.query).items()}
                    body,mime=maps.get(query);return self.send(200,body,mime)
                if url.path.startswith('/api/'):return self.send(404,{'error':'not_found'})
                relative=unquote(url.path).lstrip('/') or 'index.html'
                path=(PUBLIC/relative).resolve()
                if not path.is_relative_to(PUBLIC.resolve()) or not path.is_file():
                    return self.send(404,{'error':'not_found'})
                mime='text/javascript' if path.suffix=='.js' else mimetypes.guess_type(path)[0] or 'application/octet-stream'
                return self.send(200,path.read_bytes(),mime+'; charset=utf-8' if mime.startswith(('text/','application/json')) else mime)
            except ExternalProviderError:return self.send(503,{'error':'provider_unavailable'})
            except ValueError:return self.send(400,{'error':'invalid_input'})
            except Exception:return self.send(500,{'error':'server_error'})

        def do_POST(self):
            if not self.valid_host():return self.send(403,{'error':'invalid_host'})
            try:
                origin=self.headers.get('Origin')
                if origin and urlsplit(origin).netloc!=self.headers.get('Host'):return self.send(403,{'error':'invalid_origin'})
                if self.headers.get_content_type()!='application/json':return self.send(415,{'error':'json_required'})
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768:return self.send(413,{'error':'invalid_input'})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('invalid_input')
                token,session=self.session()
                routes={'/api/arrival/context':lambda:app.arrivals.context(session),
                        '/api/guidance/route':lambda:app.guidance.route(body),
                        '/api/guidance/search':lambda:app.guidance.search(body),
                        '/api/guidance/describe':lambda:app.guidance.describe(body),
                        '/api/guidance/location':lambda:dict(location=asdict(app.guidance.location(body.get('location')))),
                        '/api/guidance/direction':lambda:app.guidance_direction(session,body),
                        '/api/arrival/check':lambda:app.arrivals.check(session,body),
                        '/api/arrival/content':lambda:app.arrivals.content(body.get('poi_id')),
                        '/api/generate':lambda:app.generate(session,body),'/api/clarify':lambda:app.clarify(session,body),
                        '/api/trip/action':lambda:app.action(session,body),'/api/trip/turn':lambda:app.turn(session,body),'/api/reality':lambda:app.reality(session,body),
                        '/api/nearby':lambda:app.nearby(body),
                        '/api/poi':lambda:app.world.get_poi_live_info(body.get('poi_id')).to_dict()}
                if self.path not in routes:return self.send(404,{'error':'not_found'})
                return self.send(200,routes[self.path](),cookie=token)
            except LLMClientError:return self.send(503,{'error':'language_provider_unavailable'})
            except ExternalProviderError:return self.send(503,{'error':'provider_unavailable'})
            except (ValueError,KeyError,TypeError) as exc:
                known={'stale_state_conflict','no_trip','active_trip_requires_replan','natural_language_unavailable','no_pending_question','zone_mismatch','direction_locked','location_outside'}
                code=str(exc) if str(exc) in known else 'invalid_input'
                return self.send(409 if code=='stale_state_conflict' else 400,{'error':code})
            except Exception:return self.send(500,{'error':'server_error'})
    return Handler


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765);parser.add_argument('--offline',action='store_true')
    parser.add_argument('--demo',action='store_true',help='Enable clearly labeled simulated location controller')
    args=parser.parse_args()
    os.environ['TRACEMATE_ENABLE_DEMO_MODE']='true' if args.demo else 'false'
    load_local_environment()
    if args.offline:
        os.environ['AMAP_WEB_SERVICE_KEY']='';os.environ['DEEPSEEK_API_KEY']='';os.environ['AMAP_JS_API_KEY']='';os.environ['AMAP_JS_SECURITY_CODE']=''
    elif not os.environ.get('AMAP_WEB_SERVICE_KEY') and os.environ.get('AMAP_API_KEY'):
        # Existing local configuration alias, process-only; never exported to the browser.
        os.environ['AMAP_WEB_SERVICE_KEY']=os.environ['AMAP_API_KEY']
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(WebApplication()))
    print(f'TraceMate: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()

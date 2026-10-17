"""Fixed-origin JS API security proxy. The security code never reaches the browser."""
import os
import urllib.parse
import urllib.request
from .providers.base import ProviderUnavailableError


def load_local_environment():
    if os.name!='nt':return
    import winreg
    for name in ('AMAP_JS_API_KEY','AMAP_JS_SECURITY_CODE'):
        if os.environ.get(name):continue
        for root,path in ((winreg.HKEY_CURRENT_USER,'Environment'),(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')):
            try:
                with winreg.OpenKey(root,path) as key:value,_=winreg.QueryValueEx(key,name)
                if value:os.environ[name]=value;break
            except OSError:pass


def proxy_sdk(path,query):
    secret=os.environ.get('AMAP_JS_SECURITY_CODE','')
    if not secret:raise ProviderUnavailableError()
    if not path.startswith(('/v3/','/v4/')) or '..' in path or '\\' in path:raise ValueError('invalid_input')
    params=urllib.parse.parse_qs(query,keep_blank_values=True)
    params['jscode']=[secret];params['key']=[os.environ.get('AMAP_JS_API_KEY','')]
    origin='https://webapi.amap.com' if path.startswith('/v4/map/styles') else 'https://restapi.amap.com'
    url=origin+path+'?'+urllib.parse.urlencode(params,doseq=True)
    try:
        with urllib.request.urlopen(url,timeout=10) as response:
            data=response.read(8*1024*1024+1);mime=response.headers.get('Content-Type','application/octet-stream')
        if len(data)>8*1024*1024 or secret.encode() in data:raise ValueError()
        if params.get('callback'):mime='text/javascript; charset=utf-8'
        return data,mime
    except Exception:raise ProviderUnavailableError() from None

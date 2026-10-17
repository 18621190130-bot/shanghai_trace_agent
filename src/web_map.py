"""Credential-private Amap basemap image adapter for the browser map controller.

The existing JSON AmapClient cannot consume images. This isolated adapter only
fetches the official static-map binary endpoint; route/world providers are reused.
"""
import math
import os
import threading
import time
import urllib.parse
import urllib.request
from .services.ttl_cache import TTLCache
from .providers.base import ProviderUnavailableError, ProviderResponseError


class StaticMapService:
    def __init__(self, opener=None):
        self.opener=opener or urllib.request.urlopen
        self.cache=TTLCache(600,max_entries=64)
        self.lock=threading.Lock()
        self.last=0

    def get(self, query):
        try:
            lng=float(query['lng']);lat=float(query['lat']);zoom=int(query['zoom'])
            width=int(query['width']);height=int(query['height'])
            if not all(math.isfinite(x) for x in (lat,lng)) or not 30<=lat<=32 or not 120<=lng<=123:
                raise ValueError()
            if not 10<=zoom<=17 or not 100<=width<=1024 or not 100<=height<=1024:raise ValueError()
        except (ValueError,KeyError,TypeError):raise ValueError('invalid_map_view') from None
        key=(round(lng,6),round(lat,6),zoom,width,height)
        cached=self.cache.get(key)
        if cached:return cached
        credential=os.environ.get('AMAP_WEB_SERVICE_KEY','')
        if not credential:raise ProviderUnavailableError()
        parameters=dict(location=f'{lng:.6f},{lat:.6f}',zoom=zoom,size=f'{width}*{height}',scale=1,key=credential)
        url='https://restapi.amap.com/v3/staticmap?'+urllib.parse.urlencode(parameters)
        with self.lock:
            time.sleep(max(0,.5-(time.monotonic()-self.last)))
            self.last=time.monotonic()
        try:
            with self.opener(url,timeout=8) as response:
                body=response.read(4*1024*1024+1)
                mime=response.headers.get('Content-Type','').split(';')[0]
            signature=body.startswith(b'\x89PNG\r\n\x1a\n') or body.startswith(b'\xff\xd8\xff')
            if len(body)>4*1024*1024 or mime not in ('image/png','image/jpeg') or not signature:
                raise ProviderResponseError()
            result=(body,mime);self.cache.set(key,result);return result
        except Exception:raise ProviderUnavailableError() from None

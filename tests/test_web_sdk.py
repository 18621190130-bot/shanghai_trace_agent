import io
import os
import unittest
from unittest.mock import patch
from src.web_sdk import proxy_sdk
from src.providers.base import ProviderUnavailableError
from src.web_english import EnglishPlaceLabels
from src.llm_client import MockLLMClient


class SDKProxyTests(unittest.TestCase):
    def test_fixed_origin_and_private_security_code_with_jsonp_mime(self):
        response=io.BytesIO(b'callback({"status":1})');response.headers={'Content-Type':'application/octet-stream'}
        with patch.dict(os.environ,AMAP_JS_API_KEY='public-test',AMAP_JS_SECURITY_CODE='private-test'),patch('src.web_sdk.urllib.request.urlopen',return_value=response) as open_url:
            body,mime=proxy_sdk('/v3/log/init','callback=callback&jscode=untrusted&key=wrong')
        url=open_url.call_args.args[0]
        self.assertTrue(url.startswith('https://restapi.amap.com/v3/log/init?'))
        self.assertIn('jscode=private-test',url);self.assertNotIn('untrusted',url)
        self.assertTrue(mime.startswith('text/javascript'));self.assertNotIn(b'private-test',body)

    def test_path_rejected_without_network(self):
        with patch.dict(os.environ,AMAP_JS_SECURITY_CODE='private-test'),patch('src.web_sdk.urllib.request.urlopen') as open_url:
            for path in ('//evil.example/v3/log','/v3/../secret','/other'):
                with self.assertRaises(ValueError):proxy_sdk(path,'')
            open_url.assert_not_called()

    def test_missing_security_code_fails_safely(self):
        with patch.dict(os.environ,AMAP_JS_SECURITY_CODE=''),self.assertRaises(ProviderUnavailableError):proxy_sdk('/v3/log/init','')

    def test_upstream_cannot_echo_security_code(self):
        response=io.BytesIO(b'private-test');response.headers={'Content-Type':'text/plain'}
        with patch.dict(os.environ,AMAP_JS_API_KEY='public-test',AMAP_JS_SECURITY_CODE='private-test'),patch('src.web_sdk.urllib.request.urlopen',return_value=response),self.assertRaises(ProviderUnavailableError):proxy_sdk('/v3/log/init','')


class EnglishLabelsTests(unittest.TestCase):
    def test_translation_is_display_only_and_cached(self):
        client=MockLLMClient(responses=[{'places':[{'index':0,'name':'Test Cafe','address':'1 Test Road'}]}])
        service=EnglishPlaceLabels(client)
        def result():return {'results':[{'service_poi_id':'amap:test','name':'测试咖啡','address':'测试路1号','location':{'lat':31.2,'lng':121.4}}]}
        first=service.apply(result());second=service.apply(result())
        self.assertEqual(first,second);self.assertEqual(len(client.calls),1)
        row=first['results'][0];self.assertEqual(row['name'],'测试咖啡');self.assertEqual(row['name_en'],'Test Cafe');self.assertEqual(row['location'],{'lat':31.2,'lng':121.4})

    def test_no_chinese_translation_accepted_as_english(self):
        service=EnglishPlaceLabels(MockLLMClient(responses=[{'places':[{'index':0,'name':'中文','address':'中文'}]}]))
        result=service.apply({'results':[{'service_poi_id':'amap:test','name':'中文','address':''}]})
        self.assertNotIn('name_en',result['results'][0])

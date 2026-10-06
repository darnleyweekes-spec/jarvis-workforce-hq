import unittest
from unittest.mock import patch
from alpha_runtime import MissionState,SpecialistTask,MissionError
from static_web_adapter import extract_static,validate_url
class StaticTests(unittest.TestCase):
    def task(self,permission=True):
        return SpecialistTask('t','research','read',('evidence',),(),('web.static.read',) if permission else (),(),(),MissionState())
    def test_scope_and_private_network(self):
        with self.assertRaises(MissionError): extract_static(self.task(False),'https://example.com',('example.com',))
        with self.assertRaises(MissionError): validate_url('https://other.com',('example.com',))
        with patch('static_web_adapter.socket.getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]):
            with self.assertRaises(MissionError): validate_url('https://example.com',('example.com',))
    def test_evidence_and_robots(self):
        with patch('static_web_adapter.validate_url',return_value=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit('https://example.com')),patch('static_web_adapter.read',side_effect=[('User-agent: *\nAllow: /','text/plain'),('<script>secret</script><p>Evidence</p>','text/html')]):
            result=extract_static(self.task(),'https://example.com',('example.com',))
            self.assertIn('Evidence',result.claim); self.assertNotIn('secret',result.claim)
        with patch('static_web_adapter.validate_url',return_value=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit('https://example.com')),patch('static_web_adapter.read',return_value=('User-agent: *\nDisallow: /','text/plain')):
            with self.assertRaises(MissionError): extract_static(self.task(),'https://example.com',('example.com',))

"""Scoped static HTML research when a browser is unavailable."""
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
from urllib.error import HTTPError
import ipaddress
import socket
from alpha_runtime import Evidence, MissionError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise MissionError('Redirect requires a separately approved URL')

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())

def validate_url(url, hosts):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in hosts or p.username or p.password or p.port not in (None,443):
        raise MissionError('URL outside approved HTTPS scope')
    try:
        addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    except OSError as error:
        raise MissionError('Host DNS is unavailable; use the Work web-search connector') from error
    if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise MissionError('Private network access denied')
    return p

def read(url, limit):
    with build_opener(NoRedirect).open(Request(url,headers={'User-Agent':'ALPHAResearch/1.0'}),timeout=20) as response:
        body=response.read(limit+1)
        if len(body)>limit: raise MissionError('Response exceeds size limit')
        return body.decode('utf-8',errors='replace'), response.headers.get_content_type()

def extract_static(task,url,allowed_hosts,max_characters=12000):
    if 'web.static.read' not in task.allowed_tools: raise MissionError('Missing web.static.read permission')
    if not 1<=max_characters<=50000: raise ValueError('Invalid output limit')
    p=validate_url(url,allowed_hosts)
    robots=RobotFileParser()
    try:
        rules,_=read('https://'+p.hostname+'/robots.txt',100000)
        robots.parse(rules.splitlines())
        if not robots.can_fetch('ALPHAResearch',url): raise MissionError('Robots policy denies access')
    except HTTPError as error:
        if error.code!=404: raise MissionError('Cannot verify robots policy') from error
    content,mime=read(url,2000000)
    if mime not in ('text/html','text/plain'): raise MissionError('Unsupported page type')
    if mime=='text/html':
        parser=Text(); parser.feed(content); content='\n'.join(parser.parts)
    if not content.strip(): raise MissionError('Empty page')
    return Evidence('static-'+sha256((url+content).encode()).hexdigest()[:24],
        'Observed static page content:\n'+content[:max_characters],url,
        datetime.now(timezone.utc).isoformat(),'fact',86400)

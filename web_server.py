#!/usr/bin/env python3
"""NEXUS WEB — painel privado de leitura, baseado nos dados auditados do GitHub."""
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import html
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parent
SECRET=os.environ.get('NEXUS_WEB_PASSWORD','')
if not SECRET or len(SECRET)<14:
    raise RuntimeError('Configure NEXUS_WEB_PASSWORD com pelo menos 14 caracteres.')
COOKIE='nxs_auth'
TTL=86400*14
BR=timezone(timedelta(hours=-3))
FAILED={}
FAILED_LOCK=threading.Lock()

def sign(payload):
    return hmac.new(SECRET.encode(),payload.encode(),'sha256').hexdigest()
def is_authorized(headers):
    raw=headers.get('Cookie','')
    try:
        c=SimpleCookie();c.load(raw)
        v=c[COOKIE].value
        encoded,signature=v.split('.',1)
        if not hmac.compare_digest(sign(encoded),signature):return False
        issued=int(base64.urlsafe_b64decode(encoded+'===').decode())
        return 0<=time.time()-issued<TTL
    except (ValueError,KeyError,TypeError,UnicodeError):return False
def cookie():
    stamp=base64.urlsafe_b64encode(str(int(time.time())).encode()).decode().rstrip('=')
    return f'{COOKIE}={stamp}.{sign(stamp)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age={TTL}'
def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
def snapshot():
    history=ROOT/'history'
    states=read(history/'status.json')
    odds=read(history/'odds_status.json')
    bolsa=read(history/'bolsa_netpl.json')
    games=[]
    for f in sorted(history.glob('20??-??-??.json'),reverse=True)[:7]:
        doc=read(f)
        for match_id,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            fix=row.get('fixture') or {}
            if not fix.get('home') or not fix.get('away'):continue
            momentum=((row.get('thermometer') or {}).get('points') or [])
            quotes=row.get('odds_quotes') or []
            signals=row.get('paper_signals') or []
            games.append({'id':str(match_id)[:90],'day':f.stem,
                          'home':str(fix.get('home'))[:110],'away':str(fix.get('away'))[:110],
                          'league':str(fix.get('league') or '')[:100],
                          'score':str(fix.get('score') or '—')[:20],
                          'phase':str(fix.get('phase') or 'scheduled')[:24],
                          'minute':fix.get('minute'),'source':str(fix.get('source') or '')[:25],
                          'last_seen':fix.get('collected_at'),
                          'pressure':momentum[-120:] if isinstance(momentum,list) else [],
                          'stats':row.get('stats') or {},
                          'odds':quotes[:60] if isinstance(quotes,list) else [],
                          'signals':signals[:20] if isinstance(signals,list) else []})
    games.sort(key=lambda g:(0 if g['phase']=='live' else 1,-int(g['day'].replace('-','')),g['league'],g['home']))
    return {'server_time':datetime.now(timezone.utc).isoformat(),'collection':states,
            'odds_status':odds,'bolsa':bolsa,'games':games[:250],
            'warning':'P/L da Bolsa é histórico real. EV estimado não equivale a lucro realizado. Coleta do GitHub é horária e pode atrasar.',
            'kind':'nexus-web-readonly'}
LOGIN='''<!doctype html><html lang="pt-BR"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><title>NEXUS SCORE · Login</title>
<style>*{box-sizing:border-box}body{margin:0;background:#080e1c;color:#e9f2ff;font:16px system-ui;min-height:100vh;display:grid;place-items:center;padding:18px}.panel{width:min(410px,100%);border:1px solid #263450;background:#101a2c;border-radius:20px;padding:30px;box-shadow:0 20px 80px #0008}h1{margin:0 0 6px;font-size:28px}p{color:#a0afc8;font-size:14px;line-height:1.55}label{display:block;margin:24px 0 8px;color:#c3d0e5}input{width:100%;border-radius:12px;border:1px solid #32415e;background:#0b1525;color:white;padding:16px;font-size:18px}button{border:0;width:100%;padding:15px;border-radius:12px;background:#23d5aa;color:#04151c;font-size:16px;font-weight:750;margin-top:14px}.error{color:#ff919e}small{color:#8293ad}.logo{color:#23d5aa;font-weight:900;letter-spacing:3px}</style>
<body><form class="panel" action="/login" method="POST"><div class="logo">◈ NEXUS SCORE</div><h1>Seu painel, na nuvem.</h1><p>Entre para consultar o histórico de partidas, termômetros, mercados e o P/L registrado na Bolsa.</p><label for="pw">Senha do NEXUS WEB</label><input id="pw" name="password" type="password" required autocomplete="current-password" autofocus><button type="submit">Entrar no painel →</button><p class="error">%s</p><small>Área privada · Sem apostas automáticas</small></form></body></html>'''

class App(BaseHTTPRequestHandler):
    server_version='NexusWeb/0.1'
    def log_message(self, fmt, *args):
        print('%s %s'%(self.address_string(),fmt%args),flush=True)
    def send(self,status=200,content=b'',ctype='text/plain; charset=utf-8',more=None):
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
        if more:
            for k,v in more.items():self.send_header(k,v)
        self.end_headers()
        self.wfile.write(content)
    def page(self,source,error=''):
        self.send(200,(source%html.escape(error)).encode(),'text/html; charset=utf-8')
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz':
            return self.send(200,b'OK')
        if not is_authorized(self.headers):
            if path.startswith('/api/'):return self.send(401,b'{"error":"Nao autorizado"}','application/json')
            return self.page(LOGIN)
        if path=='/logout':
            return self.send(302,b'',more={'Location':'/','Set-Cookie':f'{COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0'})
        if path=='/api/dashboard':
            return self.send(200,json.dumps(snapshot(),ensure_ascii=False).encode(),'application/json; charset=utf-8')
        if path=='/' or path=='/index.html':
            try:return self.send(200,(ROOT/'web'/'index.html').read_bytes(),'text/html; charset=utf-8')
            except OSError:return self.send(500,b'Interface indisponivel')
        if path in ('/style.css','/app.js','/data.json','/web/app.js','/web/style.css'):
            filename=path.rsplit('/',1)[-1]
            if filename not in ('style.css','app.js','data.json'):
                return self.send(404,b'Nao encontrado')
            asset=ROOT/'web'/filename
            kinds={'style.css':'text/css; charset=utf-8','app.js':'application/javascript; charset=utf-8','data.json':'application/json; charset=utf-8'}
            try:return self.send(200,asset.read_bytes(),kinds[filename])
            except OSError:return self.send(404,b'Dados indisponiveis')
        return self.send(404,b'Nao encontrado')
    def do_POST(self):
        if urlsplit(self.path).path!='/login':return self.send(405,b'Nao permitido')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2048:return self.send(400,b'Requisicao invalida')
            raw=self.rfile.read(length)
            password=parse_qs(raw.decode('utf-8')).get('password',[''])[0]
        except (ValueError,UnicodeError):return self.send(400,b'Requisicao invalida')
        # Rate limit por processo, sem confiar em X-Forwarded-For nao autenticado.
        with FAILED_LOCK:
            key=self.client_address[0];arr=FAILED.get(key,[])
            arr=[t for t in arr if time.monotonic()-t<600]
            if len(arr)>=10:return self.send(429,b'Muitas tentativas; aguarde 10 minutos')
            if not hmac.compare_digest(password,SECRET):
                arr.append(time.monotonic());FAILED[key]=arr
                return self.page(LOGIN,'Senha incorreta.')
            FAILED.pop(key,None)
        self.send(302,b'',more={'Location':'/','Set-Cookie':cookie()})

if __name__=='__main__':
    port=int(os.environ.get('PORT','3000'))
    ThreadingHTTPServer(('0.0.0.0',port),App).serve_forever()

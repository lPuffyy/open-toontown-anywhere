import http.server, os, re, json, hashlib, hmac, threading, time
D="/ot/data/phone_logs"; U="/ot/data/users.json"
LOCK=threading.Lock()
FAILS={}   # key -> [timestamps] of failed recovery attempts
def load():
    try: return json.load(open(U))
    except Exception: return {"open_registration":True,"users":{}}
def save(db):
    json.dump(db,open(U+".tmp","w"),indent=1); os.replace(U+".tmp",U); os.chmod(U,0o666)
def pbk(text,salt): return hashlib.pbkdf2_hmac("sha256",text.encode(),bytes.fromhex(salt),100000).hex()
def norm(s): return " ".join(s.lower().split())
def check_name_pw(name,pw):
    if not (2<=len(name)<=20) or not name.replace("_","").replace("-","").isalnum(): return "Usernames are 2-20 letters, numbers, - or _."
    if len(pw)<4: return "Passwords need at least 4 characters."
    return None
def auth(text):
    """returns (error or None, user record or None)"""
    if ":" not in text: return "Please enter a username and password.",None
    name,pw=text.split(":",1); name=name.strip().lower()
    e=check_name_pw(name,pw)
    if e: return e,None
    with LOCK:
        db=load(); u=db["users"].get(name)
        if u is None:
            if not db.get("open_registration",True): return "Unknown user. Ask a parent to add you.",None
            salt=os.urandom(16).hex(); u=db["users"][name]={"salt":salt,"hash":pbk(pw,salt),"dbkey":"user:"+name}
            save(db); return None,u
        # (the name exists: a new player picking a taken name gets here too, so say both)
        if not hmac.compare_digest(u["hash"],pbk(pw,u["salt"])): return "That name is taken, or the password is wrong. New here? Try another name.",None
        if u.get("banned"): return "This account has been banned.",None
        return None,u
def throttled(keys):
    now=time.time()
    for k in keys:
        FAILS[k]=[t for t in FAILS.get(k,[]) if now-t<3600]
        if len(FAILS[k])>=5: return True
    return False
def note_fail(keys):
    now=time.time()
    for k in keys: FAILS.setdefault(k,[]).append(now)
def set_recovery(text):
    parts=text.split("\n")
    if len(parts)<3: return "Fill in both boxes."
    err,u=auth(parts[0])
    if err or u is None: return err or "Sign in first."
    nick,toon=norm(parts[1]),norm(parts[2])
    if len(nick)<2 or len(toon)<2: return "Answers need at least 2 letters."
    name=parts[0].split(":",1)[0].strip().lower()
    with LOCK:
        db=load(); salt=os.urandom(16).hex()
        db["users"][name]["rec"]={"salt":salt,"nick":pbk(nick,salt),"toon":pbk(toon,salt)}
        save(db)
    return None
GENERIC="Those answers don't match. Ask a parent if you need help."
def recover(text,ip):
    parts=text.split("\n")
    if len(parts)<4: return "Fill in every box."
    name=parts[0].strip().lower(); nick,toon,newpw=norm(parts[1]),norm(parts[2]),parts[3]
    keys=("u:"+name,"ip:"+ip)
    if throttled(keys): return "Too many tries. Try again in an hour or ask a parent."
    e=check_name_pw(name,newpw)
    if e and e.startswith("Passwords"): return e
    with LOCK:
        db=load(); u=db["users"].get(name); rec=(u or {}).get("rec")
        ok=False
        if rec:
            a=hmac.compare_digest(rec["nick"],pbk(nick,rec["salt"]))
            b=hmac.compare_digest(rec["toon"],pbk(toon,rec["salt"]))
            ok=a and b
        else:
            pbk(nick,os.urandom(16).hex())  # keep timing similar
        if not ok:
            note_fail(keys); return GENERIC
        salt=os.urandom(16).hex(); u["salt"]=salt; u["hash"]=pbk(newpw,salt)
        save(db)
    FAILS.pop("u:"+name,None)
    return None
CLOG="/ot/data/logs/client.log"; CLOG_MAX=30*1024*1024; CLOG_RATE={}
def client_log(ip,text):
    now=time.time(); q=CLOG_RATE.setdefault(ip,[]); q[:]=[t for t in q if now-t<3600]
    if len(q)>=6000: return False
    try:
        if os.path.exists(CLOG) and os.path.getsize(CLOG)>CLOG_MAX: return False
        q.append(now)
        with LOCK, open(CLOG,"a",encoding="utf8") as f:
            line=text[:1500].replace(chr(10)," | ")
            f.write("%s %s %s%s"%(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(now)),ip,line,chr(10)))
    except Exception: return False
    return True
# ---- the moderator panel (/mod/): for accounts marked "admin" in users.json. The districts write who is playing to
# MOD/online-<district>.json and carry out the commands left in MOD/cmd/ (toontown/ai/ModToolsAI.py).
MOD="/ot/data/mod"; MOD_PAGE="/ot/mod.html"; MOD_LOG=os.path.join(MOD,"audit.log"); SESSION_HOURS=24*30
def mod_secret():
    p=os.path.join(MOD,"secret")
    try: return bytes.fromhex(open(p).read().strip())
    except Exception:
        os.makedirs(MOD,exist_ok=True); s=os.urandom(32); open(p,"w").write(s.hex()); os.chmod(p,0o600); return s
def mod_token(name):
    exp=str(int(time.time())+SESSION_HOURS*3600); msg=name+"|"+exp
    return msg+"|"+hmac.new(mod_secret(),msg.encode(),hashlib.sha256).hexdigest()
def mod_user(token):
    """the moderator's account name for a valid, unexpired session token from an account that is still an admin, else None"""
    try:
        name,exp,sig=token.split("|")
        if not hmac.compare_digest(sig,hmac.new(mod_secret(),(name+"|"+exp).encode(),hashlib.sha256).hexdigest()): return None
        if int(exp)<time.time(): return None
        u=load()["users"].get(name)
        return name if u and u.get("admin") and not u.get("banned") else None
    except Exception: return None
def mod_audit(by,what):
    os.makedirs(MOD,exist_ok=True)
    with LOCK, open(MOD_LOG,"a",encoding="utf8") as f: f.write("%s %s %s\n"%(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime()),by,what.replace("\n"," ")))
# the game's database (Astron's YAML files): accounts, their toons, and which account each toon belongs to
GAMEDB="/ot/src/astron/databases"; GAMEDB_CACHE={"t":0,"v":None}
def yaml_value(v):
    v=v.strip()
    if v.startswith("(") and v.endswith(")"): v=v[1:-1]
    if v.startswith('"') and v.endswith('"'): v=v[1:-1].replace('\\"','"')
    if v.startswith('"') and v.endswith('"'): v=v[1:-1]
    return v
def yaml_fields(path):
    out={}
    try:
        for line in open(path,encoding="utf8",errors="replace"):
            if line.startswith("class:"): out["class"]=line.split(":",1)[1].strip()
            elif line.startswith("  ") and ":" in line:
                k,v=line.strip().split(":",1)
                if k in ("ACCOUNT_AV_SET","ACCOUNT_ID","CREATED","LAST_LOGIN","ACCESS_LEVEL","setName","setMaxHp","setHp","setMoney","setBankMoney","setLastHood"): out[k]=yaml_value(v)
    except OSError: pass
    return out
def game_db():
    """{"accounts": {name: {created, lastLogin, toons:[{avId,name,maxHp,beans}]}}, "owner": {avId: name}}, read at most every 30 s"""
    if GAMEDB_CACHE["v"] is not None and time.time()-GAMEDB_CACHE["t"]<30: return GAMEDB_CACHE["v"]
    accounts={}; owner={}; names={}
    try: ids=json.load(open(os.path.join(GAMEDB,"accounts.json")))
    except Exception: ids={}
    for name,accId in ids.items():
        a=yaml_fields(os.path.join(GAMEDB,"astrondb","%s.yaml"%accId))
        toons=[]
        for avId in re.findall(r"\d+",a.get("ACCOUNT_AV_SET","")):
            if avId=="0": continue
            t=yaml_fields(os.path.join(GAMEDB,"astrondb","%s.yaml"%avId))
            if not t: continue
            owner[int(avId)]=name; names[int(avId)]=t.get("setName","")
            num=lambda k: int(t[k]) if t.get(k,"").lstrip("-").isdigit() else 0
            toons.append({"avId":int(avId),"name":t.get("setName",""),"maxHp":num("setMaxHp"),"beans":num("setMoney")+num("setBankMoney")})
        accounts[name]={"created":a.get("CREATED",""),"lastLogin":a.get("LAST_LOGIN",""),"toons":toons}
    GAMEDB_CACHE.update(t=time.time(),v={"accounts":accounts,"owner":owner,"names":names})
    return GAMEDB_CACHE["v"]
def mod_accounts():
    db=game_db(); online={t["avId"]:d["district"] for d in mod_state(False)["districts"] for t in d.get("toons",[])}
    out=[]
    for name,u in load()["users"].items():
        g=db["accounts"].get(name,{})
        toons=[dict(t,online=online.get(t["avId"],"")) for t in g.get("toons",[])]
        out.append({"name":name,"admin":bool(u.get("admin")),"banned":u.get("banned") or None,"recovery":bool(u.get("rec")),
                    "created":g.get("created",""),"lastLogin":g.get("lastLogin",""),"toons":toons,"online":any(t["online"] for t in toons)})
    return {"accounts":out}
REPORTS=os.path.join(MOD,"reports.jsonl"); REPORT_STATE=os.path.join(MOD,"reports-state.json")
def mod_reports():
    owner=game_db()["owner"]
    try: st=json.load(open(REPORT_STATE))
    except Exception: st={}
    online={t["avId"]:(d["district"],t["where"]) for d in mod_state(False)["districts"] for t in d.get("toons",[])}
    out=[]
    try: lines=open(REPORTS,encoding="utf8").read().splitlines()[-500:]
    except OSError: lines=[]
    for line in lines:
        try: r=json.loads(line)
        except ValueError: continue
        r["reporterAccount"]=owner.get(r.get("reporter"),""); r["targetAccount"]=owner.get(r.get("target"),"")
        r["targetOnline"]=online.get(r.get("target"))
        r.update(st.get(r["id"],{}))
        out.append(r)
    out.reverse()
    return {"reports":out,"open":sum(1 for r in out if r.get("status")!="resolved")}
def mod_state(withLog=True):
    accounts=game_db()["owner"]
    districts=[]
    for f in sorted(os.listdir(MOD)) if os.path.isdir(MOD) else []:
        if not (f.startswith("online-") and f.endswith(".json")): continue
        try: d=json.load(open(os.path.join(MOD,f)))
        except Exception: continue
        d["stale"]=time.time()-d.get("updated",0)>30
        for t in d.get("toons",[]): t["account"]=accounts.get(t["avId"],"")
        districts.append(d)
    if not withLog: return {"districts":districts}
    users=load()["users"]
    banned=[dict(name=k,**v["banned"]) if isinstance(v.get("banned"),dict) else {"name":k} for k,v in users.items() if v.get("banned")]
    try: log=open(MOD_LOG,encoding="utf8").read().splitlines()[-40:][::-1]
    except Exception: log=[]
    try: openReports=mod_reports()["open"]
    except Exception: openReports=0
    return {"now":int(time.time()),"districts":districts,"banned":banned,"log":log,"accountCount":len(users),"openReports":openReports}
def mod_command(action,avId,text,by,**extra):
    os.makedirs(os.path.join(MOD,"cmd"),exist_ok=True); os.makedirs(os.path.join(MOD,"done"),exist_ok=True)
    now=time.time()
    for sub in ("cmd","done"):                           # tidy up: the districts ignore commands older than a minute
        for f in os.listdir(os.path.join(MOD,sub)):
            p=os.path.join(MOD,sub,f)
            try:
                if now-os.path.getmtime(p)>180: os.remove(p)
            except OSError: pass
    cid="%d-%s.json"%(int(now*1000),os.urandom(3).hex()); p=os.path.join(MOD,"cmd",cid)
    json.dump(dict(extra,action=action,avId=int(avId),text=text,by=by,time=now),open(p+".tmp","w")); os.replace(p+".tmp",p)
    return cid
def mod_action(req,by):
    """returns (error or None, result dict)"""
    action=req.get("action"); text=str(req.get("text",""))[:250].strip()
    if action in ("message","kick"):
        avId=int(req.get("avId",0))
        if not avId: return "Pick a toon.",None
        if action=="message" and not text: return "Write a message.",None
        cid=mod_command(action,avId,text,by); mod_audit(by,"%s toon %s (%s) %s"%(action,avId,req.get("name",""),text)); return None,{"id":cid}
    if action=="broadcast":
        if not text: return "Write a message.",None
        cid=mod_command("message",0,text,by); mod_audit(by,"broadcast "+text); return None,{"id":cid}
    if action in ("ban","unban"):
        name=str(req.get("account","")).strip().lower()
        with LOCK:
            db=load(); u=db["users"].get(name)
            if u is None: return "No account called %s."%name,None
            if action=="ban":
                if u.get("admin"): return "Admin accounts can't be banned here.",None
                u["banned"]={"reason":text,"by":by,"time":int(time.time())}
            else: u.pop("banned",None)
            save(db)
        mod_audit(by,"%s account %s %s"%(action,name,text))
        ids=[]
        if action=="ban":                                # log out every toon of that account that is playing now
            for d in mod_state()["districts"]:
                for t in d.get("toons",[]):
                    if t.get("account")==name: ids.append(mod_command("ban",t["avId"],"This account has been banned."+(" Reason: "+text if text else ""),by))
        return None,{"ids":ids}
    if action=="edit": return mod_edit(req,by)
    if action in ("resolve","reopen"):
        rid=str(req.get("id",""))
        with LOCK:
            try: st=json.load(open(REPORT_STATE))
            except Exception: st={}
            if action=="resolve": st[rid]={"status":"resolved","resolvedBy":by,"resolvedAt":int(time.time()),"note":text}
            else: st.pop(rid,None)
            json.dump(st,open(REPORT_STATE+".tmp","w")); os.replace(REPORT_STATE+".tmp",REPORT_STATE)
        mod_audit(by,"%s report %s %s"%(action,rid,text)); return None,{}
    return "Unknown action.",None
def mod_result(cid):
    try: return json.load(open(os.path.join(MOD,"done",os.path.basename(cid))))
    except Exception: return {"ok":False,"pending":True}
def mod_wait(cid,seconds=8):
    end=time.time()+seconds
    while time.time()<end:
        r=mod_result(cid)
        if not r.get("pending"): return r
        time.sleep(0.25)
    return {"ok":False,"result":"No district answered. The game server may be restarting."}
def online_toon(avId):
    for d in mod_state(False)["districts"]:
        if d.get("stale"): continue
        for t in d.get("toons",[]):
            if t["avId"]==avId: return dict(t,district=d["district"])
    return None
EDIT_OPS=("money","bank","maxHp","heal","name","pinkSlips","emotes","teleport","gags","cheesy","maxtoon","gift")
def mod_toon(avId,by):
    """everything the panel shows on a toon's page: read from the database by a district, plus where it is now"""
    cid=mod_command("inspect",avId,"",by,anyDistrict=True); r=mod_wait(cid)
    if not r.get("ok"): return r.get("result") or "Could not read that toon.",None
    toon=r["result"]; db=game_db()
    toon["account"]=db["owner"].get(avId,""); toon["online"]=online_toon(avId)
    toon["friends"]=[{"avId":f,"name":db["names"].get(f,""),"online":bool(online_toon(f))} for f in toon.get("friends",[])]
    return None,toon
def mod_edit(req,by):
    avId=int(req.get("avId",0)); op=req.get("op")
    if not avId or op not in EDIT_OPS: return "Unknown change.",None
    value=req.get("value")
    if isinstance(value,str): value=value[:60]
    elif isinstance(value,list): value=[int(v) for v in value[:2]]
    elif value is not None: value=int(value)
    playing=online_toon(avId)
    cid=mod_command("edit",avId,"",by,anyDistrict=not playing,op=op,value=value,add=bool(req.get("add")))
    r=mod_wait(cid)
    mod_audit(by,"edit toon %s (%s) %s %s%s -> %s"%(avId,req.get("name",""),op,"+" if req.get("add") else "",value,r.get("result")))
    GAMEDB_CACHE["t"]=0                                   # names and beans may have changed
    if not r.get("ok"): return r.get("result") or "That didn't work.",None
    return None,{"result":r["result"],"live":bool(playing)}
def mod_items():
    try: return {"items":json.load(open(os.path.join(MOD,"items.json")))}
    except Exception: return {"items":[]}
class H(http.server.BaseHTTPRequestHandler):
    def reply(self,code,msg):
        self.send_response(code); self.end_headers(); self.wfile.write(msg.encode())
    def reply_json(self,code,obj):
        b=json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def mod_session(self):
        a=self.headers.get("Authorization","")
        return mod_user(a[7:]) if a.startswith("Bearer ") else None
    def do_GET(self):
        path=self.path.split("?")[0]
        if path in ("/mod","/mod/"):
            try: page=open(MOD_PAGE,"rb").read()
            except OSError: return self.reply(404,"")
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Cache-Control","no-store")
            self.send_header("X-Frame-Options","DENY"); self.send_header("Referrer-Policy","no-referrer"); self.end_headers(); return self.wfile.write(page)
        if path=="/mod/api/state":
            by=self.mod_session()
            if not by: return self.reply_json(401,{"error":"Sign in again."})
            return self.reply_json(200,dict(mod_state(),you=by))
        if path in ("/mod/api/accounts","/mod/api/reports","/mod/api/items"):
            if not self.mod_session(): return self.reply_json(401,{"error":"Sign in again."})
            return self.reply_json(200,{"accounts":mod_accounts,"reports":mod_reports,"items":mod_items}[path.rsplit("/",1)[1]]())
        if path=="/mod/api/toon":
            by=self.mod_session()
            if not by: return self.reply_json(401,{"error":"Sign in again."})
            q=dict(x.split("=",1) for x in self.path.split("?",1)[-1].split("&") if "=" in x)
            try: avId=int(q.get("avId","0"))
            except ValueError: avId=0
            err,toon=mod_toon(avId,by) if avId else ("Pick a toon.",None)
            return self.reply_json(400 if err else 200,{"error":err} if err else toon)
        if path=="/mod/api/result":
            if not self.mod_session(): return self.reply_json(401,{"error":"Sign in again."})
            q=dict(x.split("=",1) for x in self.path.split("?",1)[-1].split("&") if "=" in x)
            return self.reply_json(200,mod_result(q.get("id","")))
        self.reply(404,"")
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0")); raw=self.rfile.read(n); body=raw.decode("utf-8","replace") if n<4096 else ""
        ip=self.headers.get("X-Forwarded-For") or self.client_address[0]
        if self.path=="/mod/api/login":
            keys=("mod-ip:"+ip,)
            if throttled(keys): return self.reply_json(429,{"error":"Too many tries. Try again in an hour."})
            err,u=auth(body) if ":" in body and body.split(":",1)[0].strip().lower() in load()["users"] else ("No.",None)
            if err or not u or not u.get("admin"):
                note_fail(keys); return self.reply_json(403,{"error":"That account can't use the moderator panel."})
            name=body.split(":",1)[0].strip().lower(); mod_audit(name,"signed in from "+ip)
            return self.reply_json(200,{"token":mod_token(name),"name":name})
        if self.path=="/mod/api/action":
            by=self.mod_session()
            if not by: return self.reply_json(401,{"error":"Sign in again."})
            try: req=json.loads(body)
            except ValueError: return self.reply_json(400,{"error":"Bad request."})
            err,res=mod_action(req,by)
            return self.reply_json(400 if err else 200,{"error":err} if err else res)
        if self.path=="/auth":
            err,u=auth(body)
            if err: return self.reply(403,err)
            return self.reply(200,"ok" if u.get("rec") else "setup")
        if self.path=="/setrecovery":
            err=set_recovery(body); return self.reply(403 if err else 200,err or "ok")
        if self.path=="/recover":
            err=recover(body,ip); return self.reply(403 if err else 200,err or "ok")
        if self.path=="/__log":
            # a test session (page opened with ?log=1): keep what the game prints, with the time and the device's address
            return self.reply(204 if client_log(ip,body) else 429,"")
        name=re.sub(r"[^A-Za-z0-9_.-]","_",self.path.strip("/") or "log")
        with open(os.path.join(D,name+(".png" if name.startswith("shot") else ".txt")),"wb") as f: f.write(raw)
        self.reply(200,"ok")
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(("0.0.0.0",7381),H).serve_forever()

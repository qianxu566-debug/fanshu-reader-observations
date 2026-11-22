import datetime as dt
import gzip
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from card_fields import book_tags
from tracking import discover, merge, coverage

CN = dt.timezone(dt.timedelta(hours=8))
SITE = "https://qianxu566-debug.github.io/fanshu-reader/catalog.gz"
OUT = Path("days")
OUT.mkdir(exist_ok=True)
now = lambda: dt.datetime.now(CN)
day = now().date().isoformat()
path = OUT / (day + ".json.gz")
def save():
    temp = path.with_suffix(".tmp")
    temp.write_bytes(gzip.compress(json.dumps(state,separators=(",",":")).encode(),mtime=0))
    os.replace(temp,path)
def get(url):
    with urllib.request.urlopen(url,timeout=22) as r:
        return r.read()
def read(p):
    return json.loads(gzip.decompress(p.read_bytes()))

previous_file=OUT/((dt.date.fromisoformat(day)-dt.timedelta(days=1)).isoformat()+".json.gz")
yesterday=read(previous_file) if previous_file.exists() else {}
state=read(path) if path.exists() else dict(date=day,source="fanqienovel.com/api/book/info:readCount",targets=[],rows={},errors={})
first_discovery="discoveredAt" not in state
earlier_files=sorted(p for p in OUT.glob("????-??-??.json.gz") if p.name<path.name)
previous_targets=yesterday.get("targets") or (read(earlier_files[-1])["targets"] if earlier_files else [])
state["targets"]=merge(state["targets"],previous_targets,[])
if not state.get("refused") and time.time()-state.get("discoveredAt",0)>=3600:
    try:
        incoming,issues=discover(get)
        state["targets"]=merge(state["targets"],[],incoming)
        state["discoveryIssues"]=issues
        if not state["targets"]:raise RuntimeError("no tracking targets")
        state["discoveredAt"]=int(time.time())
    except urllib.error.HTTPError as e:
        if e.code in (401,403,429):state["refused"]=str(e)
        else:raise
    save()
def run():
    missing=[i for i in state["targets"] if i not in state["rows"] and not state["errors"].get(i,{}).get("unavailable")]
    missing.sort(key=lambda i:state["errors"].get(i,{}).get("tries",0))
    if not missing or state.get("refused"):
        return
    failures=0
    start=time.monotonic()
    seconds=60 if first_discovery or not state['rows'] else 540
    for i in missing:
        if now().date().isoformat()!=day or time.monotonic()-start>=seconds:break
        try:
            data=json.loads(get("https://fanqienovel.com/api/book/info?bookId="+i))
            book=data.get("data") or {}
            n=book.get("readCount")
            if data.get("code")!=0 or str(book.get("bookId"))!=i or not str(n).isascii() or not str(n).isdigit():
                raise ValueError("source "+str(data.get("code"))+" "+str(data.get("message",""))[:80]+" or missing readCount")
            if now().date().isoformat()!=day:break
            stamp=int(now().timestamp())
            state["rows"][i]=[stamp,int(n),book_tags(book)]
            state["errors"].pop(i,None)
            failures=0
        except Exception as e:
            fails=state["errors"].get(i,{}).get("tries",0)+1
            state["errors"][i]={"tries":fails,"reason":str(e)[:140]}
            if getattr(e,"code",0)==404 or "查无此书" in str(e):
                state["errors"][i]["unavailable"]=True
                time.sleep(.4)
                continue
            if getattr(e,"code",0) in (401,403,429):
                state["refused"]=str(e)
                break
            failures+=1
            if failures>=5:break
        if (len(state["rows"])+len(state["errors"]))%50==0:save()
        time.sleep(.4)
try:
    run()
finally:
    state["coverage"]=coverage(state,yesterday)
    save()
    print(day,len(state["rows"]),"/",len(state["targets"]),state.get("refused",""),flush=True)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:
            f.write("finished="+str(bool(len(state["rows"])==len(state["targets"]) or state.get("refused"))).lower()+"\n")


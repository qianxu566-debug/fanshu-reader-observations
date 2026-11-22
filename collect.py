import datetime as dt
import gzip
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

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
if path.exists():
    state=json.loads(gzip.decompress(path.read_bytes()))
else:
    src=json.loads(gzip.decompress(get(SITE)))
    ids=list(dict.fromkeys(b["id"] for b in src["books"]))
    if not ids or not all(isinstance(i,str) and i.isdigit() for i in ids):
        raise ValueError("invalid catalog")
    state=dict(date=day,source="fanqienovel.com/api/book/info:readCount",targets=ids,rows={},errors={})
    save()
def run():
    missing=[i for i in state["targets"] if i not in state["rows"]]
    missing.sort(key=lambda i:state["errors"].get(i,{}).get("tries",0))
    if not missing or state.get("refused"):
        return
    failures=0
    start=time.monotonic()
    seconds=540 if state['rows'] else 60
    for i in missing:
        if now().date().isoformat()!=day or time.monotonic()-start>=seconds:break
        try:
            data=json.loads(get("https://fanqienovel.com/api/book/info?bookId="+i))
            book=data.get("data") or {}
            n=book.get("readCount")
            if data.get("code")!=0 or str(book.get("bookId"))!=i or not str(n).isascii() or not str(n).isdigit():
                raise ValueError("source code "+str(data.get("code"))+" or missing readCount")
            if now().date().isoformat()!=day:break
            state["rows"][i]=[int(now().timestamp()),int(n)]
            state["errors"].pop(i,None)
            failures=0
        except Exception as e:
            fails=state["errors"].get(i,{}).get("tries",0)+1
            state["errors"][i]={"tries":fails,"reason":str(e)[:140]}
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
    save()
    print(day,len(state["rows"]),"/",len(state["targets"]),state.get("refused",""),flush=True)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:
            f.write("finished="+str(bool(len(state["rows"])==len(state["targets"]) or state.get("refused"))).lower()+"\n")


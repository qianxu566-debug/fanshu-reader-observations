import datetime as dt
import json
import re

CN=dt.timezone(dt.timedelta(hours=8))
def cn_day(seconds):
    return dt.datetime.fromtimestamp(seconds,CN).date().isoformat()

def card_fields(book, stamp):
    cats=book.get("categoryV2")
    if isinstance(cats,str):
        try:cats=json.loads(cats)
        except ValueError:cats=None
    tags=list(dict.fromkeys(c["Name"] for c in cats if isinstance(c,dict) and c.get("MainCategory") is False and isinstance(c.get("Name"),str) and c["Name"])) if isinstance(cats,list) else None
    stamp_last=book.get("lastPublishTime")
    published=int(stamp_last) if str(stamp_last).isdigit() and 0<int(stamp_last)<=stamp else None
    words=0 if published and cn_day(published)<cn_day(stamp) else None
    return [tags,published,words]

def chapter_words(book_id,day,get,deadline):
    import time
    def read(url):
        if time.monotonic()>=deadline:raise TimeoutError("chapter budget reached")
        time.sleep(.4)
        return get(url)
    raw=json.loads(read("https://fanqienovel.com/api/reader/directory/detail?bookId="+book_id))
    if raw.get("code")!=0:return None
    directory=raw.get("data") or {}
    chapters=[c for group in directory.get("chapterListWithVolume",[]) for c in group]
    items=directory.get("allItemIds") or []
    if not chapters or len(chapters)!=len(items) or {str(c.get("itemId")) for c in chapters}!=set(map(str,items)):return None
    todays=[]
    for c in chapters:
        ts=c.get("firstPassTime")
        if not str(ts).isdigit() or int(ts)<=0:return None
        if cn_day(int(ts))==day:todays.append(c)
    if not todays:return None
    total=0
    for c in todays:
        if c.get("needPay") or c.get("isChapterLock") or not str(c["itemId"]).isdigit():return None
        page=read("https://fanqienovel.com/reader/"+str(c["itemId"])).decode()
        words=re.search(r'"chapterWordNumber"\s*:\s*"(\d+)"',page)
        ts=re.search(r'"firstPassTime"\s*:\s*"(\d+)"',page)
        if not words or not ts or int(ts[1])!=int(c["firstPassTime"]):return None
        total+=int(words[1])
    return total

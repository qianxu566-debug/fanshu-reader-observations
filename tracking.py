"""Discover newly published catalog and rank IDs, keeping the existing tracking list."""
import gzip
import json
import urllib.error

SITE = "https://qianxu566-debug.github.io/fanshu-reader/"
BOARDS = {
    "peak":"https://fanqienovel.com/api/author/misc/top_book_list/v1/?limit=30&offset=0",
    **{name:"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/rank/rank_list/v2/?aid=13&limit=30&offset=0&type=1&side_type="+side
       for name,side in [("dark","13"),("hot","12"),("recommend","10")]},
}

def ids(rows,field):
    values=[r[field] for r in rows]
    if not values or not all(isinstance(i,str) and i.isascii() and i.isdigit() for i in values):
        raise ValueError("invalid or empty ID list")
    return values

def discover(get):
    found={}
    issues={}
    def fetch(name,load):
        try:
            found[name]=load()
        except Exception as e:
            issues[name]=str(e)[:150]
            if getattr(e,"code",None) in (401,403,429):
                raise
    fetch("catalog",lambda:ids(json.loads(gzip.decompress(get(SITE+"catalog.gz")))["books"],"id"))
    def ranks():
        dates=json.loads(get(SITE+"history/index.json"))
        day=max(dates)
        snapshot=json.loads(gzip.decompress(get(SITE+"history/"+day+".json.gz")))
        if snapshot["date"]!=day:raise ValueError("wrong rank date")
        return ids([b for scope in snapshot["scopes"] if scope.get("ok") for b in scope["rows"]],"id")
    fetch("categoryRanks",ranks)
    for name,url in BOARDS.items():
        def load():
            j=json.loads(get(url))
            if j.get("code")!=0:raise ValueError("official code "+str(j.get("code")))
            return ids(j["book_list"] if name=="peak" else j["data"]["result"],"book_id")
        fetch(name,load)
    return list(dict.fromkeys(i for source in found.values() for i in source)),issues

def merge(existing,previous,incoming):
    return list(dict.fromkeys([*existing,*previous,*incoming]))

def coverage(state,yesterday):
    total=len(state["targets"])
    n=len(state["rows"])
    both=len(state["rows"].keys() & yesterday.get("rows",{}).keys())
    return dict(targets=total,observed=n,paired=both,withoutBaseline=len(set(state["targets"])-yesterday.get("rows",{}).keys()),
                observed95=bool(total and 100*n>=95*total),paired95=bool(total and 100*both>=95*total))

import json,urllib.parse,subprocess,sys,time
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
JAR="/tmp/gt_cookies.txt"
def get(url):
    r=subprocess.run(["curl","-s","-m","30","-A",UA,"-b",JAR,"-c",JAR,"-w","\n%{http_code}",url],capture_output=True,text=True)
    body,_,code=r.stdout.rpartition("\n"); return code,body
get("https://trends.google.com/trends/?geo=CO")
def compare(terms,time_="today 3-m"):
    req={"comparisonItem":[{"keyword":t,"geo":"CO","time":time_} for t in terms],"category":0,"property":""}
    code,b=get("https://trends.google.com/trends/api/explore?hl=es&tz=300&req="+urllib.parse.quote(json.dumps(req)))
    if code!="200": return code,b[:200]
    w=json.loads(b[b.index("{"):])["widgets"]
    ts=[x for x in w if x["id"]=="TIMESERIES"][0]
    code,b=get("https://trends.google.com/trends/api/widgetdata/multiline?hl=es&tz=300&req="+urllib.parse.quote(json.dumps(ts["request"]))+"&token="+ts["token"])
    if code!="200": return code,b[:200]
    data=json.loads(b[b.index("{"):])["default"]["timelineData"]
    return "200",data
terms=sys.argv[1].split(",")
code,data=compare(terms)
if code!="200": print("ERROR",code,data); sys.exit()
n=len(data); first=data[:n//3]; last=data[-n//3:]
for i,t in enumerate(terms):
    a=sum(d["value"][i] for d in first)/len(first); z=sum(d["value"][i] for d in last)/len(last)
    print(f"{t:28s} promedio inicio {a:5.1f} → últimas semanas {z:5.1f}  ({'+' if z>=a else ''}{(z-a):.1f})")
print("periodo:",data[0]["formattedTime"],"→",data[-1]["formattedTime"])

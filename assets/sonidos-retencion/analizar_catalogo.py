import subprocess, json, sys, re, numpy as np
from pathlib import Path
def pcm(p, sr=22050):
    b = subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(p),"-ac","1","-ar",str(sr),"-f","f32le","-"],capture_output=True,check=True).stdout
    return np.frombuffer(b, np.float32), sr
def lufs(p):
    o = subprocess.run(["ffmpeg","-nostdin","-nostats","-i",str(p),"-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", o); P = re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", o)
    return float(I[-1]) if I else None, float(P[-1]) if P else None
out = {}
root = Path(sys.argv[1])
for p in sorted(root.rglob("*")):
    if p.suffix not in (".mp3",".wav"): continue
    x, sr = pcm(p); win = int(sr*0.01)
    env = np.sqrt(np.convolve(x**2, np.ones(win)/win, mode="same"))
    pk = int(np.argmax(env)); thr = env.max()*0.1
    act = np.where(env > thr)[0]
    I, P = lufs(p)
    out[str(p.relative_to(root))] = {"dur": round(len(x)/sr,3), "pico_s": round(pk/sr,3),
        "inicio_audible_s": round(act[0]/sr,3), "fin_audible_s": round(act[-1]/sr,3), "lufs": I, "peak_db": P}
json.dump(out, sys.stdout, indent=1, ensure_ascii=False)

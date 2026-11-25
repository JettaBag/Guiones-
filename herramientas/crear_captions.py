#!/usr/bin/env python3
"""Convierte el JSON de transcribir-local (forma Scribe) a Caption[] de @remotion/captions."""
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
caps = [{"text": " " + w["text"], "startMs": int(w["start"] * 1000), "endMs": int(w["end"] * 1000),
         "timestampMs": None, "confidence": w.get("logprob")} for w in d["words"] if w.get("type", "word") == "word"]
json.dump(caps, open(dst, "w"), ensure_ascii=False)
print(f"{len(caps)} captions -> {dst}")

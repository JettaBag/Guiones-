#!/usr/bin/env python3
"""Revisa contactos contra el historial permanente (historial-contactos.json).

Uso:
  python3 scripts/revisar_duplicados.py auditar
      Busca repetidos dentro del historial.
  python3 scripts/revisar_duplicados.py revisar candidatos.json
      Clasifica cada candidato en: nuevo, repetido (se descarta) o posible repetido.
  python3 scripts/revisar_duplicados.py agregar candidatos.json --lista "Lista 6"
      Igual que revisar, y además guarda en el historial los nuevos y los posibles.

candidatos.json: lista de objetos con al menos "nombre" y "perfil" (link),
y opcionalmente "whatsapp", "otros_numeros" (lista), "usuarios" (lista de @usuarios).

Reglas:
  - Repetido (se descarta): mismo número normalizado (sin espacios, guiones,
    paréntesis ni +57/57 al inicio), o el mismo usuario de Instagram, TikTok o
    Facebook (en cualquier red), o el mismo link de perfil.
  - Posible repetido (no se entrega como nuevo): mismo nombre de negocio
    normalizado, nombre muy parecido, o usuario que solo cambia en puntos o
    guiones bajos.
"""
import json, re, sys, unicodedata, difflib, urllib.parse, datetime, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(RAIZ, "historial-contactos.json")

def telefono(s):
    s = re.sub(r"\D", "", str(s or ""))
    if len(s) == 12 and s.startswith("57"):
        s = s[2:]
    return s if len(s) == 10 and s.startswith("3") else ""

def _sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")

def nombre(s):
    return re.sub(r"[^a-z0-9]", "", _sin_tildes(re.sub(r"\(.*?\)", "", s or "")))

def usuario_de_link(url):
    u = urllib.parse.urlparse(url or ""); host = u.netloc.lower().replace("www.", "")
    p = [x for x in u.path.split("/") if x]
    if not p:
        return ("web:" + host) if host else ""
    if "tiktok.com" in host or "instagram.com" in host or "wa.me" in host:
        return "@" + p[0].lstrip("@").lower()
    if "facebook.com" in host:
        if p[0] in ("people", "p") and len(p) >= 2:
            m = re.search(r"\d{8,}", p[-1])
            return ("fb:" + m.group(0)) if m else "@" + p[1].lower()
        return ("fb:" + p[0]) if p[0].isdigit() else "@" + p[0].lower()
    return "web:" + host

def claves(c):
    tels = {telefono(c.get("whatsapp"))} | {telefono(x) for x in c.get("otros_numeros", [])}
    tels.discard("")
    us = {usuario_de_link(c.get("perfil"))} | {"@" + x.lstrip("@").lower().rstrip(".") for x in c.get("usuarios", [])}
    us.discard("")
    return tels, us, nombre(c.get("nombre"))

def cargar():
    with open(HIST, encoding="utf-8") as f:
        return json.load(f)

def comparar(c, hist):
    tels, us, nn = claves(c)
    for h in hist["contactos"]:
        if tels & set(h["telefonos"]):
            return "repetido", h, "mismo número"
        if us & set(h["usuarios"]):
            return "repetido", h, "misma cuenta"
    for h in hist["contactos"]:
        su = {re.sub(r"[._]", "", x) for x in us if x.startswith("@")}
        hu = {re.sub(r"[._]", "", x) for x in h["usuarios"] if x.startswith("@")}
        if len(nn) >= 4 and nn == h["nombre_normalizado"]:
            return "posible", h, "mismo nombre de negocio"
        if su & hu:
            return "posible", h, "usuario casi igual"
        if len(nn) >= 6 and difflib.SequenceMatcher(None, nn, h["nombre_normalizado"]).ratio() >= 0.93:
            return "posible", h, "nombre muy parecido"
    return "nuevo", None, ""

def revisar(path, lista=None):
    hist = cargar()
    cands = json.load(open(path, encoding="utf-8"))
    res = {"nuevo": [], "posible": [], "repetido": []}
    vistos = {"contactos": list(hist["contactos"])}
    for c in cands:
        tipo, h, motivo = comparar(c, vistos)
        res[tipo].append((c, h, motivo))
        if tipo != "repetido":   # evita repetidos dentro del mismo lote
            tels, us, nn = claves(c)
            vistos["contactos"].append({"nombre": c.get("nombre"), "lista": lista or "lote", "telefonos": sorted(tels), "usuarios": sorted(us), "nombre_normalizado": nn})
    print(f"{len(res['nuevo'])} contactos nuevos · {len(res['repetido'])} repetidos descartados · {len(res['posible'])} posibles repetidos")
    for c, h, m in res["repetido"]:
        print(f"  REPETIDO  {c.get('nombre')}  → ya entregado como {h['nombre']} ({h['lista']}) · {m}")
    for c, h, m in res["posible"]:
        print(f"  POSIBLE   {c.get('nombre')}  ~ {h['nombre']} ({h['lista']}) · {m}")
    if lista:
        hoy = datetime.date.today().isoformat()
        for tipo in ("nuevo", "posible"):
            for c, h, m in res[tipo]:
                tels, us, nn = claves(c)
                hist["contactos"].append({"id": c.get("id", ""), "lista": lista, "nombre": c.get("nombre"), "perfil": c.get("perfil", ""),
                    "telefonos": sorted(tels), "usuarios": sorted(us), "nombre_normalizado": nn, "entregado": hoy,
                    **({"posible_repetido_de": h["nombre"], "motivo": m} if tipo == "posible" else {})})
        for c, h, m in res["repetido"]:
            hist.setdefault("descartados", []).append({"lista": lista, "nombre": c.get("nombre"), "perfil": c.get("perfil", ""), "repetido_de": h["nombre"], "motivo": m, "fecha": hoy})
        with open(HIST, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=1)
        print("Historial actualizado:", len(hist["contactos"]), "contactos")
    return res

def auditar():
    hist = cargar(); cs = hist["contactos"]; n = 0
    for i, a in enumerate(cs):
        for b in cs[i+1:]:
            if set(a["telefonos"]) & set(b["telefonos"]) or set(a["usuarios"]) & set(b["usuarios"]):
                n += 1; print("REPETIDO:", a["nombre"], f"({a['lista']})", "=", b["nombre"], f"({b['lista']})")
    print(f"{len(cs)} contactos en el historial · {n} repetidos exactos")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "auditar":
        auditar()
    elif len(sys.argv) >= 3 and sys.argv[1] in ("revisar", "agregar"):
        lista = sys.argv[sys.argv.index("--lista") + 1] if "--lista" in sys.argv else None
        revisar(sys.argv[2], lista if sys.argv[1] == "agregar" else None)
    else:
        print(__doc__)

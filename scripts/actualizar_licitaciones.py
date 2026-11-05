#!/usr/bin/env python3
"""
licitom AGUA · actualización diaria automática (se ejecuta en GitHub Actions).

Qué hace cada mañana:
  1. Recupera los datos publicados el día anterior (datos/agua.atom y datos/estado.json) desde la propia web.
  2. Lee las novedades de la sindicación oficial de la Plataforma de Contratación del Sector Público:
       - modo diario: feed Atom en vivo, página a página, hasta llegar a lo ya leído;
       - modo inicial o de recuperación: ZIP mensuales de datos abiertos (mes actual y anterior).
  3. Se queda sólo con las licitaciones del ciclo integral del agua (filtro amplio: CPV del agua
     o término del agua). El filtro fino de O&M lo aplica la aplicación en el navegador.
  4. Publica datos/agua.atom (últimos VENTANA_DIAS días, una versión por licitación) y datos/estado.json.

Sólo usa la biblioteca estándar de Python: no hay que instalar nada.
Si una fuente falla, se conservan los datos anteriores y el código de salida es distinto de 0.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

VERSION = "1.0"
VENTANA_DIAS = 60          # antigüedad máxima de lo publicado (por fecha de última actualización)
SOLAPE_HORAS = 30          # se relee un día y pico hacia atrás para no perder nada
MAX_PAGINAS = 80           # techo del modo diario (500 entradas por página)
UA = "licitom-agua/1.0 (+https://github.com; actualizacion diaria de datos abiertos)"

BASE = os.environ.get("LICITOM_BASE", "https://contrataciondelsectorpublico.gob.es/sindicacion")
FUENTES = [
    {"nombre": "perfiles_placsp",
     "feed": f"{BASE}/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom",
     "zip": f"{BASE}/sindicacion_643/licitacionesPerfilesContratanteCompleto3_{{aaaamm}}.zip"},
    {"nombre": "plataformas_agregadas",
     "feed": f"{BASE}/sindicacion_1044/PlataformasAgregadasSinMenores.atom",
     "zip": f"{BASE}/sindicacion_1044/PlataformasAgregadasSinMenores_{{aaaamm}}.zip"},
]

NS = {
    "": "http://www.w3.org/2005/Atom",
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
    "cac-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "at": "http://purl.org/atompub/tombstones/1.0",
}
for _p, _u in NS.items():
    ET.register_namespace(_p, _u)
ATOM = NS[""]

# --- filtro amplio del ciclo del agua (mismo vocabulario que la aplicación) ---------------------
CPV_AGUA = ("651", "904")
PALABRAS_AGUA = [
    "edar", "etap", "edam", "idam", "ebar", "depuradora", "depuradoras", "depuracion de aguas",
    "aguas residuales", "potabilizadora", "potabilizadoras", "potabilizacion", "agua potable", "desaladora",
    "desaladoras", "desalinizadora", "desalinizadoras", "desalacion", "desalinizacion", "osmosis inversa",
    "tratamiento de aguas", "tratamiento de agua", "agua regenerada", "reutilizacion de aguas", "ciclo integral del agua",
    "ciclo del agua", "abastecimiento de agua", "abastecimiento en alta", "red de abastecimiento", "abastecimiento y saneamiento",
    "saneamiento y depuracion", "red de saneamiento", "alcantarillado", "estacion de bombeo", "estaciones de bombeo",
    "bombeo de aguas", "tanque de tormentas", "tanques de tormenta", "emisario submarino", "lodos de depuradora",
    "depositos de agua", "captaciones de agua", "red de distribucion de agua",
    # extra (más amplio que la app; la app vuelve a filtrar)
    "saneamiento", "abastecimiento", "depuracion", "aguas pluviales", "colector", "colectores",
]


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s)


_KW = []
for _k in PALABRAS_AGUA:
    _n = norm(_k)
    _KW.append(re.compile(rf"(?<![a-z0-9]){re.escape(_n)}(?![a-z0-9])") if len(_n) <= 5 else re.compile(re.escape(_n)))


def es_agua(texto: str, cpvs: list[str]) -> bool:
    if any(c.startswith(CPV_AGUA) for c in cpvs):
        return True
    t = norm(texto)
    return any(k.search(t) for k in _KW)


# --- utilidades -------------------------------------------------------------------------------
def ahora() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def log(msg: str) -> None:
    print(f"[{ahora():%H:%M:%S}] {msg}", flush=True)


def http_get(url: str, destino=None, intentos: int = int(os.environ.get("LICITOM_REINTENTOS", 4)), timeout: int = 180):
    """Descarga con reintentos. Devuelve bytes (o escribe en `destino`). None si 404."""
    espera = 10
    for i in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if destino is None:
                    return r.read()
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    destino.write(b)
                return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or i == intentos:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == intentos:
                raise
        log(f"  reintento {i} en {espera}s: {url}")
        time.sleep(espera)
        espera *= 2
        if destino is not None:
            destino.seek(0)
            destino.truncate()
    return None


# --- lectura de entradas ----------------------------------------------------------------------
def entradas_de_feed(data: bytes):
    """Devuelve (entradas, tombstones, next_url, feed_updated). entradas: lista de (id, updated, Element)."""
    root = ET.fromstring(data)
    if local(root.tag) != "feed":
        raise ValueError("el documento no es un feed Atom")
    nxt = None
    for l in root.findall(f"{{{ATOM}}}link"):
        if l.get("rel") == "next":
            nxt = l.get("href")
    upd = root.findtext(f"{{{ATOM}}}updated")
    ents, tombs = [], []
    for e in root:
        n = local(e.tag)
        if n == "entry":
            uid = e.findtext(f"{{{ATOM}}}id")
            if uid:
                ents.append((uid.strip(), parse_dt(e.findtext(f"{{{ATOM}}}updated")), e))
        elif n == "deleted-entry" and e.get("ref"):
            tombs.append((e.get("ref"), parse_dt(e.get("when")), e))
    return ents, tombs, nxt, upd


def entrada_es_agua(e) -> bool:
    titulo = e.findtext(f"{{{ATOM}}}title") or ""
    resumen = e.findtext(f"{{{ATOM}}}summary") or ""
    cpvs = [x.text.strip() for x in e.iter() if local(x.tag) == "ItemClassificationCode" and x.text]
    proyecto = ""
    for x in e.iter():
        if local(x.tag) == "ProcurementProject":
            proyecto = next((y.text for y in x if local(y.tag) == "Name" and y.text), "")
            break
    return es_agua(f"{titulo} {resumen} {proyecto}", cpvs)


class Almacen:
    """Una versión (la más reciente) por licitación."""

    def __init__(self):
        self.ent: dict[str, tuple[datetime | None, ET.Element]] = {}
        self.tomb: dict[str, tuple[datetime | None, ET.Element]] = {}
        self.nuevas = 0

    def poner(self, uid, upd, el, nueva_cuenta=True):
        cur = self.ent.get(uid)
        if cur is None or (upd and (cur[0] is None or upd > cur[0])):
            if cur is None and nueva_cuenta:
                self.nuevas += 1
            self.ent[uid] = (upd, el)

    def procesar(self, data: bytes, desde: datetime | None, stats: dict):
        ents, tombs, nxt, upd = entradas_de_feed(data)
        fechas = [u for _, u, _ in ents if u]
        for uid, u, el in ents:
            stats["leidas"] += 1
            if desde and u and u < desde:
                continue
            if entrada_es_agua(el):
                stats["agua"] += 1
                self.poner(uid, u, el)
        for uid, u, el in tombs:
            if uid in self.ent:
                self.tomb[uid] = (u, el)
        return nxt, (max(fechas) if fechas else None), (min(fechas) if fechas else None), upd

    def recortar(self, limite: datetime):
        for d in (self.ent, self.tomb):
            for k in [k for k, (u, _) in d.items() if u and u < limite]:
                del d[k]

    def escribir(self, ruta: str, actualizado: str):
        root = ET.Element(f"{{{ATOM}}}feed")
        ET.SubElement(root, f"{{{ATOM}}}id").text = "licitom-agua:ciclo-integral-del-agua"
        ET.SubElement(root, f"{{{ATOM}}}title").text = "licitom AGUA · licitaciones del ciclo integral del agua"
        ET.SubElement(root, f"{{{ATOM}}}updated").text = actualizado
        orden = sorted(self.ent.items(), key=lambda kv: kv[1][0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for _, (_, el) in orden:
            root.append(el)
        for _, (_, el) in self.tomb.items():
            root.append(el)
        tmp = ruta + ".tmp"
        ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
        os.replace(tmp, ruta)


# --- modos de lectura -------------------------------------------------------------------------
def meses(n: int) -> list[str]:
    d = ahora().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    return out


def leer_zip_mensual(f: dict, aaaamm: str, alm: Almacen, desde, stats) -> bool:
    url = f["zip"].format(aaaamm=aaaamm)
    log(f"  ZIP {aaaamm}: {url}")
    with tempfile.TemporaryFile() as tmp:
        ok = http_get(url, destino=tmp, timeout=900)
        if not ok:
            log(f"  ZIP {aaaamm} no disponible")
            if aaaamm == meses(1)[0]:
                stats["avisos"].append(f"el ZIP del mes en curso ({aaaamm}) aún no está disponible")
            return False
        tmp.seek(0)
        with zipfile.ZipFile(tmp) as z:
            nombres = [n for n in z.namelist() if n.lower().endswith((".atom", ".xml"))]
            for n in nombres:
                alm.procesar(z.read(n), desde, stats)
                stats["paginas"] += 1
    return True


def leer_feed_diario(f: dict, alm: Almacen, desde: datetime, stats) -> bool:
    """True si llegó hasta `desde`; False si agotó el techo de páginas."""
    url = f["feed"]
    while url and stats["paginas"] < MAX_PAGINAS:
        data = http_get(url)
        if data is None:
            raise RuntimeError(f"feed no encontrado: {url}")
        nxt, mx, mn, upd = alm.procesar(data, desde, stats)
        stats["paginas"] += 1
        if stats["paginas"] == 1:
            stats["feed_actualizado"] = upd
        if mx and mx < desde:
            return True
        url = nxt
    return url is None


def cargar_previo(base: str | None, alm: Almacen) -> dict:
    if not base:
        return {}
    base = base.rstrip("/") + "/"
    try:
        est = http_get(base + "estado.json", intentos=2, timeout=60)
        if not est:
            log("Sin datos previos publicados: carga inicial.")
            return {}
        estado = json.loads(est)
        data = http_get(base + "agua.atom", intentos=2, timeout=300)
        if data:
            ents, tombs, _, _ = entradas_de_feed(data)
            for uid, u, el in ents:
                alm.poner(uid, u, el, nueva_cuenta=False)
            for uid, u, el in tombs:
                alm.tomb[uid] = (u, el)
            log(f"Datos previos: {len(ents)} licitaciones (a {estado.get('actualizado')}).")
        return estado
    except Exception as e:  # noqa: BLE001
        log(f"No se pudieron recuperar los datos previos ({e}): carga inicial.")
        return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="datos")
    ap.add_argument("--previo", default=os.environ.get("LICITOM_PREVIO"), help="URL de la carpeta datos/ publicada")
    ap.add_argument("--inicial", action="store_true", help="forzar carga desde los ZIP mensuales")
    a = ap.parse_args(argv)
    os.makedirs(a.salida, exist_ok=True)

    alm = Almacen()
    previo = cargar_previo(a.previo, alm)
    marcas = previo.get("marcas", {})
    t0 = ahora()
    estado = {"version": VERSION, "ventana_dias": VENTANA_DIAS, "ultimo_intento": t0.isoformat(timespec="seconds"),
              "actualizado": previo.get("actualizado"), "marcas": dict(marcas), "fuentes": {}, "incidencias": []}
    fallos = 0
    for f in FUENTES:
        st = {"modo": "", "paginas": 0, "leidas": 0, "agua": 0, "avisos": []}
        marca = parse_dt(marcas.get(f["nombre"]))
        try:
            if a.inicial or not marca or t0 - marca > timedelta(days=25):
                st["modo"] = "inicial (ZIP mensuales)"
                desde = t0 - timedelta(days=VENTANA_DIAS)
                leidos = [leer_zip_mensual(f, m, alm, desde, st) for m in meses(3)]
                if not any(leidos):
                    raise RuntimeError("no se pudo descargar ningún ZIP mensual")
            else:
                st["modo"] = "diario (feed en vivo)"
                desde = marca - timedelta(hours=SOLAPE_HORAS)
                if not leer_feed_diario(f, alm, desde, st):
                    st["avisos"].append(f"más de {MAX_PAGINAS} páginas: se completa con el ZIP del mes")
                    leer_zip_mensual(f, meses(1)[0], alm, desde, st)
            estado["marcas"][f["nombre"]] = t0.isoformat(timespec="seconds")
            log(f"{f['nombre']}: {st['modo']} · {st['paginas']} páginas · {st['leidas']} entradas · {st['agua']} del agua")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            st["error"] = str(e)
            estado["incidencias"].append(f"{f['nombre']}: no se pudo leer la fuente oficial ({e}). Se mantienen los datos anteriores.")
            log(f"ERROR {f['nombre']}: {e}")
        for av in st["avisos"]:
            estado["incidencias"].append(f"{f['nombre']}: {av}")
        estado["fuentes"][f["nombre"]] = st

    alm.recortar(t0 - timedelta(days=VENTANA_DIAS))
    if fallos < len(FUENTES):
        estado["actualizado"] = t0.isoformat(timespec="seconds")
    estado["licitaciones"] = len(alm.ent)
    estado["nuevas_o_actualizadas"] = alm.nuevas
    alm.escribir(os.path.join(a.salida, "agua.atom"), estado["actualizado"] or t0.isoformat(timespec="seconds"))
    with open(os.path.join(a.salida, "estado.json"), "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    log(f"Publicadas {len(alm.ent)} licitaciones del agua · fallos de fuente: {fallos}")
    return 0 if fallos == 0 else (2 if fallos == len(FUENTES) else 1)


if __name__ == "__main__":
    sys.exit(main())

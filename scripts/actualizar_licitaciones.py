#!/usr/bin/env python3
"""licitom AGUA - actualizacion automatica limitada al mes actual."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone

VERSION = "1.1-mes-actual"
UA = "licitom-agua/1.1 (+GitHub Actions; datos abiertos)"
BASE = "https://contrataciondelsectorpublico.gob.es/sindicacion"

FUENTES = [
    {
        "nombre": "perfiles_placsp",
        "zip": f"{BASE}/sindicacion_643/licitacionesPerfilesContratanteCompleto3_{{aaaamm}}.zip",
    },
    {
        "nombre": "plataformas_agregadas",
        "zip": f"{BASE}/sindicacion_1044/PlataformasAgregadasSinMenores_{{aaaamm}}.zip",
    },
]

ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("", ATOM)

CPV_AGUA = ("651", "904")
PALABRAS_AGUA = [
    "edar", "etap", "edam", "idam", "ebar", "depuradora", "depuracion de aguas",
    "aguas residuales", "potabilizadora", "potabilizacion", "agua potable",
    "desaladora", "desalinizadora", "desalacion", "desalinizacion", "osmosis inversa",
    "tratamiento de aguas", "tratamiento de agua", "agua regenerada", "reutilizacion de aguas",
    "ciclo integral del agua", "ciclo del agua", "abastecimiento de agua",
    "abastecimiento en alta", "red de abastecimiento", "abastecimiento y saneamiento",
    "saneamiento y depuracion", "red de saneamiento", "saneamiento", "alcantarillado",
    "estacion de bombeo", "estaciones de bombeo", "bombeo de aguas",
    "tanque de tormentas", "tanques de tormenta", "emisario submarino",
    "lodos de depuradora", "depositos de agua", "captaciones de agua",
    "red de distribucion de agua", "colector", "colectores", "aguas pluviales",
]


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def log(texto: str) -> None:
    print(f"[{ahora():%H:%M:%S}] {texto}", flush=True)


def norm(texto: str | None) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s)


PATRONES = []
for palabra in PALABRAS_AGUA:
    p = norm(palabra)
    if len(p) <= 5:
        PATRONES.append(re.compile(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])"))
    else:
        PATRONES.append(re.compile(re.escape(p)))


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_dt(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        d = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def es_agua(entry: ET.Element) -> bool:
    titulo = entry.findtext(f"{{{ATOM}}}title") or ""
    resumen = entry.findtext(f"{{{ATOM}}}summary") or ""
    cpvs = [
        x.text.strip()
        for x in entry.iter()
        if local(x.tag) == "ItemClassificationCode" and x.text
    ]
    if any(c.startswith(CPV_AGUA) for c in cpvs):
        return True

    nombres = []
    for x in entry.iter():
        if local(x.tag) == "Name" and x.text:
            nombres.append(x.text)
    contenido = norm(" ".join([titulo, resumen, *nombres]))
    return any(p.search(contenido) for p in PATRONES)


def http_descargar(url: str, destino, intentos: int = 3) -> None:
    espera = 8
    for intento in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=900) as r:
                while True:
                    bloque = r.read(1024 * 1024)
                    if not bloque:
                        break
                    destino.write(bloque)
            return
        except Exception:
            if intento == intentos:
                raise
            import time
            time.sleep(espera)
            espera *= 2
            destino.seek(0)
            destino.truncate()


def leer_atom(data: bytes):
    root = ET.fromstring(data)
    if local(root.tag) != "feed":
        return []
    salida = []
    for e in root:
        if local(e.tag) != "entry":
            continue
        uid = e.findtext(f"{{{ATOM}}}id")
        if not uid:
            continue
        upd = parse_dt(e.findtext(f"{{{ATOM}}}updated"))
        salida.append((uid.strip(), upd, e))
    return salida


def procesar_zip(url: str, nombre: str, almacen: dict, estadistica: dict) -> None:
    log(f"ZIP MES ACTUAL: {url}")
    with tempfile.TemporaryFile() as tmp:
        http_descargar(url, tmp)
        tmp.seek(0)
        with zipfile.ZipFile(tmp) as z:
            atom_files = [n for n in z.namelist() if n.lower().endswith((".atom", ".xml"))]
            if not atom_files:
                raise RuntimeError("el ZIP no contiene ficheros .atom/.xml")
            for fichero in atom_files:
                estadistica["paginas"] += 1
                for uid, upd, entry in leer_atom(z.read(fichero)):
                    estadistica["leidas"] += 1
                    if not es_agua(entry):
                        continue
                    estadistica["agua"] += 1
                    anterior = almacen.get(uid)
                    if anterior is None or (upd and (anterior[0] is None or upd > anterior[0])):
                        almacen[uid] = (upd, entry)
    log(
        f"{nombre}: {estadistica['paginas']} ficheros Atom - "
        f"{estadistica['leidas']} entradas - {estadistica['agua']} relacionadas con agua"
    )


def escribir_atom(ruta: str, almacen: dict, actualizado: str) -> None:
    root = ET.Element(f"{{{ATOM}}}feed")
    ET.SubElement(root, f"{{{ATOM}}}id").text = "licitom-agua:mes-actual"
    ET.SubElement(root, f"{{{ATOM}}}title").text = "licitom AGUA - licitaciones del mes actual"
    ET.SubElement(root, f"{{{ATOM}}}updated").text = actualizado

    minimo = datetime.min.replace(tzinfo=timezone.utc)
    orden = sorted(almacen.values(), key=lambda x: x[0] or minimo, reverse=True)
    for _, entry in orden:
        root.append(entry)

    tmp = ruta + ".tmp"
    ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, ruta)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default="datos")
    # Se conserva por compatibilidad con actualizar.yml, aunque esta version reconstruye solo el mes actual.
    parser.add_argument("--previo", default=None)
    args = parser.parse_args(argv)

    os.makedirs(args.salida, exist_ok=True)
    inicio = ahora()
    aaaamm = inicio.strftime("%Y%m")

    log(f"Actualizacion de licitom AGUA: SOLO MES ACTUAL ({aaaamm})")

    almacen = {}
    estado = {
        "version": VERSION,
        "modo": "mes_actual",
        "mes": aaaamm,
        "ultimo_intento": inicio.isoformat(timespec="seconds"),
        "actualizado": None,
        "licitaciones": 0,
        "fuentes": {},
        "incidencias": [],
    }

    fallos = 0
    for fuente in FUENTES:
        st = {"paginas": 0, "leidas": 0, "agua": 0}
        url = fuente["zip"].format(aaaamm=aaaamm)
        try:
            procesar_zip(url, fuente["nombre"], almacen, st)
            st["ok"] = True
        except Exception as e:
            fallos += 1
            st["ok"] = False
            st["error"] = str(e)
            estado["incidencias"].append(
                f"{fuente['nombre']}: no se pudo leer el ZIP del mes actual ({e})"
            )
            log(f"ERROR {fuente['nombre']}: {e}")
        estado["fuentes"][fuente["nombre"]] = st

    if fallos < len(FUENTES):
        estado["actualizado"] = ahora().isoformat(timespec="seconds")

    estado["licitaciones"] = len(almacen)

    actualizado = estado["actualizado"] or inicio.isoformat(timespec="seconds")
    escribir_atom(os.path.join(args.salida, "agua.atom"), almacen, actualizado)

    with open(os.path.join(args.salida, "estado.json"), "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

    log(f"Publicadas {len(almacen)} licitaciones del agua del mes {aaaamm}; fallos: {fallos}")

    # 0: bien; 1: una fuente fallo; 2: fallaron ambas.
    return 0 if fallos == 0 else (2 if fallos == len(FUENTES) else 1)


if __name__ == "__main__":
    sys.exit(main())

"""Robô do Bom dia: coleta notícias, foto da NASA, "neste dia" e palavra do dia
e grava tudo em data.json, que a página lê. Roda no GitHub Actions às 6h50.
Só usa a biblioteca padrão do Python (nada para instalar)."""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SP = timezone(timedelta(hours=-3))  # Brasil sem horário de verão desde 2019
UA = {"User-Agent": "bom-dia/1.0 (github.com/PhelipeFraga/bom-dia)"}

GN = "https://news.google.com/rss/{}hl=pt-BR&gl=BR&ceid=BR:pt-419"
TEMAS = {
    "Brasil": GN.format("headlines/section/topic/NATION?"),
    "Mundo": GN.format("headlines/section/topic/WORLD?"),
    "Ciência": GN.format("headlines/section/topic/SCIENCE?"),
    "Tecnologia": GN.format("headlines/section/topic/TECHNOLOGY?"),
    "Games": GN.format("search?q=playstation+OR+videogame+OR+games+when:2d&"),
}
POR_TEMA = 6


def baixar(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def noticias():
    saida = {}
    for tema, url in TEMAS.items():
        try:
            itens = ET.fromstring(baixar(url)).iter("item")
        except Exception as e:
            print(f"[aviso] notícias {tema}: {e}")
            continue
        lista = []
        for it in itens:
            titulo = it.findtext("title", "")
            fonte = it.findtext("source", "")
            if fonte and titulo.endswith(" - " + fonte):
                titulo = titulo[: -len(fonte) - 3]
            try:
                quando = parsedate_to_datetime(it.findtext("pubDate")).astimezone(SP).isoformat()
            except Exception:
                quando = None
            lista.append({"titulo": titulo, "fonte": fonte, "quando": quando, "link": it.findtext("link")})
            if len(lista) == POR_TEMA:
                break
        saida[tema] = lista
    return saida


def nasa():
    try:
        item = ET.fromstring(baixar("https://www.nasa.gov/feeds/iotd-feed/")).find("channel/item")
        img = item.find("enclosure").get("url")
        return {
            "titulo": item.findtext("title"),
            "texto": item.findtext("description"),
            "imagem": img + "?w=900",
            "link": item.findtext("link"),
        }
    except Exception as e:
        print(f"[aviso] NASA: {e}")
        return None


def neste_dia(hoje):
    try:
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/pt/onthisday/selected/{hoje:%m}/{hoje:%d}"
        eventos = json.loads(baixar(url)).get("selected", [])
    except Exception as e:
        print(f"[aviso] neste dia: {e}")
        return []
    saida = []
    for ev in eventos[:3]:
        pag = (ev.get("pages") or [{}])[0]
        link = pag.get("content_urls", {}).get("mobile", {}).get("page")
        saida.append({"ano": ev.get("year"), "texto": ev.get("text"), "link": link})
    return saida


def palavra(hoje):
    palavras = json.loads((RAIZ / "scripts" / "palavras.json").read_text(encoding="utf-8"))
    return palavras[hoje.timetuple().tm_yday % len(palavras)]


def main():
    agora = datetime.now(SP)
    dados = {
        "gerado_em": agora.isoformat(timespec="minutes"),
        "noticias": noticias(),
        "nasa": nasa(),
        "neste_dia": neste_dia(agora),
        "palavra": palavra(agora),
    }
    (RAIZ / "data.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in dados["noticias"].values())
    print(f"ok: {total} notícias, NASA={'sim' if dados['nasa'] else 'não'}, neste dia={len(dados['neste_dia'])}")


if __name__ == "__main__":
    main()

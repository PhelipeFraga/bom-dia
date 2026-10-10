"""Robô do Bom dia: coleta notícias, foto da NASA, "neste dia" e palavra do dia
e grava tudo em data.json, que a página lê. Roda no GitHub Actions às 6h50.
Só usa a biblioteca padrão do Python (nada para instalar)."""

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SP = timezone(timedelta(hours=-3))  # Brasil sem horário de verão desde 2019
UA = {"User-Agent": "bom-dia/1.0 (github.com/PhelipeFraga/bom-dia)"}

GN = "https://news.google.com/rss/{}hl=pt-BR&gl=BR&ceid=BR:pt-419"
# Cada tema pode juntar mais de um feed; os itens são intercalados entre eles
TEMAS = {
    "Brasil": [GN.format("headlines/section/topic/NATION?")],
    "Mundo": [GN.format("headlines/section/topic/WORLD?")],
    "Ciência": [GN.format("headlines/section/topic/SCIENCE?")],
    # O tema Tecnologia do Google Notícias em português mistura celebridade e polícia
    "Tecnologia": ["https://canaltech.com.br/rss/", "https://tecnoblog.net/feed/"],
    "Games": [GN.format("search?q=PS5+OR+PlayStation+OR+Xbox+OR+Nintendo+OR+%22jogo+de+videogame%22+when:2d&")],
}
POR_TEMA = 6
MAX_HORAS = 36        # notícia mais velha que isso não entra
MAX_POR_FONTE = 2     # para não virar "só G1"

# O crivo: o que nunca entra, em qualquer tema
BLOQUEIO_GERAL = re.compile(
    r"mega-?sena|lotof[aá]cil|quina|loteria|resultado d[oa] sorteio|hor[oó]scopo|signo|"
    r"BBB|big brother|a fazenda|novela|fofoca|ex-bbb|influenciador|"
    r"onde assistir|como assistir|ao vivo:|palpite|bets?|casa de apostas|apostas esportivas|cupom|"
    r"black friday|menor pre[cç]o|\d+% ?off|em oferta|sem juros|pre[cç]o baix|"
    r"^como |^veja como|vale a pena comprar|melhores (celulares|tvs|notebooks|fones)|"
    r"veja (as|os|fotos|v[ií]deo)|v[ií]deo:|fotos:|quiz|teste:", re.I)
# Ruído específico de cada tema
BLOQUEIO_TEMA = {
    "Games": re.compile(r"futebol|brasileir[aã]o|libertadores|gol|jogada|rodada|copa do|"
                        r"cassino|tigrinho|loteria|bets?", re.I),
}
# Agregadores, fofoca, propaganda de marca e de partido
FONTES_RUINS = re.compile(r"^(Terra|MSN|Yahoo|Metrópoles Entretenimento|Notícias da TV|Gshow|"
                          r"Nintendo|XBOX Wire|Xbox Wire|PlayStation\.Blog.*|Partido .*|PT|PL)$", re.I)
SUFIXOS = re.compile(r"\s*[;|–-]\s*(V[IÍ]DEO|VÍDEOS|FOTOS|AO VIVO)\s*$", re.I)


def baixar(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def palavras_chave(titulo):
    return {p for p in re.findall(r"\w{4,}", titulo.lower())}


def parecida(chaves, vistas):
    """Mesma notícia por outro veículo: mais da metade das palavras em comum."""
    return any(len(chaves & v) / max(1, min(len(chaves), len(v))) > 0.5 for v in vistas)


def ler_feed(url):
    canal = ET.fromstring(baixar(url)).find("channel")
    padrao = (canal.findtext("title") or "").split(" - ")[0].split(" | ")[0].strip()
    for it in canal.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        fonte = it.findtext("source") or padrao
        if titulo.endswith(" - " + fonte):
            titulo = titulo[: -len(fonte) - 3]
        try:
            quando = parsedate_to_datetime(it.findtext("pubDate")).astimezone(SP)
        except Exception:
            quando = None
        yield {"titulo": SUFIXOS.sub("", titulo), "fonte": fonte, "quando": quando, "link": it.findtext("link")}


def intercalar(listas):
    for grupo in zip(*listas):
        yield from grupo
    maior = max(listas, key=len, default=[])
    yield from maior[min(map(len, listas)):]


def noticias():
    saida, vistas = {}, []   # vistas vale entre temas: a mesma notícia não aparece duas vezes
    limite = datetime.now(SP) - timedelta(hours=MAX_HORAS)
    for tema, urls in TEMAS.items():
        listas = []
        for url in urls:
            try:
                listas.append(list(ler_feed(url)))
            except Exception as e:
                print(f"[aviso] notícias {tema} ({url}): {e}")
        lista, por_fonte, cortadas = [], {}, 0
        teto_fonte = MAX_POR_FONTE if len(urls) == 1 else POR_TEMA // len(urls)
        for n in intercalar(listas) if listas else []:
            chaves = palavras_chave(n["titulo"])
            if (
                (n["quando"] and n["quando"] < limite)
                or BLOQUEIO_GERAL.search(n["titulo"])
                or (tema in BLOQUEIO_TEMA and BLOQUEIO_TEMA[tema].search(n["titulo"]))
                or FONTES_RUINS.match(n["fonte"])
                or por_fonte.get(n["fonte"], 0) >= teto_fonte
                or len(chaves) < 3
                or parecida(chaves, vistas)
            ):
                cortadas += 1
                continue
            vistas.append(chaves)
            por_fonte[n["fonte"]] = por_fonte.get(n["fonte"], 0) + 1
            n["quando"] = n["quando"].isoformat() if n["quando"] else None
            lista.append(n)
            if len(lista) == POR_TEMA:
                break
        print(f"{tema}: {len(lista)} entraram, {cortadas} cortadas pelo crivo")
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

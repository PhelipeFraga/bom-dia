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
# Temas escolhidos pelo Phelipe em 2026-10-09. Cada tema pode juntar mais de um feed;
# os itens são intercalados entre eles. A ordem aqui é a ordem das abas na página.
TEMAS = {
    "Brasil": [GN.format("headlines/section/topic/NATION?")],
    "Mundo": [GN.format("headlines/section/topic/WORLD?")],
    "Economia": [GN.format("headlines/section/topic/BUSINESS?")],
    "São Paulo": [GN.format("search?q=%22S%C3%A3o+Paulo%22+(prefeitura+OR+metr%C3%B4+OR+CPTM+OR+Sabesp+OR+Enel+OR+tr%C3%A2nsito+OR+%22na+capital%22)+when:1d&")],
    # O tema Tecnologia do Google Notícias em português mistura celebridade e polícia
    "IA e tech": [
        "https://canaltech.com.br/rss/",
        "https://tecnoblog.net/feed/",
        GN.format("search?q=%22intelig%C3%AAncia+artificial%22+OR+OpenAI+OR+Anthropic+OR+Gemini+when:1d&"),
    ],
    "Ciência": [GN.format("headlines/section/topic/SCIENCE?")],
    "Games": [GN.format("search?q=PS5+OR+PlayStation+OR+Xbox+OR+Nintendo+OR+%22jogo+de+videogame%22+when:2d&")],
    "Cultura": [
        GN.format("search?q=(Netflix+OR+%22Prime+Video%22+OR+HBO+OR+%22Disney%2B%22+OR+cinema)"
                  "+(estreia+OR+trailer+OR+temporada+OR+cr%C3%ADtica)+when:2d&"),
        GN.format("search?q=livro+(%22Companhia+das+Letras%22+OR+Intr%C3%ADnseca+OR+%22mais+vendidos%22+OR+Jabuti+OR+Flip)+when:3d&"),
    ],
}
POR_TEMA = 5
MAX_HORAS = 36        # notícia mais velha que isso não entra
MAX_POR_FONTE = 2     # para não virar "só G1"

# O crivo: o que nunca entra, em qualquer tema
LIXO = (
    r"mega-?sena|lotof[aá]cil|\bquina\b|loteria|resultado d[oa] sorteio|hor[oó]scopo|\bsignos?\b|"
    r"onde assistir|como assistir|ao vivo|palpite|\bbets?\b|casa de apostas|apostas esportivas|cupom|"
    r"black friday|menor pre[cç]o|\d+% ?off|em oferta|sem juros|pre[cç]o baix|"
    r"^como |^veja como|vale a pena comprar|melhores (celulares|tvs|notebooks|fones)|"
    r"veja (as|os|fotos|v[ií]deo)|v[ií]deo:|fotos:|\bquiz\b|teste:|reflex[aã]o d[ao]|a frase"
)
# Escolhas do Phelipe: nada de crimes e tragédias, celebridades ou esportes de manhã
CRIMES = (
    r"assassin|homic[ií]dio|feminic|latroc|\bpres[oa]s?\b|pris[aã]o|pol[ií]cia|\bPM\b|tiroteio|\bbalead|"
    r"atira|esfaque|estupr|sequestr|\broub|furto|assalt|\bcrime|criminos|tr[aá]fico|fac[cç][aã]o|"
    r"execu[cç][aã]o de condenad|fuzilamento"
)
TRAGEDIAS = (
    r"\bmort[eoa]s?\b|\bmorre|cad[aá]ver|corpo (é|e) encontrado|desaparecid|acidente|avi[aã]o cai|"
    r"em chamas|inc[eê]ndio|explos|desab|naufr[aá]g|enchente|deslizamento|trag[eé]dia|v[ií]timas?|ferid[oa]s"
)
CELEBRIDADES = (
    r"\bBBB\b|big brother|a fazenda|novela|fofoca|ex-bbb|influenciador|famos[oa]s?\b|"
    r"pl[aá]stica|namorad|affair|separa[cç][aã]o|div[oó]rcio|web reage|internautas|viraliza|"
    r"look|mans[aã]o|p[oõ]e (à|a) venda|herdeir"
)
ESPORTES = (
    r"futebol|brasileir[aã]o|libertadores|sul-americana|\bcopa do\b|\bgols?\b|jogada|rodada|"
    r"campeonato|sele[cç][aã]o brasileira|\bt[eé]cnico do\b|f[oó]rmula 1|\bF1\b|\bNBA\b|\bUFC\b|"
    r"\bt[eê]nis\b|v[oô]lei|corinthians|palmeiras|flamengo|fluminense|botafogo|vasco|gr[eê]mio|"
    r"cruzeiro|atl[eé]tico-mg|\bSPFC\b|tricolor|ol[ií]mpi"
)
BLOQUEIO_GERAL = re.compile("|".join([LIXO, CELEBRIDADES, ESPORTES]), re.I)
BLOQUEIO_CRIMES = re.compile(CRIMES, re.I)
# Em Mundo, guerra e conflito fazem parte da geopolítica; o filtro de tragédias não se aplica lá
BLOQUEIO_TRAGEDIAS = re.compile(TRAGEDIAS, re.I)
SEM_FILTRO_TRAGEDIAS = {"Mundo"}
# Ruído específico de cada tema
BLOQUEIO_TEMA = {
    "Games": re.compile(r"cassino|tigrinho", re.I),
}
# Agregadores, fofoca, propaganda de marca, de partido e comunicados de órgãos públicos
FONTES_RUINS = re.compile(
    r"^(Terra|MSN|Yahoo.*|Metrópoles Entretenimento|Notícias da TV|Gshow|Quem|Contigo.*|"
    r"Nintendo|XBOX Wire|Xbox Wire|PlayStation\.Blog.*|Netflix|Partido .*|PT|PL|"
    r"Prefeitura.*|Governo.*|Secretaria.*|Associa[cç][aã]o.*|Ajufe|Sindicato.*|.*\.gov\.br|Tribunal.*|TJ.*|OAB.*|Universidade.*|UF[A-Z]+.*|"
    r"Comunica .*|C[aâ]mara Municipal.*|Assembleia.*|Minist[eé]rio.*)$", re.I)
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
        for n in intercalar(listas) if listas else []:
            chaves = palavras_chave(n["titulo"])
            if (
                (n["quando"] and n["quando"] < limite)
                or BLOQUEIO_GERAL.search(n["titulo"])
                or BLOQUEIO_CRIMES.search(n["titulo"])
                or (tema not in SEM_FILTRO_TRAGEDIAS and BLOQUEIO_TRAGEDIAS.search(n["titulo"]))
                or (tema in BLOQUEIO_TEMA and BLOQUEIO_TEMA[tema].search(n["titulo"]))
                or FONTES_RUINS.match(n["fonte"])
                or por_fonte.get(n["fonte"], 0) >= MAX_POR_FONTE
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

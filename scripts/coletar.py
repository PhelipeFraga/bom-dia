"""Robô do Bom dia: coleta notícias, foto da NASA, "neste dia" e palavra do dia
e grava tudo em data.json, que a página lê. Roda no GitHub Actions às 6h50.
Só usa a biblioteca padrão do Python (nada para instalar)."""

import gzip
import html as html_mod
import json
import time
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SP = timezone(timedelta(hours=-3))  # Brasil sem horário de verão desde 2019
# Identificação de navegador comum: o Google Notícias às vezes recusa pedidos de robôs
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

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
# Reserva: feeds diretos dos jornais, usados quando o Google Notícias falha ou traz pouco
G1 = "https://g1.globo.com/rss/g1/{}/"
RESERVA = {
    "Brasil": [G1.format("politica")],
    "Mundo": [G1.format("mundo"), "https://feeds.bbci.co.uk/portuguese/rss.xml"],
    "Economia": [G1.format("economia")],
    "São Paulo": [G1.format("sp/sao-paulo")],
    "IA e tech": [G1.format("tecnologia")],
    "Ciência": [G1.format("ciencia"), "https://canaltech.com.br/rss/espaco/"],
    "Cultura": [G1.format("pop-arte")],
}
NOMES_FONTE = {"g1.globo.com": "G1", "bbci.co.uk": "BBC News Brasil"}
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


def baixar(url, timeout=25, tentativas=3):
    """Baixa com até 3 tentativas (espera 5 s e 15 s entre elas)."""
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                corpo = r.read()
                # alguns sites (G1) mandam o conteúdo compactado mesmo sem pedirmos
                return gzip.decompress(corpo) if corpo[:2] == bytes((0x1F, 0x8B)) else corpo
        except Exception:
            if n == tentativas - 1:
                raise
            time.sleep(5 if n == 0 else 15)


def palavras_chave(titulo):
    return {p for p in re.findall(r"\w{4,}", titulo.lower())}


def parecida(chaves, vistas):
    """Mesma notícia por outro veículo (mais da metade das palavras em comum): devolve a já vista."""
    for v, item in vistas:
        if len(chaves & v) / max(1, min(len(chaves), len(v))) > 0.5:
            return item
    return None


MEDIA = "{http://search.yahoo.com/mrss/}"
CONTEUDO = "{http://purl.org/rss/1.0/modules/content/}encoded"
IMG_HTML = re.compile(r"""<img[^>]+src=["']([^"']+)""", re.I)


def foto_do_feed(it):
    """Foto que o próprio feed traz (G1, BBC, Canaltech, Tecnoblog); o Google Notícias não traz."""
    for tag in (MEDIA + "content", MEDIA + "thumbnail"):
        el = it.find(tag)
        if el is not None and el.get("url"):
            return el.get("url")
    for el in it.iter(MEDIA + "content"):
        if el.get("url"):
            return el.get("url")
    enc = it.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image"):
        return enc.get("url")
    for campo in (CONTEUDO, "description"):
        m = IMG_HTML.search(it.findtext(campo) or "")
        if m:
            return m.group(1)
    return None


def ler_feed(url):
    canal = ET.fromstring(baixar(url)).find("channel")
    padrao = next((nome for dom, nome in NOMES_FONTE.items() if dom in url), None)         or (canal.findtext("title") or "").split(" - ")[0].split(" | ")[0].strip()
    for it in canal.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        fonte = it.findtext("source") or padrao
        if titulo.endswith(" - " + fonte):
            titulo = titulo[: -len(fonte) - 3]
        try:
            quando = parsedate_to_datetime(it.findtext("pubDate")).astimezone(SP)
        except Exception:
            quando = None
        yield {"titulo": SUFIXOS.sub("", titulo), "fonte": fonte, "quando": quando, "link": it.findtext("link"),
               "foto": foto_do_feed(it)}


def intercalar(listas):
    for grupo in zip(*listas):
        yield from grupo
    maior = max(listas, key=len, default=[])
    yield from maior[min(map(len, listas)):]


def baixar_feeds(tema, urls):
    listas = []
    for url in urls:
        try:
            listas.append(list(ler_feed(url)))
        except Exception as e:
            print(f"[aviso] notícias {tema} ({url}): {e}")
    return listas


def filtrar(tema, listas, vistas, limite, lista, teto_fonte=MAX_POR_FONTE):
    """Passa o crivo e acrescenta à lista do tema até POR_TEMA; devolve quantas foram cortadas."""
    por_fonte, cortadas = {}, 0
    for n in lista:
        por_fonte[n["fonte"]] = por_fonte.get(n["fonte"], 0) + 1
    for n in intercalar(listas) if listas else []:
        chaves = palavras_chave(n["titulo"])
        if (
            (n["quando"] and n["quando"] < limite)
            or BLOQUEIO_GERAL.search(n["titulo"])
            or BLOQUEIO_CRIMES.search(n["titulo"])
            or (tema not in SEM_FILTRO_TRAGEDIAS and BLOQUEIO_TRAGEDIAS.search(n["titulo"]))
            or (tema in BLOQUEIO_TEMA and BLOQUEIO_TEMA[tema].search(n["titulo"]))
            or FONTES_RUINS.match(n["fonte"])
            or len(chaves) < 3
        ):
            cortadas += 1
            continue
        igual = parecida(chaves, vistas)
        if igual:
            # Outro veículo dando a mesma notícia: não repete, mas conta como cobertura
            if n["fonte"] not in igual["veiculos"]:
                igual["veiculos"].append(n["fonte"])
            continue
        if len(lista) == POR_TEMA or por_fonte.get(n["fonte"], 0) >= teto_fonte:
            vistas.append((chaves, {"veiculos": [n["fonte"]]}))  # só para contar cobertura
            continue
        n["veiculos"] = [n["fonte"]]
        vistas.append((chaves, n))
        por_fonte[n["fonte"]] = por_fonte.get(n["fonte"], 0) + 1
        n["quando"] = n["quando"].isoformat() if n["quando"] else None
        n["tema"] = tema
        lista.append(n)
    return cortadas


def noticias():
    saida, vistas = {}, []   # vistas vale entre temas: a mesma notícia não aparece duas vezes
    limite = datetime.now(SP) - timedelta(hours=MAX_HORAS)
    for tema, urls in TEMAS.items():
        lista = []
        cortadas = filtrar(tema, baixar_feeds(tema, urls), vistas, limite, lista)
        if len(lista) < 3 and tema in RESERVA:
            # Google falhou ou trouxe pouco: completa com os feeds diretos dos jornais
            antes = len(lista)
            # na reserva a fonte é uma só (G1), então vale até POR_TEMA do mesmo veículo e notícias de até 72 h
            filtrar(tema, baixar_feeds(tema, RESERVA[tema]), vistas, limite - timedelta(hours=36), lista, POR_TEMA)
            print(f"[aviso] {tema}: Google trouxe {antes}; completado com a reserva ({len(lista)})")
        print(f"{tema}: {len(lista)} entraram, {cortadas} cortadas pelo crivo")
        saida[tema] = lista
    for lista in saida.values():
        for n in lista:
            n["cobertura"] = len(n.pop("veiculos"))
    return saida


ORDEM_DESTAQUES = ["Brasil", "Mundo", "Economia", "IA e tech", "Ciência", "São Paulo", "Games", "Cultura"]


OG_IMAGE = [re.compile(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""", re.I),
            re.compile(r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image""", re.I),
            re.compile(r"""<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)""", re.I)]


def link_original(link):
    """O link do Google Notícias é um desvio; o próprio Google informa a matéria original nesta consulta."""
    aid = link.split("/articles/")[1].split("?")[0]
    html = baixar(f"https://news.google.com/rss/articles/{aid}", tentativas=1).decode("utf-8", "ignore")
    sg = re.search(r'data-n-a-sg="([^"]+)"', html).group(1)
    ts = re.search(r'data-n-a-ts="([^"]+)"', html).group(1)
    pedido = [[["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                          f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts},"{sg}"]', None, "generic"]]]
    corpo = urllib.parse.urlencode({"f.req": json.dumps(pedido)}).encode()
    req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=corpo,
                                 headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = r.read().decode("utf-8", "ignore")
    return json.loads(json.loads(resp.split("\n\n")[1])[0][2])[1]


def foto_da_pagina(url):
    html = baixar(url, timeout=15, tentativas=1)[:400_000].decode("utf-8", "ignore")
    for padrao in OG_IMAGE:
        m = padrao.search(html)
        if m:
            return urllib.parse.urljoin(url, m.group(1).replace("&amp;", "&"))
    return None


def completar_fotos(por_tema, guardadas):
    """Dá foto a cada notícia. Usa a do feed; senão, a já descoberta em passagens anteriores; senão, busca na matéria.
    Devolve o dicionário atualizado de fotos guardadas (link do Google → {url, foto})."""
    novas = {}
    pendentes = [n for lista in por_tema.values() for n in lista if not n.get("foto")]

    def resolver(n):
        g = n["link"]
        if g in guardadas:
            return g, guardadas[g]
        try:
            url = link_original(g) if "news.google.com" in g else g
            return g, {"url": url, "foto": foto_da_pagina(url)}
        except Exception as e:
            return g, {"url": None, "foto": None, "erro": str(e)[:80]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        for g, info in ex.map(resolver, pendentes):
            novas[g] = info
    achadas = 0
    for lista in por_tema.values():
        for n in lista:
            info = novas.get(n["link"])
            if info:
                if info.get("url"):
                    n["link"] = info["url"]     # abre direto no site do jornal
                if info.get("foto"):
                    n["foto"] = info["foto"]
            achadas += bool(n.get("foto"))
    total = sum(len(l) for l in por_tema.values())
    print(f"fotos: {achadas} de {total} notícias ({len([g for g in novas if g not in guardadas])} buscadas agora)")
    # guarda só o que deu certo, e no máximo as 400 mais recentes
    guardadas = {**guardadas, **{g: i for g, i in novas.items() if i.get("foto")}}
    return dict(list(guardadas.items())[-400:])


def destaques(noticias_por_tema, quantos=5):
    """O mais importante do dia: a principal de cada tema (o Google já ordena por relevância),
    na ordem de ORDEM_DESTAQUES."""
    return [noticias_por_tema[t][0] for t in ORDEM_DESTAQUES if noticias_por_tema.get(t)][:quantos]


AVISO_SP = re.compile(r"metr[oô]|\blinha \d|CPTM|greve|alagament|falta de (energia|luz|[aá]gua)|"
                      r"\bEnel\b|interdi[cç]|congestionament|rod[ií]zio", re.I)


def avisos_sp(noticias_por_tema):
    return [n for n in noticias_por_tema.get("São Paulo", []) if AVISO_SP.search(n["titulo"])][:2]


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


CLIMA_URL = ("https://api.open-meteo.com/v1/forecast?latitude=-23.55&longitude=-46.63"
             "&current=temperature_2m,apparent_temperature,weather_code,precipitation"
             "&hourly=temperature_2m,precipitation_probability,precipitation,weather_code"
             "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
             "&timezone=America%2FSao_Paulo&forecast_days=7")


AR_URL = ("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=-23.55&longitude=-46.63"
          "&current=us_aqi,pm2_5&timezone=America%2FSao_Paulo")


def json_de(url, nome):
    """Cópia de reserva do clima e do radar: a página busca ao vivo e só usa esta se falhar."""
    try:
        return json.loads(baixar(url))
    except Exception as e:
        print(f"[aviso] {nome}: {e}")
        return None


# ---------------- Metrô e trens ----------------
METRO_URL = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
CPTM_URL = "https://api.cptm.sp.gov.br/AppCPTM/v1/Linhas/ObterStatus"
CPTM = {10: ("Turquesa", "#008b8b"), 11: ("Coral", "#f04e23"), 12: ("Safira", "#083e89"), 13: ("Jade", "#00b352")}
PROBLEMA = re.compile(r"falha|interromp|paralis|velocidade reduzida|lentid|atraso|pane|sem circula|suspens|"
                      r"inoperan|problema|normaliza", re.I)


def linhas_metro():
    """Situação oficial das linhas do Metrô (1, 2, 3, 4, 5, 15 e 17), da página "Direto do Metrô"."""
    pagina = baixar(METRO_URL).decode("utf-8", "ignore")
    saida = []
    for bloco in re.findall(r'<li class="linha list-group-item">(.*?)</li>', pagina, re.S):
        num = re.search(r'class="linha-numero"[^>]*?background-color:\s*(#[0-9a-fA-F]{6})[^>]*>(\d+)<', bloco)
        nome = re.search(r'class="linha-nome">([^<]+)<', bloco)
        sit = re.search(r'class="linha-situacao"[^>]*>([^<]+)<', bloco)
        quando = re.search(r"atualizado em ([0-9/]+ [0-9:]+)", bloco)
        desc = re.search(r"class='description'>(.*?)</div>", html_mod.unescape(bloco), re.S)
        if num and nome and sit:
            saida.append({"numero": int(num.group(2)), "nome": nome.group(1).strip(), "cor": num.group(1),
                          "situacao": sit.group(1).strip(), "detalhe": re.sub(r"<[^>]+>", " ", desc.group(1)).strip() if desc else "",
                          "quando": quando.group(1) if quando else None, "fonte": "Metrô"})
    return saida


def linhas_cptm():
    saida = []
    for l in json.loads(baixar(CPTM_URL)):
        nome, cor = CPTM.get(l["linhaId"], (str(l["linhaId"]), "#888888"))
        saida.append({"numero": l["linhaId"], "nome": nome, "cor": cor, "situacao": l.get("status") or "",
                      "detalhe": l.get("descricao") or "", "quando": l.get("dataGeracao"), "fonte": "CPTM"})
    return saida


def linha9_pelas_noticias():
    """A ViaMobilidade não publica a situação num formato aberto: procura notícias de problema na
    Linha 9-Esmeralda nas últimas 3 horas."""
    url = GN.format("search?q=%22Linha+9%22+Esmeralda+when:1d&")
    limite = datetime.now(SP) - timedelta(hours=3)
    alerta = None
    for n in ler_feed(url):
        if n["quando"] and n["quando"] >= limite and PROBLEMA.search(n["titulo"]):
            alerta = n
            break
    return {"numero": 9, "nome": "Esmeralda", "cor": "#01a9a7", "fonte": "notícias",
            "situacao": "Possível problema" if alerta and not re.search(r"normaliza|opera normalmente", alerta["titulo"], re.I)
                        else "Sem alertas nas notícias",
            "detalhe": alerta["titulo"] if alerta else "", "link": alerta["link"] if alerta else None,
            "quando": alerta["quando"].isoformat() if alerta else None}


def linhas():
    lista = []
    for nome, func in (("Metrô", linhas_metro), ("CPTM", linhas_cptm), ("Linha 9", linha9_pelas_noticias)):
        try:
            r = func()
            lista.extend(r if isinstance(r, list) else [r])
        except Exception as e:
            print(f"[aviso] linhas {nome}: {e}")
    lista.sort(key=lambda l: l["numero"])
    print("linhas: " + ", ".join(f'{l["numero"]}={l["situacao"]}' for l in lista))
    return lista


def palavra(hoje):
    palavras = json.loads((RAIZ / "scripts" / "palavras.json").read_text(encoding="utf-8"))
    return palavras[hoje.timetuple().tm_yday % len(palavras)]


def main():
    agora = datetime.now(SP)
    por_tema = noticias()
    antes = {}
    try:
        antes = json.loads((RAIZ / "data.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    fotos = completar_fotos(por_tema, antes.get("fotos_guardadas", {}))
    # Tema que veio vazio (fonte fora do ar) mantém as notícias da passagem anterior, se tiverem até 24 h
    try:
        idade = agora - datetime.fromisoformat(antes["gerado_em"])
        if idade < timedelta(hours=24):
            for tema, lista in antes.get("noticias", {}).items():
                if not por_tema.get(tema) and lista:
                    por_tema[tema] = lista
                    print(f"[aviso] {tema}: fonte vazia, mantidas as notícias anteriores")
    except Exception as e:
        print(f"[aviso] sem dados anteriores para reaproveitar: {e}")
    dados = {
        "gerado_em": agora.isoformat(timespec="minutes"),
        "destaques": destaques(por_tema),
        "avisos_sp": avisos_sp(por_tema),
        "noticias": por_tema,
        "nasa": nasa(),
        "neste_dia": neste_dia(agora),
        "palavra": palavra(agora),
        "clima": json_de(CLIMA_URL, "clima"),
        "radar": json_de("https://api.rainviewer.com/public/weather-maps.json", "radar"),
        "ar": json_de(AR_URL, "qualidade do ar"),
        "fotos_guardadas": fotos,
        "linhas": linhas(),
    }
    (RAIZ / "data.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in dados["noticias"].values())
    print(f"ok: {total} notícias, NASA={'sim' if dados['nasa'] else 'não'}, neste dia={len(dados['neste_dia'])}")


if __name__ == "__main__":
    main()

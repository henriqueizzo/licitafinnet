"""Edital e anexos da licitação, puxados da fonte de origem ao abrir o card.

O time abria o link do portal e caçava o edital à mão. Aqui o CRM lista os
arquivos publicados (PNCP: edital, termo de referência, anexos) e faz o download
pelo próprio backend (proxy), porque o PNCP não libera CORS para o navegador e
devolve URLs com porta interna inválida.

Para as demais fontes só há o `edital_url` (cadastro manual pode apontar direto
para o PDF): se ele responder um arquivo, vira um único item "Edital".
"""
import logging
import re
import time
from urllib.parse import unquote

import httpx

from ..models import Licitacao

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_PNCP_ARQUIVOS = re.compile(r"^https://pncp\.gov\.br/pncp-api/v1/orgaos/\d+/compras/\d+/\d+/arquivos/?$")
MAX_BYTES = 60 * 1024 * 1024  # teto de um arquivo proxiado


def _sem_porta(url: str) -> str:
    """Bug do PNCP: URL com porta interna (pncp.gov.br:24932) que não aceita conexão externa."""
    return re.sub(r"^(https://[^/:]+):\d+", r"\1", url or "")


def _nome_do_content_disposition(cabecalho: str | None) -> str:
    if not cabecalho:
        return ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", cabecalho)
    if m:
        return unquote(m.group(1)).strip()
    m = re.search(r'filename="?([^";]+)"?', cabecalho)
    return m.group(1).strip() if m else ""


def _extensao(nome: str, content_type: str | None, inicio: bytes) -> str:
    if "." in nome:
        return "." + nome.rsplit(".", 1)[1].lower()[:6]
    if inicio.startswith(b"%PDF"):
        return ".pdf"
    if inicio[:2] == b"PK":
        return ".zip"
    if content_type and "pdf" in content_type:
        return ".pdf"
    return ""


def _nome_seguro(texto: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', " ", texto).strip()[:120]


def listar_arquivos(lic: Licitacao) -> list[dict]:
    """Arquivos publicados da licitação: [{seq, titulo, tipo, publicado_em}].

    PNCP: consulta a API de arquivos (edital primeiro). Outras fontes: um item
    único quando `edital_url` aponta para um arquivo. Lista vazia = nada
    disponível na origem (o card mantém o link do portal).
    """
    url = (lic.edital_url or "").strip()
    if not url:
        return []
    if _PNCP_ARQUIVOS.match(url):
        return _listar_pncp(url)
    return _listar_link_direto(url)


def _listar_pncp(url: str) -> list[dict]:
    # O PNCP oscila (timeouts esporádicos): uma segunda tentativa resolve a maioria
    for tentativa in (1, 2):
        try:
            with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": _UA}) as client:
                resp = client.get(url)
                resp.raise_for_status()
                arquivos = resp.json() or []
            break
        except Exception as exc:
            logger.warning("Falha ao listar arquivos do PNCP %s (tentativa %d): %s", url, tentativa, exc)
            if tentativa == 2:
                raise
            time.sleep(2)
    itens = []
    for a in arquivos:
        if a.get("statusAtivo") is False:
            continue
        seq = a.get("sequencialDocumento")
        if seq is None:
            continue
        tipo = (a.get("tipoDocumentoNome") or "").strip()
        titulo = (a.get("titulo") or "").strip() or tipo or f"Arquivo {seq}"
        itens.append({
            "seq": int(seq),
            "titulo": titulo,
            "tipo": tipo,
            "publicado_em": (a.get("dataPublicacaoPncp") or "")[:10],
        })
    # Edital primeiro (pelo título, porque o publicador marca anexos como tipo
    # "Edital"), depois os demais do tipo Edital, o termo de referência e o resto
    def peso(item):
        titulo, tipo = item["titulo"].lower(), item["tipo"].lower()
        if "edital" in titulo:
            return 0
        if "edital" in tipo:
            return 1
        if "refer" in f"{tipo} {titulo}":
            return 2
        return 3
    itens.sort(key=lambda i: (peso(i), i["seq"]))
    return itens


def _listar_link_direto(url: str) -> list[dict]:
    """Fonte sem API de arquivos: só vale se o link entregar um arquivo (não uma página)."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": _UA}) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return []
                ctype = (resp.headers.get("content-type") or "").lower()
                inicio = b""
                for pedaco in resp.iter_bytes(1024):
                    inicio = pedaco
                    break
    except Exception as exc:
        logger.info("Link do edital %s não respondeu: %s", url, exc)
        return []
    if inicio.startswith(b"%PDF") or "pdf" in ctype or "octet-stream" in ctype or inicio[:2] == b"PK":
        return [{"seq": 1, "titulo": "Edital", "tipo": "Edital", "publicado_em": ""}]
    return []


def baixar_arquivo(lic: Licitacao, seq: int) -> tuple[bytes, str, str]:
    """Baixa um arquivo da origem. Retorna (conteudo, nome_para_download, content_type).

    Levanta ValueError se o arquivo não existir na origem e httpx.HTTPError se a
    origem falhar (a rota traduz em 404/502).
    """
    url = _sem_porta((lic.edital_url or "").strip())
    if not url:
        raise ValueError("Licitação sem link de edital")
    titulo = "Edital"
    if _PNCP_ARQUIVOS.match(url):
        itens = {i["seq"]: i for i in _listar_pncp(url)}
        if seq not in itens:
            raise ValueError("Arquivo não encontrado na origem")
        titulo = itens[seq]["titulo"]
        url = f"{url.rstrip('/')}/{seq}"
    elif seq != 1:
        raise ValueError("Arquivo não encontrado na origem")

    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            partes, total = [], 0
            for pedaco in resp.iter_bytes(256 * 1024):
                total += len(pedaco)
                if total > MAX_BYTES:
                    raise ValueError("Arquivo maior que o limite de 60 MB")
                partes.append(pedaco)
            conteudo = b"".join(partes)
            nome_origem = _nome_do_content_disposition(resp.headers.get("content-disposition"))
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip()

    ext = _extensao(nome_origem, ctype, conteudo[:8])
    if ext == ".pdf" or conteudo.startswith(b"%PDF"):
        ctype = "application/pdf"
    elif not ctype or ctype == "application/octet-stream":
        ctype = "application/octet-stream"
    base = _nome_seguro(" - ".join(filter(None, [lic.orgao, lic.id_externo, titulo])))
    return conteudo, f"{base}{ext}", ctype

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class LicitacaoColetada:
    """Formato normalizado de uma licitação, independente da fonte."""

    fonte: str
    id_externo: str
    orgao: str = ""
    municipio: str = ""
    uf: str = ""
    modalidade: str = ""
    objeto: str = ""
    valor_estimado: float | None = None
    data_abertura: str = ""      # ISO 8601
    data_encerramento: str = ""  # ISO 8601
    link: str = ""
    edital_url: str = ""
    sistema: str = ""             # plataforma onde a disputa corre (BLL, PCP…)
    endereco_licitacao: str = ""  # link da licitação nessa plataforma
    raw: dict = field(default_factory=dict)


class BaseCollector:
    """Interface dos coletores. Cada fonte implementa `coletar`."""

    fonte = "base"

    def coletar(self, ufs: list[str], palavras_chave: list[str], dias: int = 3) -> list[LicitacaoColetada]:
        raise NotImplementedError

    @staticmethod
    def bate_palavra_chave(texto: str, palavras_chave: list[str]) -> bool:
        """Casa palavra/frase INTEIRA, ignorando acentos e maiúsculas.

        Comparação por substring pura gerava falsos positivos graves: "EDI"
        batia dentro de "mEDIcamentos", "expEDIente", "crEDIenciamento" etc.
        Agora cada palavra-chave só casa cercada por caracteres não alfanuméricos.
        """
        t = _sem_acentos(texto)
        for p in palavras_chave:
            pn = _sem_acentos(p).strip()
            if not pn:
                continue
            padrao = r"\s+".join(re.escape(parte) for parte in pn.split())
            if re.search(rf"(?<![a-z0-9]){padrao}(?![a-z0-9])", t):
                return True
        return False


def _sem_acentos(texto: str) -> str:
    """Minúsculas sem acentos: 'Eletrônica' -> 'eletronica'."""
    nfd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

"""Varredura ampla, estado a estado, com gravação incremental e retomada.

Cada UF é coletada e GRAVADA antes de passar para a próxima: uma interrupção
no meio (queda, reinício, processo morto) preserva tudo o que já entrou e a
próxima execução retoma de onde parou, lendo o arquivo de progresso.

Uso (a partir de backend/, com DATABASE_URL apontando para o banco desejado):
    venv\\Scripts\\python.exe scripts\\varredura_ampla.py [dias] [limite_analises]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import Licitacao  # noqa: E402
from app.services.pipeline import executar_coleta, executar_analises  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]

PROGRESSO = Path(__file__).resolve().parent / "varredura_progresso.json"

dias = int(sys.argv[1]) if len(sys.argv) > 1 else 30
limite = int(sys.argv[2]) if len(sys.argv) > 2 else 40

feitas: list[str] = []
if PROGRESSO.exists():
    try:
        feitas = json.loads(PROGRESSO.read_text(encoding="utf-8")).get("ufs_concluidas", [])
    except Exception:
        feitas = []
    if feitas:
        print(f"RETOMANDO: {len(feitas)} UF(s) ja coletada(s) — {', '.join(feitas)}", flush=True)

db = SessionLocal()

print(f"### COLETA — {len(UFS) - len(feitas)} UF(s), ultimos {dias} dias", flush=True)
total_novas = 0
for i, uf in enumerate(UFS, start=1):
    if uf in feitas:
        continue
    r = None
    for tentativa in (1, 2):
        try:
            r = executar_coleta(db, dias=dias, ufs=[uf])
            break
        except Exception as exc:
            # Conexão derrubada pelo Postgres gerenciado é o caso típico: descarta
            # a sessão furada e refaz a UF com uma nova antes de desistir dela.
            print(f"UF {uf} ({i}/27): tentativa {tentativa} falhou — {exc}", flush=True)
            try:
                db.rollback()
                db.close()
            except Exception:
                pass
            db = SessionLocal()
    if r is None:  # uma UF problemática não derruba a varredura inteira
        print(f"UF {uf} ({i}/27): DESISTIU apos 2 tentativas", flush=True)
        continue
    novas = r.get("novas_licitacoes", 0)
    total_novas += novas
    print(f"UF {uf} ({i}/27): +{novas} nova(s) | acumulado {total_novas}", flush=True)
    feitas.append(uf)
    PROGRESSO.write_text(json.dumps({"ufs_concluidas": feitas}), encoding="utf-8")

print(f"RESULTADO COLETA: {json.dumps({'novas_licitacoes': total_novas}, ensure_ascii=False)}", flush=True)

pendentes = db.scalar(
    select(func.count()).select_from(Licitacao).where(Licitacao.status_analise == "pendente")
)
print(f"### ANALISES — {pendentes} pendente(s), analisando ate {limite}", flush=True)
analises = executar_analises(db, limite=limite)
print("RESULTADO ANALISES: " + json.dumps(analises, ensure_ascii=False), flush=True)

"""
limpeza.py — Pipeline de tratamento da base "Facções na Imprensa".

Etapa 1: normalização das colunas categóricas (baseada na limpeza original).
Etapa 2: preparo geográfico/temporal para o dashboard
         (data -> ano, bairro/cidade normalizados e explodidos via de-para).

Uso:
    from limpeza import carregar_base
    df, longs = carregar_base("Questionario_Faccoes_na_Imprensa.csv", "Bairros_de_Fortaleza.geojson", "geojs-23-mun.json")

`df`    -> uma linha por notícia, com colunas amigáveis e flags de crime/fenômeno.
`longs` -> dicionário de tabelas "long" (explodidas) para os mapas:
           longs['bairros'], longs['cidades'] -> uma linha por (notícia, bairro/cidade).
"""

import json
import re
import unicodedata
import pandas as pd
import numpy as np


# ----------------------------------------------------------------------------- #
# Utilidades
# ----------------------------------------------------------------------------- #
def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def _norm(s) -> str:
    """minúsculo, sem acento, sem pontuação extra, espaços colapsados."""
    if pd.isna(s):
        return ""
    t = _strip_accents(str(s)).lower().strip()
    t = re.sub(r"[^a-z0-9\s;/]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _is_sim(v) -> bool:
    return str(v).strip().lower().startswith("sim")


def _split(cell):
    if pd.isna(cell):
        return []
    return [p.strip() for p in re.split(r"[;,]", str(cell)) if p.strip()]


# ----------------------------------------------------------------------------- #
# De-para de bairros (validado e fechado pelo usuário)
# ----------------------------------------------------------------------------- #
DEPARA_BAIRROS = {
    "São João do Tauape": "Tauape", "Sapiranga-Coité": "Sapiranga / Coité",
    "Vila Ellery": "Ellery", "José Walter": "Prefeito José Walter",
    "Manoel Dias Branco": "Manuel Dias Branco",
    "Luciano Cavalcante": "Engenheiro Luciano Cavalcante",
    "Presidente Vargas": "Parque Presidente Vargas",
    "Castelão": "Boa Vista / Castelão", "Boa Vista": "Boa Vista / Castelão",
    "Jardim Castelão II": "Boa Vista / Castelão",
    "Otávio Bonfim": "Farias Brito", "Otávio Bonfim.": "Farias Brito",
    "Pio XII": "Tauape", "Lagamar": "Tauape", "LAGAMAR": "Tauape",
    "Piedade e Pio xii": "Tauape", "Praia do Futuro": "Praia do Futuro I",
    "Planalto Pici": "Pici", "Serviluz": "Cais do Porto", "Beira Mar": "Meireles",
    "Caça e Pesca": "Praia do Futuro II", "Castelo Encantado": "Vila Velha",
    "Alagadiço Novo": "José de Alencar", "Seis Bocas": "Cidade dos Funcionários",
    # descartados (não mapeiam para polígono):
    "Tancredo Neves": None, "Presidente Tancredo Neves": None,
    "São Cristovão": None, "Cidade Jardim": None, "Antonio Diogo": None,
    "Aracati": None, "Guajiru": None, "Lagoa do urubu": None,
    "Não especifica o bairro de Fortaleza": None,
    "bairros pertencentes à Área Integrada de Segurança 3": None,
}

# Facções principais (normalização da 2.1)
def _norm_faccao(p: str) -> str:
    t = _strip_accents(str(p).lower().strip())
    if "comando vermelho" in t or t == "cv":
        return "Comando Vermelho"
    if "primeiro comando da capital" in t or t == "pcc":
        return "PCC"
    if "guardioes" in t or "gde" in t:
        return "Guardiões do Estado"
    if "massa" in t or "tdn" in t:
        return "Massa (TDN)"
    if "terceiro comando puro" in t or "tcp" in t:
        return "Terceiro Comando Puro"
    if "familia do norte" in t or "fdn" in t:
        return "Família do Norte"
    if "nao e possivel identificar" in t or "nao identificado" in t or "nao identific" in t:
        return "Não identificado"
    return "Outros"


# ----------------------------------------------------------------------------- #
# Taxonomia de crimes/fenômenos (colunas Sim/Não -> rótulo do filtro/pizza)
# ----------------------------------------------------------------------------- #
# Cada item: rótulo -> nome da coluna Sim/Não na base.
CRIMES = {
    "Ações contra a vida": "2.2 Retrata uma ou mais ações de facções contra a vida de indivíduos?",
    "Tráfico de drogas": "2.4 Retrata tráfico de drogas?",
    "Apreensão de drogas": "2.5 Retrata apreensão de drogas comercializadas pela facção?",
    "Tráfico de armas": "2.6. Retrata tráfico de armas?",
    "Apreensão de armas": "2.7 Retrata apreensão de armas da facção?",
    "Lavagem de dinheiro": "2.8 Retrata crime e esquemas de lavagem de dinheiro?",
    "Apreensão de dinheiro/bens": "2.9 Retrata apreensão de dinheiro ou bens das facções?",
    "Crimes ambientais": "2.10 É feita menção a facções em crimes ambientais? ",
    "Aliança entre facções": "2.12 Retrata uma articulação ou cooperação entre facções?\n",
    "Conflito entre facções": "2.13 Retrata conflito entre facções? ",
    "Cooperação c/ agentes públicos": "2.16 Retrata cooperação entre facções e agentes públicos?",
    "Cooperação c/ políticos": "2.18 Retrata cooperação entre facções e políticos?",
    "Atuação em mercados lícitos": "2.22 Retrata a participação de facções em negócios formais e lícitos?",
    "Ataque a patrimônio": "2.23 Retrata ataque de facções contra o patrimônio público ou privado?",
    "Controle territorial": "3.1. Retrata ações de controle territorial de uma ou mais facções?",
    "Tortura": "3.12 Retrata casos de tortura contra pessoas?",
    "Tribunais do crime": "3.13 Retrata a realização de tribunais do crime?",
    "Conflito em prisões": "6.2 Retrata conflito entre facções em prisões?",
    "Rebelião em prisões": "6.4 Retrata rebeliões em prisões?",
    "Fuga de unidade prisional": "6.6 Retrata fuga de unidade prisional?",
    "Confronto com polícia": "6.8 Retrata confronto entre facções e forças de segurança pública?\n* Inclua situações de ameaça, violência e crime praticadas por faccionados contra um ou mais policiais.",
    "Operação policial": "6.9 Retrata operação policial?",
}

# As 5 pizzas "fortes" (ordem de exibição)
PIZZAS_FORTES = [
    "Ações contra a vida",
    "Operação policial",
    "Tráfico de drogas",
    "Controle territorial",
    "Conflito entre facções",
]

# Colunas de identificação (renomeadas para nomes amigáveis)
COLS = {
    "data": "1.5 Data da notícia:",
    "veiculo": "1.1 Instância de comunicação:",
    "titulo": "1.2 Título da matéria:",
    "resumo": "1.3 Subtítulo/síntese da matéria:",
    "link": "1.4 Link da matéria:",
    "faccao": "2.1 A matéria faz referência a que facção?\n* preencher OUTROS com todas as letras em caixa alta e separar mais de uma ocorrência por ponto e vírgula ( ; )",
    "bairro": "2.26.1 Qual bairro de Fortaleza?",
    "cidade_interior": "2.24.1 Qual município do interior do Estado do Ceará?",
    "cidade_rmf": "2.25.1 Qual cidade da Região Metropolitana de Fortaleza?",
}


# ----------------------------------------------------------------------------- #
# Pipeline principal
# ----------------------------------------------------------------------------- #
def carregar_base(csv_path, geo_bairros_path, geo_mun_path):
    df = pd.read_csv(csv_path)

    # ---- IDs amigáveis -----------------------------------------------------
    out = pd.DataFrame(index=df.index)
    out["titulo"] = df[COLS["titulo"]]
    out["veiculo"] = df[COLS["veiculo"]].astype(str).str.strip()
    out["resumo"] = df[COLS["resumo"]].fillna("").astype(str)
    out["link"] = df[COLS["link"]]

    # ---- Data -> ano (ISO, com guarda de intervalo) ------------------------
    dt = pd.to_datetime(df[COLS["data"]], format="%Y-%m-%d", errors="coerce")
    ano = dt.dt.year
    ano = ano.where((ano >= 2000) & (ano <= 2026))      # descarta typos (219, futuros absurdos)
    out["data"] = dt
    out["ano"] = ano

    # ---- Facção (lista normalizada por linha) ------------------------------
    def faccoes_linha(cell):
        fs = sorted({_norm_faccao(p) for p in _split(cell)})
        return fs
    out["faccoes"] = df[COLS["faccao"]].apply(faccoes_linha)

    # ---- Flags de crime/fenômeno ------------------------------------------
    for rotulo, col in CRIMES.items():
        if col in df.columns:
            out["crime__" + rotulo] = df[col].apply(_is_sim)
        else:
            out["crime__" + rotulo] = False

    # lista de crimes citados por linha (para filtro "todos os crimes")
    out["crimes"] = out.apply(
        lambda r: [k for k in CRIMES if r["crime__" + k]], axis=1
    )

    # ---- Geo: nomes oficiais dos polígonos ---------------------------------
    bairros_geo = {f["properties"]["Nome"] for f in
                   json.load(open(geo_bairros_path, encoding="utf-8"))["features"]}
    bairros_geo_norm = {_norm(b): b for b in bairros_geo}
    mun_geo = {f["properties"]["name"] for f in
               json.load(open(geo_mun_path, encoding="utf-8"))["features"]}
    mun_geo_norm = {_norm(m): m for m in mun_geo}

    def resolve_bairro(p):
        if _norm(p) in bairros_geo_norm:
            return bairros_geo_norm[_norm(p)]
        if p in DEPARA_BAIRROS:
            return DEPARA_BAIRROS[p]            # pode ser None (descartar)
        # tenta de-para por forma normalizada
        for k, v in DEPARA_BAIRROS.items():
            if _norm(k) == _norm(p):
                return v
        return None

    def resolve_cidade(p):
        return mun_geo_norm.get(_norm(p))       # None se não bater

    out["bairros"] = df[COLS["bairro"]].apply(
        lambda c: sorted({b for b in (resolve_bairro(x) for x in _split(c)) if b})
    )

    def cidades_linha(row):
        vals = _split(row[COLS["cidade_interior"]]) + _split(row[COLS["cidade_rmf"]])
        return sorted({c for c in (resolve_cidade(x) for x in vals) if c})
    out["cidades"] = df.apply(cidades_linha, axis=1)

    out = out.reset_index(drop=True)

    # ---- Tabelas long (explodidas) para os mapas ---------------------------
    longs = {
        "bairros": _explode_long(out, "bairros", "bairro"),
        "cidades": _explode_long(out, "cidades", "cidade"),
    }
    return out, longs


def _explode_long(df, col_lista, novo_nome):
    """Uma linha por (notícia, item da lista), preservando ano/facções/crimes/veículo."""
    base = df[[col_lista, "ano", "faccoes", "crimes", "veiculo"]].copy()
    base = base.explode(col_lista).dropna(subset=[col_lista])
    base = base.rename(columns={col_lista: novo_nome})
    return base.reset_index(drop=True)


if __name__ == "__main__":
    df, longs = carregar_base(
        "Questionário_Facções_na_Imprensa.csv",
        "Bairros_de_Fortaleza.geojson",
        "geojs-23-mun.json",
    )
    print("Notícias:", len(df))
    print("Anos:", sorted(df["ano"].dropna().astype(int).unique().tolist()))
    print("Bairros (long):", len(longs["bairros"]), "| únicos:",
          longs["bairros"]["bairro"].nunique())
    print("Cidades (long):", len(longs["cidades"]), "| únicas:",
          longs["cidades"]["cidade"].nunique())
    print("Facções vistas:", sorted({f for fs in df["faccoes"] for f in fs}))
    print("\nCrimes (% de notícias):")
    for k in CRIMES:
        print(f"  {df['crime__'+k].mean()*100:5.1f}%  {k}")

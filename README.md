# Dashboard — Facções na Imprensa (CE)

Protótipo local rodável. Fonte de dados: CSV (3.165 notícias) + 2 GeoJSON.

## Como rodar

1. Tenha Python 3.10+ instalado.
2. No terminal, dentro desta pasta:

```bash
pip install streamlit plotly pandas
streamlit run app.py
```

3. Abre sozinho no navegador (geralmente http://localhost:8501).

## Arquivos

- `app.py` — o dashboard (interface, filtros, 6 blocos).
- `limpeza.py` — pipeline de tratamento: limpeza das categóricas + preparo
  geográfico/temporal + aplicação do de-para de bairros (já validado).
- `Questionário_Facções_na_Imprensa.csv` — base (3.165 notícias).
- `Bairros_de_Fortaleza.geojson` — polígonos dos 121 bairros (IPLANFOR).
- `geojs-23-mun.json` — polígonos dos 184 municípios do CE (IBGE).
- `depara_bairros_Fortaleza.xlsx` — de-para de bairros validado (referência).

## O que tem no dashboard

- **Filtros globais** (lateral): facção, tipo de crime, período (ano). Combináveis.
  Tudo no painel recalcula ao vivo conforme os filtros.
- **Tabela de crimes** mencionados, ordenada por frequência.
- **Mapas coropléticos** (abas): bairros de Fortaleza e cidades do CE.
  Cor = contagem de notícias; bairro/cidade sem notícia fica claro/cinza.
- **Barras**: notícias por ano e por veículo.
- **5 pizzas** (ações contra a vida, operação policial, tráfico, controle
  territorial, conflito entre facções) + **barra consolidada** com todos os
  fenômenos por frequência.
- **Tabela de notícias** com busca por termo no resumo (= subtítulo),
  mostrando data, veículo, título, resumo e link.

## Próximo passo (produção)

Trocar a função `carregar()` em `app.py` para ler do Google Sheets em vez do
CSV local. O restante do pipeline não muda. Depois, deploy (Streamlit Cloud
ou container) — conforme conversamos.

## Notas de dados

- Datas em formato ISO (AAAA-MM-DD); 17 linhas com data inválida e alguns anos
  fora de 2000–2026 são tratados como sem-data (saem do gráfico anual, ficam no resto).
- ~316 notícias dizem "não especifica o bairro" — não entram no mapa de bairro
  (impossível localizar), mas seguem em todos os outros blocos.

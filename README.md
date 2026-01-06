# Web App — Risco de Inundação (AHP / Multicritério)

Web app em **Flask + Folium** para gerar e visualizar mapas de risco de inundação/alagamento por município em Pernambuco, a partir de uma análise multicritério com pesos por **AHP (Analytic Hierarchy Process)**.

A análise utiliza (quando ativados em configuração):

- **Hipsometria** (derivada do MDE)
- **Declividade** (derivada do MDE)
- **Fluxo acumulado** (a partir do MDE via WhiteboxTools)
- **Uso e cobertura do solo** (MapBiomas/GeoTIFF categórico)

## Como rodar

### 1) Pré-requisitos

- Python 3.10+ (recomendado)
- Dependências do projeto via `requirements.txt`
- Dados mínimos em `dados/` (ver seção **Dados necessários**)

### 2) Instalação (ambiente virtual)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Executar o servidor

Este projeto não possui `app.run()` no arquivo, então rode com o CLI do Flask:

```bash
python -m flask --app app:app run --debug
```

Por padrão o Flask sobe em `http://127.0.0.1:5000`.

Se precisar expor na rede local:

```bash
python -m flask --app app:app run --host 0.0.0.0 --port 5000 --debug
```

## Uso (interface)

1. Acesse `/` e selecione uma cidade.
2. Clique em **Executar análise** (a app gera rasters intermediários e o raster final de risco).
3. O mapa é renderizado com overlay do raster de risco e limite do município.
4. Clique no mapa para consultar valores no ponto (risco/uso do solo).

> Observação: a primeira execução para uma cidade pode demorar, pois gera e reprojeta rasters.

## Dados necessários

### Limites municipais (obrigatório)

O app carrega os municípios a partir do shapefile:

- `dados/PE_Municipios_2023/PE_Municipios_2023.shp` (e arquivos auxiliares `.dbf`, `.shx`, `.prj`, etc.)

### MDE (obrigatório para análise)

A análise precisa de um Modelo Digital de Elevação (MDE). O serviço resolve o MDE nesta ordem:

1. **Configuração em** `static/config/config.json` → `dados.mde` (por cidade ou estadual)
2. Arquivos por cidade em `dados/mde_<cidade>.tif` (ex.: `dados/mde_recife.tif`)
3. Mosaico estadual: `dados/mde_pernambuco.tif`

Se nenhum existir, a análise falha com mensagem indicando os caminhos esperados.

### Uso do solo (recomendado)

Para o critério **uso do solo**, o pipeline espera o GeoTIFF:

- `dados/uso-do-solo-pernambuco-2023.tif`

Se este arquivo não existir e o critério estiver `ativo`, a análise falhará.

## Configuração

O arquivo `static/config/config.json` controla:

- `cidades_suportadas`: allowlist de cidades (útil quando não há MDE estadual disponível)
- `criterios.*.ativo`: liga/desliga cada critério
- Classes de reclassificação:
  - `criterios.declividade.classes` (intervalar)
  - `criterios.fluxo_acumulado.classes` (intervalar)
  - `criterios.hipsometria.classes` (intervalar)
  - `criterios.uso_do_solo.classes` (categórico por IDs)
- Comparações par-a-par do AHP em `pesos.*` (ex.: `uso_vs_fluxo`, `declividade_vs_hipsometria`, etc.)

A rota `/config` salva alterações de configuração (weights/classes) e redireciona para a página inicial.

## Rotas principais (API)

- `GET /` — Página principal e mapa base
- `POST /executar_analise` — Executa a análise para uma cidade (JSON `{ "cidade": "Recife" }`)
- `GET /valor_ponto?cidade=...&lat=...&lon=...` — Consulta risco/uso do solo em um ponto
  - Opcional: pesos dinâmicos `w_uso`, `w_decl`, `w_flux`, `w_hipso` (normalizados internamente)
- `GET /overlay_risco?cidade=...&w_uso=...&w_decl=...&w_flux=...&w_hipso=...` — Retorna um PNG (data-url) do overlay de risco recalculado com pesos
- `GET /sobre` — Página “Sobre”

## Saídas geradas

A análise cria arquivos em `outputs/`:

- `outputs/mde/` — MDE alinhado à moldura municipal
- `outputs/molduras_municipios/` — Raster “mestre” (grid) por município
- `outputs/declividade/` — Declividade e reclassificado
- `outputs/fluxo_acumulado/` — Fluxo acumulado e reclassificado
- `outputs/uso_do_solo/` — Uso do solo alinhado e reclassificado
- `outputs/hipsometria/` — Hipsometria reclassificada
- `outputs/mapas_de_risco/` — Raster final de risco e versão recortada
- `outputs/mapas_interativos/` — HTMLs de mapas (quando gerados)

## Observações e troubleshooting

- **Whitebox/fluxo acumulado**: o cálculo usa `whitebox` (WhiteboxTools). Em macOS/Google Drive e caminhos com caracteres Unicode, a rotina roda o Whitebox em um diretório temporário (ASCII) e copia o resultado para `outputs/`.
- Se o resultado ficar “estranho”, uma limpeza comum é remover rasters antigos em `outputs/` da cidade e rodar novamente.

## Licença / autoria

(Preencha conforme sua necessidade.)

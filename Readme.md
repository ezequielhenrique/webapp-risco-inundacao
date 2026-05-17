# GeoCritério — Plataforma Web para Análise de Risco de Inundação

O **GeoCritério** é uma aplicação web desenvolvida em Python com Flask para geração e visualização de mapas de risco de inundação/alagamento a partir de uma análise multicritério baseada em **AHP (Analytic Hierarchy Process)**.

A plataforma integra processamento geoespacial, análise raster e visualização interativa em mapas, permitindo avaliar áreas suscetíveis a inundação em municípios de Pernambuco.

## Funcionalidades

- Geração automática de mapas de risco de inundação
- Análise multicritério utilizando AHP
- Visualização interativa com Leaflet
- Consulta de valores diretamente no mapa
- Reclassificação dinâmica de critérios
- Ajuste de pesos em tempo real
- Sobreposição de rasters no mapa
- Processamento geoespacial automatizado

## Critérios Utilizados

A análise pode utilizar os seguintes critérios:

- **Hipsometria** (derivada do MDE)
- **Declividade** (derivada do MDE)
- **Fluxo acumulado** (a partir do MDE via WhiteboxTools)
- **Uso e cobertura do solo** (MapBiomas/GeoTIFF categórico)

## Tecnologias Utilizadas

- Python
- Flask
- Rasterio
- GeoPandas
- NumPy
- Folium
- WhiteboxTools

---

# Instalação

## 1. Clonar o repositório

```bash
git clone <URL_DO_REPOSITORIO>
cd geocriterio
```

---

## 2. Criar ambiente virtual

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```bash
py -m venv .venv
.venv\Scripts\activate
```

---

## 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

# Dados do Projeto

Os arquivos geoespaciais utilizados no projeto **não estão incluídos no repositório** devido ao tamanho elevado dos datasets raster.

## Download dos dados

Faça o download dos arquivos através do link:

```text
https://drive.google.com/drive/folders/1Um1ff04B_xPGc_Cjp25djOC_hNgkhuZM?usp=sharing
```

Após o download:

1. Extraia os arquivos
2. Coloque a pasta `dados/` na raiz do projeto

---

# Dados Necessários

## Limites municipais

O projeto utiliza os shapefiles dos municípios de Pernambuco:

```text
dados/PE_Municipios_2023/
```

---

## Modelo Digital de Elevação (MDE)

Os rasters de elevação devem estar na pasta:

```text
dados/
```

Exemplos:

```text
dados/mde_pernambuco.tif
```

---

## Uso e cobertura do solo

Exemplo de arquivo esperado:

```text
dados/uso-do-solo-pernambuco-2023.tif
```

---

# Executando a Aplicação

O projeto utiliza Flask.

Execute:

```bash
flask run --debug
```

A aplicação ficará disponível em:

```text
http://127.0.0.1:5000
```

---

# Como Utilizar

1. Abra a aplicação no navegador
2. Selecione um município
3. Execute a análise
4. Aguarde o processamento dos rasters
5. Visualize o mapa de risco gerado
6. Clique no mapa para consultar valores locais

---

# Estrutura de Saídas

Os arquivos gerados automaticamente são armazenados em:

```text
outputs/
```

Principais diretórios:

```text
outputs/mde/
outputs/declividade/
outputs/fluxo_acumulado/
outputs/hipsometria/
outputs/uso_do_solo/
outputs/mapas_de_risco/
outputs/molduras_municipios/
outputs/uso_do_solo/
```

---

# API / Rotas Principais

## Página inicial

Renderiza a interface principal da aplicação.

```http
GET /
```

---

## Executar análise multicritério

Executa toda a análise geoespacial para o município selecionado.

```http
POST /executar_analise
```

### Payload

```json
{
  "cidade": "Recife",
  "config": {}
}
```

### Retorno

```json
{
  "status": "ok",
  "cidade": "Recife",
  "centro": [-8.05, -34.88],
  "config": {},
  "overlay_url": "...",
  "bounds": [],
  "uso_url": "...",
  "uso_bounds": []
}
```

A rota:

- Executa o pipeline completo de análise
- Gera os rasters intermediários
- Calcula o mapa final de risco
- Retorna overlays para visualização dinâmica no frontend

---

## Consultar valores em um ponto

Consulta valores raster em uma coordenada específica do mapa.

```http
POST /valor_ponto
```

### Payload

```json
{
  "cidade": "Recife",
  "lat": -8.05,
  "lon": -34.88
}
```

### Retorno

```json
{
  "risco": 3,
  "uso_solo": "Área Urbana",
  "declividade": 12.4,
  "elevacao": 15.7,
  "fluxo": 482
}
```

A rota consulta:

- risco de inundação
- uso do solo
- declividade
- elevação
- fluxo acumulado

---

## Atualizar overlay de risco dinamicamente

Recalcula o overlay de risco utilizando pesos personalizados enviados pelo frontend.

```http
GET /overlay_risco
```

### Query Params

```text
cidade
w_uso
w_decl
w_flux
w_hipso
```

### Exemplo

```http
/overlay_risco?cidade=Recife&w_uso=2&w_decl=1&w_flux=4&w_hipso=3
```

Os pesos são normalizados automaticamente antes do cálculo.

A rota retorna:

- overlay PNG em formato data-url
- pesos normalizados utilizados no cálculo

---

## Página Sobre

Renderiza a página institucional/informativa do projeto.

```http
GET /sobre
```

---

# Observações

- A primeira execução pode demorar devido ao processamento raster
- O WhiteboxTools é utilizado no cálculo de fluxo acumulado
- Recomenda-se utilizar SSD devido ao volume de leitura/escrita de rasters
- Os resultados variam conforme a resolução e qualidade dos dados utilizados

---

# Projeto Acadêmico

Projeto desenvolvido no contexto de pesquisas relacionadas à análise hidrológica e risco de inundação em Pernambuco.

---

# Licença

Este projeto é destinado para fins acadêmicos e educacionais.
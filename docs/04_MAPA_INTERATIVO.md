# 🗺️ Mapa Interativo Estilo Leaflet — Rascunho de Design

> ⚠️ **Atualizado em 2026-09-09**: a primeira versão (`L.imageOverlay`, sem tiling) foi implementada
> e depois **rejeitada pelo autor** ao testar — "zoom infinito" fake e trocas malfeitas de camada,
> não era "Google Maps real". A versão atual É a Abordagem B deste documento (pirâmide de tiles
> pré-gerada), com uma economia importante: profundidade só onde há continente/cidade, oceano vazio
> raso — evita o custo de gerar a pirâmide inteira em profundidade máxima. Ver a **Frente 6** do
> [`05_ROADMAP.md`](05_ROADMAP.md) para arquitetura, resultados e a limitação de costura encontrada.
>
> Documento de apoio à **Frente 6** do [`05_ROADMAP.md`](05_ROADMAP.md). Ideia do autor: "portar de alguma
> forma ou reutilizar os NPZs pra ter algum formato de 'Google Maps da aventura', tipo com leaflet."

## O que já existe e é reaproveitável

- **Dados fonte**: `.npz` com 4 canais (altitude, temperatura, umidade, ID de bioma) em 3 escalas:
  - Mundo composto: `database/mapa_composto.npz`, 768×768px (grid de tiles 3×3 de 256px cada).
  - Zoom de continente: `database/continentes/mapa_<slug>.npz`, gerado sob demanda em ~3000×3000px.
  - Zoom de cidade: `database/cidades/mapa_<slug>.npz`, gerado sob demanda em ~800×800px.
- **Renderer NumPy → PNG**: `web/helpers.py: render_npz_map_to_bytes()` já faz toda a composição
  visual (oceano, biomas, hillshading) a partir de um `.npz`.
- **Cache por mtime**: `composed_routes.py: obter_mapa_do_cache()` já evita recarregar o `.npz` do
  disco a cada requisição.
- **Coordenadas de entidades**: `Local.coordenadas` e a posição atual de cada NPC já são pares
  `[x, y]` na mesma grade dos mapas — dá para virar marcador do Leaflet sem re-projeção complexa.

## O gap técnico principal

O Leaflet (e qualquer visualizador de mapas em pirâmide — Google Maps, OpenLayers, MapLibre) espera
**tiles fixos de um esquema `{z}/{x}/{y}.png`**: para cada nível de zoom `z`, o mundo é cortado numa
grade de imagens quadradas (tradicionalmente 256×256px), e o cliente só baixa os tiles visíveis na
tela. Hoje o `render_npz_map_to_bytes()` faz o oposto: renderiza **o `.npz` inteiro como uma única
imagem**, do tamanho que ele for (768px, 3000px, 800px). Adaptar isso é o núcleo do trabalho desta
frente.

## Duas abordagens possíveis

### Abordagem A — Tiles gerados sob demanda (recomendada para começar)
Um endpoint Flask `/tiles/<escopo>/<z>/<x>/<y>.png` que, a cada requisição:
1. Escolhe qual `.npz` fonte usar dependendo de `z` (zooms baixos → mapa composto; zooms altos →
   zoom de continente/cidade já gerado sob demanda, reaproveitando `ROIZoomGenerator`/
   `CityROIZoomGenerator` existentes).
2. Recorta da fonte a região `[x*256 .. x*256+256, y*256 .. y*256+256]` correspondente àquele nível
   de zoom (com a devida escala/interpolação entre a resolução da fonte e a resolução do tile).
3. Renderiza só esse recorte com `render_npz_map_to_bytes`-like (adaptado para operar em recorte, não
   na imagem inteira) e devolve o PNG.
4. Cacheia o tile gerado em disco (`web/static/tiles_cache/<escopo>/<z>/<x>/<y>.png`) para não
   regerar o mesmo recorte a cada pan/zoom do usuário.

**Vantagem**: não precisa pré-gerar nada, funciona incrementalmente com o que já existe.
**Cuidado**: gerar tiles de zoom alto exige ter a fonte de zoom (continente/cidade) já gerada — o
fluxo de "gerar sob demanda" já existe para as imagens inteiras (`composed_routes.py`), só precisa
ser adaptado para recorte em vez de imagem cheia.

### Abordagem B — Pré-geração de pirâmide completa de tiles
Um script (rodando junto do `reset_world.sh`/`reset_cartography.sh`) que gera **todos** os tiles de
todos os níveis de zoom de uma vez, salvando em disco como arquivos estáticos servidos diretamente
pelo Flask (ou por um servidor de arquivos estático).

**Vantagem**: navegação no mapa fica instantânea (sem custo de geração por requisição).
**Custo**: tempo de build do mundo aumenta (gerar uma pirâmide completa de tiles para vários níveis
de zoom é bem mais trabalho que gerar 3 imagens únicas como hoje); e recalcular tudo a cada reset do
mundo pode ficar lento à medida que o mundo cresce (mais continentes/cidades).

**Recomendação inicial**: começar pela Abordagem A (sob demanda + cache em disco), que é incremental
sobre o que já existe, e migrar para B só se a geração sob demanda se mostrar lenta demais na prática.

## Sobreposição de entidades (NPCs, locais)

O Leaflet lida bem com marcadores/overlays via GeoJSON ou camadas customizadas. Como o mundo já usa
coordenadas de grade simples `[x, y]` (não lat/lng reais), duas opções:
- Usar `L.CRS.Simple` do Leaflet (modo "mapa de imagem plana", pensado exatamente para mapas de jogos
  e plantas baixas, sem projeção geográfica real) e mapear `[x, y]` do jogo direto para o sistema de
  coordenadas do Leaflet.
- Os endpoints que já existem para entidades por cidade (`composed_routes.py:
  api_cidade_entities`) podem virar a fonte de um layer de marcadores que se atualiza via polling
  (mesmo padrão já usado pelo `dashboard.js`, a cada 1s).

## Perguntas em aberto para decidir com o autor
1. O mapa Leaflet substitui o canvas atual (`mapa_composto.js`) ou convive como uma visualização
   alternativa/nova aba?
2. O foco inicial é navegação (pan/zoom fluido tipo Google Maps) ou já nasce com os NPCs em tempo
   real por cima (o que aumenta a complexidade de sincronização, mas é mais "vivo")?
3. Faz sentido reaproveitar o CRS simples (coordenadas de jogo) ou vale a pena, no futuro, dar uma
   "escala real" ao mundo (usando `escala_pixel_area_km2` já existente) para health-checks de
   distância/tempo de viagem ficarem plausíveis?

## Dependências
- Não depende tecnicamente de nenhuma outra frente — pode ser adiantada a qualquer momento.
- Se rodar **depois** da Frente 1 (parametrização), a lógica de renderização por recorte pode
  reaproveitar diretamente os mesmos parâmetros centralizados em vez de duplicar constantes (ex.:
  `nivel_mar`, paleta de cores) uma quarta vez, como já aconteceu em `web/helpers.py` hoje.

## Status
🔴 Não iniciado.

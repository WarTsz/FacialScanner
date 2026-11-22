# Spec Delta

## Purpose

Compara a representação de um scan com todos os itens do catálogo e devolve os 10 itens mais parecidos, sejam pessoas ou objetos, com uma porcentagem de similaridade.

## ADDED Requirements

### Requirement: Top 10 itens mais similares
O sistema SHALL retornar os 10 itens do catálogo mais similares ao scan, em ordem decrescente de similaridade. Pessoas e objetos SHALL concorrer no mesmo ranking, sem filtro por tipo.

#### Scenario: Ranking misto
- **WHEN** um scan de uma lata de refrigerante é comparado com um catálogo que tem pessoas e objetos
- **THEN** o ranking contém os 10 itens mais similares, independentemente de serem pessoas ou objetos

#### Scenario: Ordenação
- **WHEN** o ranking é exibido
- **THEN** cada item tem similaridade maior ou igual à do item seguinte

### Requirement: Agregação por item
O sistema SHALL ranquear itens, não imagens. Um item SHALL aparecer no máximo uma vez no ranking, independentemente de quantas imagens tiver, e sua similaridade SHALL vir das imagens que ele possui.

#### Scenario: Item com várias imagens
- **WHEN** várias imagens do mesmo item estão entre as mais próximas do scan
- **THEN** o item aparece uma única vez no ranking

### Requirement: Porcentagem de similaridade calibrada
O sistema SHALL exibir a similaridade como uma porcentagem de 0% a 100%, obtida por uma calibração da medida bruta, em que valores altos indicam o mesmo item ou um item visualmente quase igual. Essa mesma porcentagem SHALL ser usada pela regra de inserção.

#### Scenario: Faixa da porcentagem
- **WHEN** qualquer item é exibido no ranking
- **THEN** sua similaridade está entre 0% e 100%

#### Scenario: Mesmo item
- **WHEN** um objeto já catalogado é escaneado novamente em condições semelhantes
- **THEN** esse objeto aparece no topo do ranking com similaridade de pelo menos 90%

### Requirement: Resultado exibe apenas imagens
O sistema SHALL apresentar cada item do ranking apenas pela imagem e pela porcentagem. O nome interno do item MUST NOT ser exibido no ranking.

#### Scenario: Item sem nome visível
- **WHEN** o ranking é exibido
- **THEN** cada posição mostra uma imagem e uma porcentagem, sem o nome do item

### Requirement: Imagem mais parecida do item
O sistema SHALL representar cada item do ranking pela imagem desse item mais similar ao scan atual.

#### Scenario: Item com várias imagens
- **WHEN** um item com várias imagens aparece no ranking
- **THEN** a imagem exibida é a do item com maior similaridade com o scan

### Requirement: Catálogo com menos de 10 itens
O sistema SHALL exibir todos os itens disponíveis quando o catálogo tiver menos de 10 itens, e um ranking vazio quando o catálogo estiver vazio.

#### Scenario: Catálogo pequeno
- **WHEN** o catálogo tem 4 itens
- **THEN** o ranking mostra os 4 itens

#### Scenario: Catálogo vazio
- **WHEN** o catálogo não tem nenhum item
- **THEN** o ranking é vazio e o usuário é informado de que não há itens para comparar

### Requirement: Tempo de resposta
O sistema SHALL exibir o ranking em até 2 segundos após o fim da janela de captura, com um catálogo de até 10.000 itens, em um computador sem GPU dedicada.

#### Scenario: Resposta rápida
- **WHEN** a janela de captura de 5 segundos termina
- **THEN** o ranking aparece em até 2 segundos

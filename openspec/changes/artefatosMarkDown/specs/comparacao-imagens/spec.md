# Spec Delta

## Purpose

Permite buscar no catálogo a partir de uma ou mais imagens de um mesmo objeto, sem câmera, com o mesmo ranking do scan, validando as imagens e descartando as que não pertencem ao objeto.

## ADDED Requirements

### Requirement: Busca no catálogo a partir de imagens
O sistema SHALL aceitar uma ou mais imagens de um mesmo objeto, escolhidas pelo usuário, e mostrar o top 10 do catálogo com as mesmas regras do ranking do scan, sem usar a câmera.

#### Scenario: Uma imagem
- **WHEN** o usuário compara uma única imagem válida
- **THEN** o sistema mostra o top 10 do catálogo para essa imagem

#### Scenario: Várias imagens do mesmo objeto
- **WHEN** o usuário compara quatro imagens semelhantes do mesmo objeto
- **THEN** todas participam de uma única busca, representadas pela média normalizada dos seus vetores

### Requirement: Validação de qualidade das imagens
Cada imagem SHALL passar pelo mesmo filtro de qualidade e recorte da adição manual de imagens. Imagens ilegíveis ou reprovadas SHALL ser descartadas e listadas com o motivo.

#### Scenario: Imagem borrada
- **WHEN** uma das imagens está borrada
- **THEN** ela é descartada com o motivo "borrado" e a busca usa as demais

#### Scenario: Nenhuma imagem válida
- **WHEN** nenhuma das imagens passa no filtro de qualidade
- **THEN** nenhuma busca é feita, nada é inserido e o usuário é informado do motivo de cada imagem

### Requirement: Agrupamento por semelhança mínima
As imagens válidas SHALL ser agrupadas em ordem: cada imagem entra no primeiro grupo, entre os já formados, cuja semelhança com a média do grupo seja a maior e atinja a semelhança mínima configurável (padrão 50%, na escala calibrada); se não atingir com nenhum, forma um grupo novo.

#### Scenario: Imagens semelhantes
- **WHEN** todas as imagens válidas são semelhantes entre si
- **THEN** elas formam um único grupo

#### Scenario: Imagem completamente diferente
- **WHEN** três imagens são de um objeto e uma é de algo completamente diferente
- **THEN** a imagem diferente forma outro grupo

### Requirement: Escolha do grupo
O sistema SHALL usar o grupo com mais imagens; em caso de empate, o grupo formado primeiro. As imagens dos outros grupos SHALL ser descartadas e listadas como diferentes do grupo escolhido.

#### Scenario: Maior grupo vence
- **WHEN** há um grupo com três imagens e outro com uma
- **THEN** a busca usa o grupo de três e a imagem do outro grupo é listada como diferente

#### Scenario: Empate
- **WHEN** há dois grupos com duas imagens cada
- **THEN** a busca usa o grupo formado primeiro, isto é, o que contém a primeira imagem válida

### Requirement: Inserção a partir das imagens
Se o 1º colocado do ranking ficar abaixo de 90%, ou o catálogo estiver vazio, todas as imagens do grupo escolhido SHALL virar um novo item com nome automático, como um item de scan, sem pedido de consentimento, inclusive para rostos. Com 90% ou mais, nada SHALL ser gravado.

#### Scenario: Objeto novo
- **WHEN** o 1º colocado tem 72%
- **THEN** as imagens do grupo escolhido viram um novo item `item-NNNNNN` e o usuário é avisado

#### Scenario: Objeto já catalogado
- **WHEN** o 1º colocado tem 90% ou mais
- **THEN** nada é gravado no catálogo nem no disco

#### Scenario: Rosto
- **WHEN** as imagens do grupo escolhido contêm um rosto e o 1º colocado fica abaixo de 90%
- **THEN** o item é criado sem pedido de consentimento

### Requirement: Resumo da validação
O resultado SHALL informar quantas imagens foram usadas e listar as descartadas por qualidade e as descartadas por serem diferentes do grupo escolhido.

#### Scenario: Resumo completo
- **WHEN** de cinco imagens, uma é borrada e uma é diferente das demais
- **THEN** o resultado informa que 3 imagens foram usadas, a borrada com o motivo e a diferente como fora do grupo

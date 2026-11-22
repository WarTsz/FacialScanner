# Spec Delta

## Purpose

Mantém o catálogo de itens (pessoas e objetos) usado nas comparações: carga inicial manual, crescimento a partir dos scans, nomeação automática, consentimento para rostos e remoção.

## ADDED Requirements

### Requirement: Estrutura do item
Cada item do catálogo SHALL ter um nome único, uma origem ("seed" para itens importados pela linha de comando ou "scan" para itens criados pelo aplicativo, pelo scanner ou pela adição manual de imagens), uma ou mais imagens e a representação vetorial de cada imagem.

#### Scenario: Item completo
- **WHEN** um item é adicionado ao catálogo, por seed, por scan ou pela adição manual de imagens
- **THEN** ele tem nome único, origem registrada, pelo menos uma imagem e um vetor para cada imagem

### Requirement: Seed manual por linha de comando
O sistema SHALL oferecer um comando que importa itens a partir de uma pasta em que cada subpasta é um item e contém suas imagens. As imagens SHALL passar pelo mesmo recorte e pelo mesmo filtro de qualidade aplicados aos scans.

#### Scenario: Importação de uma pasta de seed
- **WHEN** o comando de seed é executado sobre uma pasta com as subpastas `pele/` e `lata-coca/`
- **THEN** dois itens com origem "seed" são criados, cada um com as imagens válidas da sua subpasta

#### Scenario: Imagem inválida no seed
- **WHEN** uma imagem da subpasta não passa no filtro de qualidade ou não tem sujeito identificável
- **THEN** a imagem é ignorada, o comando informa qual foi ignorada e as demais imagens do item são importadas

#### Scenario: Subpasta sem imagens válidas
- **WHEN** nenhuma imagem de uma subpasta é válida
- **THEN** nenhum item é criado para essa subpasta e o comando informa o motivo

### Requirement: Inserção dinâmica por novidade
Ao fim de cada scan bem-sucedido, o sistema SHALL inserir o scan como um novo item quando a similaridade do 1º colocado do ranking for menor que 90%, ou quando o catálogo estiver vazio. Com similaridade de 90% ou mais, o scan SHALL ser descartado e o item existente não é alterado.

#### Scenario: Scan novo
- **WHEN** o 1º colocado do ranking tem 72% de similaridade
- **THEN** o scan se torna elegível para inserção como novo item

#### Scenario: Scan repetido
- **WHEN** o 1º colocado do ranking tem 90% ou mais de similaridade
- **THEN** o scan é descartado e nenhum item é criado nem alterado

#### Scenario: Primeiro scan em catálogo vazio
- **WHEN** um scan é concluído e o catálogo está vazio
- **THEN** o scan se torna elegível para inserção como novo item

### Requirement: Nome automático e único
O sistema SHALL gerar automaticamente o nome de cada item inserido por scan ou pela adição manual de imagens, no formato `item-` seguido de um número sequencial de 6 dígitos. O número MUST NOT ser reutilizado, nem depois que um item for removido. O usuário MUST NOT escolher o nome.

#### Scenario: Numeração sequencial
- **WHEN** o último item criado foi `item-000041` e um novo scan é inserido
- **THEN** o novo item recebe o nome `item-000042`

#### Scenario: Número de item removido
- **WHEN** `item-000042` é removido e depois um novo scan é inserido
- **THEN** o novo item recebe `item-000043`, e não `item-000042`

### Requirement: Imagens guardadas de um scan inserido
Quando um scan é inserido, o sistema SHALL guardar como imagens do novo item os k melhores frames do scan, segundo o filtro de qualidade, com k configurável, além dos vetores correspondentes.

#### Scenario: Seleção dos melhores frames
- **WHEN** um scan com 15 frames válidos é inserido e k é 3
- **THEN** o novo item guarda os 3 frames de maior qualidade e seus vetores

### Requirement: Adição manual de imagens
O sistema SHALL permitir adicionar ao catálogo, sem passar pelo scanner, um novo item formado por um ou mais arquivos de imagem escolhidos pelo usuário. Cada imagem SHALL passar pelo filtro de qualidade e pelo recorte do seed. Todas as imagens válidas SHALL formar um único item guardado como um item de scan: origem "scan", nome automático, imagens e vetores.

#### Scenario: Imagens válidas
- **WHEN** o usuário adiciona três imagens válidas do mesmo objeto
- **THEN** um novo item de origem "scan" e nome `item-` mais 6 dígitos é criado com as três imagens e seus vetores

#### Scenario: Imagem inválida entre as escolhidas
- **WHEN** uma das imagens escolhidas está borrada, escura demais, tem um rosto pequeno demais ou não é uma imagem legível
- **THEN** essa imagem é ignorada, o motivo é informado e as demais formam o item

#### Scenario: Nenhuma imagem válida
- **WHEN** nenhuma das imagens escolhidas é válida
- **THEN** nenhum item é criado e o motivo de cada imagem ignorada é informado

### Requirement: Adição manual sem regra dos 90% nem consentimento
Na adição manual de imagens, a regra dos 90% MUST NOT ser aplicada e nenhum consentimento SHALL ser pedido, mesmo quando as imagens contêm um rosto.

#### Scenario: Imagens parecidas com um item existente
- **WHEN** as imagens adicionadas têm 90% ou mais de similaridade com um item do catálogo
- **THEN** o novo item é criado mesmo assim

#### Scenario: Imagem com rosto
- **WHEN** as imagens adicionadas contêm um rosto
- **THEN** o item é criado sem pedido de consentimento

### Requirement: Consentimento para rostos
O sistema MUST obter consentimento explícito do usuário antes de inserir um scan marcado como "contém rosto". O pedido de consentimento SHALL informar que a imagem será armazenada e poderá aparecer nos resultados de outros usuários. Scans de objeto SHALL ser inseridos sem consentimento.

#### Scenario: Consentimento aceito
- **WHEN** um scan com rosto é elegível para inserção e o usuário aceita o consentimento
- **THEN** o scan é inserido como novo item

#### Scenario: Consentimento recusado
- **WHEN** um scan com rosto é elegível para inserção e o usuário recusa o consentimento
- **THEN** nada é inserido, o scan é descartado e o ranking já exibido continua visível

#### Scenario: Objeto elegível
- **WHEN** um scan de objeto é elegível para inserção
- **THEN** o scan é inserido sem pedir consentimento

### Requirement: Remoção de itens criados por scan
O sistema SHALL permitir remover qualquer item de origem "scan", inclusive os criados pela adição manual de imagens, apagando de forma definitiva suas imagens e vetores, de modo que ele não apareça mais em nenhum ranking.

#### Scenario: Remoção de item
- **WHEN** o item `item-000042` é removido
- **THEN** suas imagens e vetores são apagados e nenhum ranking posterior o inclui

### Requirement: Persistência local
O catálogo SHALL persistir localmente entre execuções do aplicativo.

#### Scenario: Reinício do aplicativo
- **WHEN** o aplicativo é fechado e aberto novamente
- **THEN** todos os itens existentes antes do fechamento continuam disponíveis para comparação

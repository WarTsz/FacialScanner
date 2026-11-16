# Spec Delta

## Purpose

Interface gráfica desktop pela qual o usuário vê a câmera, faz scans, consulta os resultados, responde ao consentimento, adiciona imagens ao catálogo e remove itens criados pelo aplicativo.

## ADDED Requirements

### Requirement: Tela de espera com preview da câmera
O aplicativo SHALL abrir em uma tela com o preview ao vivo da câmera e uma ação para iniciar o scan.

#### Scenario: Abertura do aplicativo
- **WHEN** o aplicativo é aberto com uma câmera disponível
- **THEN** o preview ao vivo e a ação "Escanear" são exibidos

#### Scenario: Câmera indisponível
- **WHEN** o aplicativo é aberto sem câmera acessível
- **THEN** uma mensagem informa que a câmera não foi encontrada e a ação "Escanear" fica desabilitada

### Requirement: Feedback durante a captura
Durante a janela de 5 segundos, a interface SHALL manter o preview da câmera, mostrar uma moldura indicando onde posicionar o sujeito e exibir o progresso ou o tempo restante. Não SHALL ser possível iniciar outro scan enquanto um estiver em andamento.

#### Scenario: Captura em andamento
- **WHEN** o usuário inicia um scan
- **THEN** a interface mostra a moldura e o tempo restante até o fim dos 5 segundos, e a ação "Escanear" fica desabilitada

### Requirement: Falha de captura
A interface SHALL informar quando um scan falhar por falta de frames válidos e permitir uma nova tentativa.

#### Scenario: Frames insuficientes
- **WHEN** o scan falha por falta de frames válidos
- **THEN** a interface mostra "Tente novamente", com uma dica de enquadramento e iluminação, e volta para a tela de espera

### Requirement: Tela de resultados
A interface SHALL exibir o ranking em uma grade, com cada posição mostrando a imagem do item e sua porcentagem de similaridade, sem o nome do item, e SHALL oferecer a ação de iniciar um novo scan.

#### Scenario: Exibição do ranking
- **WHEN** o ranking fica pronto
- **THEN** a interface mostra até 10 imagens em ordem, cada uma com sua porcentagem, e a ação "Novo scan"

### Requirement: Diálogo de consentimento
Quando um scan com rosto for elegível para inserção, a interface SHALL mostrar, sobre a tela de resultados, um diálogo de consentimento que informa que a imagem será armazenada e poderá aparecer para outros usuários, com as opções de aceitar e recusar.

#### Scenario: Diálogo exibido
- **WHEN** o ranking de um scan com rosto é exibido e o 1º colocado tem menos de 90%
- **THEN** o diálogo de consentimento aparece com as opções "Aceitar" e "Recusar"

#### Scenario: Diálogo não exibido
- **WHEN** o 1º colocado tem 90% ou mais, ou o scan é de um objeto
- **THEN** nenhum diálogo de consentimento é exibido

### Requirement: Aviso de inserção
A interface SHALL avisar quando um scan for inserido no catálogo, sem exibir o nome gerado.

#### Scenario: Objeto inserido
- **WHEN** um scan de objeto é inserido automaticamente
- **THEN** a interface mostra o aviso "Novo item adicionado ao catálogo"

### Requirement: Tela de remoção de itens
A interface SHALL oferecer uma tela que lista os itens de origem "scan" pela imagem e pelo nome gerado e permite remover um item, com confirmação antes da remoção. Itens de origem "seed" MUST NOT aparecer nessa tela.

#### Scenario: Remoção confirmada
- **WHEN** o usuário seleciona um item na tela de remoção e confirma
- **THEN** o item é removido do catálogo e some da lista

#### Scenario: Remoção cancelada
- **WHEN** o usuário seleciona um item e cancela a confirmação
- **THEN** o item continua no catálogo

### Requirement: Adição de imagens pela interface
A tela de espera SHALL oferecer a ação "Adicionar imagens", que abre um seletor de arquivos de imagem com seleção múltipla. Enquanto as imagens são processadas, a interface SHALL mostrar um indicador de processamento e desabilitar as ações da tela de espera. Ao fim, SHALL informar quantas imagens foram adicionadas e quais foram ignoradas, com o motivo, sem exibir o nome gerado. A ação SHALL estar disponível mesmo sem câmera.

#### Scenario: Imagens adicionadas
- **WHEN** o usuário escolhe imagens no seletor e ao menos uma é válida
- **THEN** a interface mostra um indicador de processamento e depois avisa que um novo item foi adicionado, com o número de imagens guardadas e as ignoradas

#### Scenario: Nenhuma imagem válida
- **WHEN** nenhuma das imagens escolhidas é válida
- **THEN** a interface informa que nada foi adicionado e mostra o motivo de cada imagem ignorada

#### Scenario: Seletor cancelado
- **WHEN** o usuário fecha o seletor sem escolher imagens
- **THEN** nada é processado e a tela de espera continua como estava

#### Scenario: Sem câmera
- **WHEN** o aplicativo está aberto sem câmera acessível
- **THEN** a ação "Adicionar imagens" continua disponível, embora "Escanear" fique desabilitada

### Requirement: Interface responsiva durante o processamento
A interface MUST NOT travar durante a captura, a geração dos vetores ou a busca. O preview e as animações de progresso SHALL continuar atualizando.

#### Scenario: Processamento pós-captura
- **WHEN** o sistema está gerando o vetor e buscando o ranking
- **THEN** a interface mostra um indicador de processamento e continua respondendo

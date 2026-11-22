# Spec Delta

## Purpose

Torna a câmera opcional: detecta os dispositivos de vídeo disponíveis, permite ativar, desativar e trocar a câmera, lembra a última escolha e bloqueia as funções que dependem dela.

## ADDED Requirements

### Requirement: Detecção de dispositivos de vídeo
O sistema SHALL listar os dispositivos de vídeo capazes de capturar imagem, com um nome legível, ignorando dispositivos que não entregam vídeo (como nós só de metadados). A lista SHALL poder ser atualizada pelo usuário sem reiniciar o aplicativo.

#### Scenario: Câmera com nó de metadados
- **WHEN** uma webcam expõe um dispositivo de captura e outro só de metadados
- **THEN** apenas o dispositivo de captura aparece na lista

#### Scenario: Câmera conectada depois
- **WHEN** uma câmera é conectada com o aplicativo aberto e o usuário atualiza a lista
- **THEN** a nova câmera passa a aparecer na lista

#### Scenario: Nenhum dispositivo
- **WHEN** nenhum dispositivo de vídeo é encontrado
- **THEN** a lista informa que não há câmera e a ativação fica indisponível

### Requirement: Ativar e desativar a câmera
O usuário SHALL poder ativar e desativar a câmera a qualquer momento fora de um scan. Com a câmera desativada, o aplicativo MUST NOT acessar o dispositivo e o preview SHALL informar que a câmera está desativada.

#### Scenario: Desativar
- **WHEN** o usuário desativa a câmera
- **THEN** o dispositivo é liberado e o preview mostra "Câmera desativada"

#### Scenario: Ativar
- **WHEN** o usuário ativa a câmera com um dispositivo selecionado
- **THEN** o preview ao vivo volta a ser exibido

### Requirement: Troca de dispositivo
O usuário SHALL poder escolher outro dispositivo da lista fora de um scan. Com a câmera ativa, a troca SHALL passar a exibir o novo dispositivo; se ele não puder ser aberto, a câmera SHALL ficar desativada e o usuário SHALL ser informado.

#### Scenario: Troca com a câmera ativa
- **WHEN** o usuário escolhe outro dispositivo com a câmera ativa
- **THEN** o preview passa a mostrar o novo dispositivo

#### Scenario: Dispositivo que não abre
- **WHEN** o dispositivo escolhido não pode ser aberto
- **THEN** a câmera fica desativada e uma mensagem informa o problema

### Requirement: Funções que exigem câmera
Sem câmera ativa, o scan MUST NOT poder ser iniciado. As funções que não dependem da câmera (adicionar imagens, comparar imagens e gerenciar itens) SHALL continuar disponíveis. Durante um scan, a câmera MUST NOT poder ser desativada nem trocada.

#### Scenario: Sem câmera ativa
- **WHEN** a câmera está desativada ou não há dispositivo
- **THEN** "Escanear" fica desabilitado, e "Adicionar imagens", "Comparar imagens" e "Gerenciar itens" continuam habilitados

#### Scenario: Durante o scan
- **WHEN** um scan está em andamento
- **THEN** os controles de câmera ficam desabilitados até o fim do scan

### Requirement: Memória da última escolha
O aplicativo SHALL guardar o dispositivo escolhido e o estado ativado ou desativado e SHALL abrir com essa escolha. Se o dispositivo guardado não estiver disponível, SHALL abrir com a câmera desativada.

#### Scenario: Reabrir o aplicativo
- **WHEN** o usuário desativa a câmera, fecha e reabre o aplicativo
- **THEN** o aplicativo abre com a câmera desativada

#### Scenario: Dispositivo ausente
- **WHEN** o dispositivo guardado não está conectado ao abrir o aplicativo
- **THEN** o aplicativo abre com a câmera desativada e informa que a câmera não foi encontrada

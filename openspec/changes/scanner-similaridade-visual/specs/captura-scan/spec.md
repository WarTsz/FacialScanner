# Spec Delta

## Purpose

Captura, durante uma janela de 5 segundos, o rosto ou objeto diante da câmera e o transforma em uma representação única e estável, usada para busca e inserção no catálogo.

## ADDED Requirements

### Requirement: Janela de captura de 5 segundos
O sistema SHALL capturar frames da câmera durante uma janela de 5 segundos iniciada pelo usuário. A quantidade n de frames SHALL ser configurável, e o valor padrão SHALL ser suficiente para produzir um resultado estável.

#### Scenario: Captura iniciada pelo usuário
- **WHEN** o usuário inicia um scan
- **THEN** o sistema captura n frames distribuídos ao longo de 5 segundos e encerra a captura ao fim da janela

#### Scenario: Quantidade de frames configurada
- **WHEN** o valor de n é alterado na configuração
- **THEN** os scans seguintes capturam n frames na mesma janela de 5 segundos

#### Scenario: Câmera sem frame novo no instante da amostra
- **WHEN** chega o instante de uma amostra e a câmera ainda não entregou um frame novo desde a amostra anterior
- **THEN** a amostra usa o próximo frame entregue pela câmera, e nenhum frame entra mais de uma vez no mesmo scan

### Requirement: Filtro de qualidade dos frames
O sistema SHALL descartar os frames inadequados para comparação, como frames borrados, escuros demais ou sem sujeito identificável.

#### Scenario: Frame borrado descartado
- **WHEN** um frame capturado está borrado além do limite de qualidade
- **THEN** o frame não participa da representação do scan

### Requirement: Mínimo de frames válidos
O sistema SHALL exigir um número mínimo configurável M de frames válidos. Abaixo desse mínimo, o scan falha sem realizar busca nem inserção.

#### Scenario: Frames válidos insuficientes
- **WHEN** menos de M frames passam pelo filtro de qualidade
- **THEN** o scan falha, nenhuma busca é feita, nada é inserido no catálogo e o usuário é orientado a tentar novamente

### Requirement: Recorte do sujeito
O sistema SHALL recortar o sujeito de cada frame válido antes de gerar a representação: o rosto quando um rosto é detectado dentro da moldura da interface e, caso contrário, o objeto em destaque na moldura. Um rosto cujo centro fica fora da moldura MUST NOT definir o sujeito do frame nem invalidá-lo.

#### Scenario: Rosto presente
- **WHEN** um rosto é detectado no frame com o centro dentro da moldura
- **THEN** a representação usa o recorte do rosto, não a imagem inteira

#### Scenario: Rosto fora da moldura
- **WHEN** um objeto está dentro da moldura e um rosto aparece no frame com o centro fora dela
- **THEN** o rosto é ignorado e a representação usa o recorte do objeto na moldura

#### Scenario: Objeto sem rosto
- **WHEN** nenhum rosto é detectado no frame
- **THEN** a representação usa o recorte do objeto em destaque

### Requirement: Classificação do scan como rosto ou objeto
O sistema SHALL marcar o scan como "contém rosto" quando a maioria dos frames válidos tiver um rosto detectado e, caso contrário, como "objeto". Essa marcação define se o consentimento é necessário para a inserção.

#### Scenario: Scan de rosto
- **WHEN** a maioria dos frames válidos contém um rosto
- **THEN** o scan é marcado como "contém rosto"

#### Scenario: Scan de objeto
- **WHEN** a maioria dos frames válidos não contém rosto
- **THEN** o scan é marcado como "objeto"

### Requirement: Representação agregada do scan
O sistema SHALL agregar os frames válidos em uma única representação vetorial, gerada pelo mesmo modelo usado para todo o catálogo, de modo que rostos e objetos fiquem no mesmo espaço de comparação.

#### Scenario: Agregação dos frames
- **WHEN** a captura termina com pelo menos M frames válidos
- **THEN** o sistema produz um único vetor representando o scan, combinando os vetores dos frames válidos

### Requirement: Imagens do scan não persistem sem inserção
O sistema MUST NOT manter os frames ou a representação de um scan depois do fim do fluxo, a menos que o scan seja inserido no catálogo.

#### Scenario: Scan descartado
- **WHEN** um scan termina sem ser inserido no catálogo
- **THEN** seus frames e seu vetor são apagados da memória e do disco

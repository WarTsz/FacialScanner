# Proposta

## Por quê

Queremos um scanner visual que, em uma janela de 5 segundos, capture o que está diante da câmera (um rosto ou um objeto) e mostre os 10 itens mais parecidos de um catálogo, com a porcentagem de similaridade de cada um. O catálogo começa com pessoas públicas e objetos inseridos manualmente e cresce sozinho: cada scan suficientemente novo vira um item do catálogo.

## O que muda

- Novo aplicativo desktop com interface gráfica que mostra o preview da câmera, conduz a captura de 5 segundos e exibe os resultados.
- Captura de n frames (configurável) durante 5 segundos. Os frames passam por um filtro de qualidade e pelo recorte do sujeito (o rosto, se houver; senão, o objeto central) e são agregados em um único vetor de embedding.
- Um único modelo de embedding genérico para rostos e objetos, de forma que pessoas e objetos fiquem no mesmo espaço e no mesmo ranking.
- Ranking dos 10 itens mais similares, agregado por item, com % de similaridade calibrada (não o cosseno bruto). Os resultados mostram apenas imagens, sem nomes.
- Inserção dinâmica: se a similaridade do 1º colocado for menor que 90%, o scan vira um novo item com nome automático único (`item-000001`, `item-000002`, ...). Com 90% ou mais, o scan é descartado.
- Consentimento explícito antes de inserir um scan que contenha rosto (LGPD, dado biométrico sensível). Objetos são inseridos sem consentimento.
- Seed manual do catálogo por script de linha de comando, a partir de pastas `seed/<item>/*.jpg`.
- Tela de remoção de itens criados por scan na interface.
- Adição manual de imagens pela interface: o usuário escolhe arquivos de imagem, que viram um novo item guardado da mesma forma que um item de scan (nome automático, mesma pasta de imagens, removível na interface), sem a regra dos 90% e sem pedido de consentimento.
- Fora de escopo: busca de imagens no Google, validador de "rosto humano vs. objeto" na inserção, análise por característica facial e versão web.

## Capacidades

### Novas capacidades

- `captura-scan`: janela de captura de 5 segundos, filtro de qualidade dos frames, recorte do sujeito e geração do vetor agregado do scan.
- `ranking-similaridade`: busca no catálogo, agregação por item, % calibrada e top 10 com a imagem mais parecida de cada item.
- `catalogo-itens`: armazenamento dos itens, seed manual, inserção dinâmica com a regra dos 90%, nomeação automática, consentimento e remoção.
- `interface-scanner`: telas e fluxo do aplicativo desktop (espera, captura, resultados, consentimento, avisos e remoção).

### Capacidades modificadas

Nenhuma. O projeto ainda não tem specs.

## Impacto

- Projeto novo, sem código existente.
- Aplicativo desktop em Python, com dependências de visão computacional (câmera e detecção de rosto), um modelo de embedding pré-treinado, um índice vetorial e um toolkit de interface gráfica.
- Armazenamento local de imagens e vetores na máquina onde o aplicativo roda.
- Requer webcam.
- Dados biométricos de usuários são armazenados apenas com consentimento e podem ser removidos.

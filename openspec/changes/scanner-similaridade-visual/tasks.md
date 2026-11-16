# Tasks

## 1. Estrutura do projeto

- [x] 1.1 Criar o pacote `scanner/` com os módulos `captura`, `qualidade`, `recorte`, `embedding`, `catalogo`, `ranking`, `calibracao`, `gui`, `cli` e um `__main__.py`, e verificar que `python -m scanner --help` executa
- [x] 1.2 Criar `pyproject.toml` com as dependências (PySide6, opencv-python, torch, numpy, pytest) e verificar que a instalação em um ambiente limpo conclui sem erros
- [x] 1.3 Criar `config.toml` com n=15, M=5, k=3, limiar=90, índice da câmera, limiares de qualidade e âncoras de calibração provisórias, mais um carregador de configuração; verificar com um teste que lê os valores e aplica os padrões quando uma chave falta
- [x] 1.4 Implementar o comando `python -m scanner preparar`, que baixa e guarda localmente os pesos do YuNet e do DINOv2 ViT-S/14, e verificar que uma segunda execução não baixa nada de novo

## 2. Pipeline de imagem (qualidade, recorte, embedding)

- [x] 2.1 Implementar o filtro de qualidade (variância do Laplaciano, brilho médio e pontuação de qualidade) e verificar com testes usando uma imagem nítida, uma borrada e uma escura
- [x] 2.2 Implementar a detecção de rosto com YuNet (confiança de pelo menos 0,8 e lado mínimo de 80 px) e verificar com testes usando uma imagem com rosto e uma de objeto
- [x] 2.3 Implementar o recorte do sujeito (rosto com margem de 20% alinhado pelos olhos; senão, a região da moldura) e verificar com testes as dimensões e a região do recorte nos dois casos
- [x] 2.4 Implementar o embedding DINOv2 ViT-S/14 com saída normalizada de 384 dimensões e verificar com testes a dimensão, a norma 1 e que a mesma imagem gera o mesmo vetor
- [x] 2.5 Implementar a agregação do scan (marcação "contém rosto" por maioria, filtragem pela classe majoritária, média normalizada e falha abaixo de M frames válidos) e verificar com testes os casos de rosto, objeto e frames insuficientes

## 3. Catálogo

- [x] 3.1 Implementar o esquema SQLite (`itens` com `AUTOINCREMENT` e `nome UNIQUE`, `imagens` com o vetor em BLOB) e o armazenamento de arquivos em `data/images/<nome>/`, e verificar com um teste que o banco é criado e reaberto sem perda de dados
- [x] 3.2 Implementar a inserção de item por scan com o nome `item-{id:06d}` e os k melhores frames, e verificar com testes a numeração sequencial e a não reutilização do número depois de uma remoção
- [x] 3.3 Implementar a remoção definitiva de itens de origem "scan" (linhas, vetores e arquivos), recusando itens de "seed", e verificar com testes que o item some do banco, do disco e da busca
- [x] 3.4 Implementar a CLI `python -m scanner seed <pasta>` (uma subpasta por item, mesmo pipeline do scan, relatório de imagens ignoradas, conflito de nome pulado) e verificar com um teste sobre uma pasta de exemplo com imagens válidas, imagens inválidas e uma subpasta vazia
- [x] 3.5 Documentar no `README.md` o formato da pasta de seed e o uso da CLI, e verificar que o comando documentado roda como descrito

## 4. Ranking e calibração

- [x] 4.1 Implementar o índice em memória (matriz NumPy e vetor de `item_id`) carregado do SQLite e atualizado em inserções e remoções, e verificar com testes a sincronização depois de inserir e remover
- [x] 4.2 Implementar a busca com agregação por item usando o máximo, devolvendo o top 10 com a imagem mais parecida de cada item, e verificar com testes a unicidade de cada item, a ordenação, um catálogo com menos de 10 itens e um catálogo vazio
- [x] 4.3 Implementar o mapeamento linear por partes do cosseno para % (âncoras `cos_zero` e `cos_noventa`, limitado a [0, 100]) e verificar com testes os valores nas âncoras e nos extremos
- [x] 4.4 Implementar o script `python -m scanner calibrar` (pares iguais e diferentes, mediana e percentil 10, relatório das distribuições, gravação em `config.toml`) e verificar rodando sobre o seed de exemplo
- [x] 4.5 Implementar a regra de inserção (descarta com 90% ou mais; elegível abaixo de 90% ou com catálogo vazio; exige consentimento se o scan contém rosto) como uma função pura, e verificar com testes cada combinação
- [x] 4.6 Medir o tempo entre o fim da captura e o ranking com um catálogo sintético de 10.000 itens em CPU, e verificar que fica abaixo de 2 s (exportar para ONNX Runtime se não ficar)

## 5. Interface gráfica

- [x] 5.1 Implementar a janela principal com a thread de câmera, o preview ao vivo e o botão "Escanear", e a mensagem de câmera indisponível com o botão desabilitado; verificar abrindo o app com e sem câmera
- [x] 5.2 Implementar a tela de captura (moldura, contagem de 5 s, botão desabilitado e envio dos frames ao worker em `QThreadPool` durante a captura), e verificar manualmente que o preview não trava
- [x] 5.3 Implementar o tratamento de falha de captura ("Tente novamente" com dica e volta para a espera), e verificar cobrindo a câmera durante um scan
- [x] 5.4 Implementar a tela de resultados (grade de até 10 imagens com %, sem nomes, indicador de processamento e botão "Novo scan"), e verificar com um scan real e com o catálogo vazio
- [x] 5.5 Implementar o diálogo de consentimento (texto informando armazenamento e exibição para outros usuários, botões Aceitar e Recusar) e o aviso "Novo item adicionado ao catálogo" para objetos, e verificar os quatro fluxos: rosto aceito, rosto recusado, objeto inserido e scan com 90% ou mais
- [x] 5.6 Implementar a tela de remoção (lista de itens de scan com miniatura e nome, confirmação, sem itens de seed), e verificar removendo e cancelando a remoção de um item
- [x] 5.7 Garantir que os frames e vetores de scans não inseridos não são gravados em disco, e verificar que `data/` não muda depois de um scan descartado ou recusado
- [x] 5.8 Documentar no `README.md` a instalação, o comando `preparar`, a calibração e o uso do aplicativo, e verificar seguindo o passo a passo em um ambiente limpo

## 6. Verificação integrada

- [x] 6.1 Rodar o fluxo completo de ponta a ponta (preparar, seed, calibrar, escanear um objeto novo, escanear o mesmo objeto de novo, escanear um rosto e aceitar, escanear um rosto e recusar, remover o item) e verificar que cada passo se comporta como as specs descrevem
- [x] 6.2 Rodar `openspec validate scanner-similaridade-visual --strict` e verificar que passa sem erros

## 7. Adição manual de imagens

- [x] 7.1 Implementar no motor a adição de arquivos de imagem como um único item (pipeline do seed por arquivo, todas as válidas guardadas via `inserir_scan`, índice atualizado, ignoradas com motivo, sem regra dos 90% nem consentimento), e verificar com testes: imagens válidas, uma inválida e um arquivo ilegível, nenhuma válida (nada gravado em `data/`), imagens repetidas de um item existente e imagem com rosto
- [x] 7.2 Implementar na tela de espera o botão "Adicionar imagens" (seletor de arquivos com seleção múltipla, processamento no worker com indicador, mensagem com adicionadas e ignoradas, disponível sem câmera), e verificar com testes da interface a adição, a falha sem imagens válidas, o seletor cancelado e o botão habilitado sem câmera
- [x] 7.3 Documentar a adição de imagens no `README.md` e rodar `openspec validate scanner-similaridade-visual --strict`

## Workflow follow-up

- Arquivar a change com `/opsx:archive` depois que a implementação for revisada.

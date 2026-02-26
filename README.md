# Ecommerce MLOps & GenAI Pipeline


[![Powered by Kedro](https://img.shields.io/badge/Powered_by-Kedro-ffc900?logo=Kedro)](https://kedro.org)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue?logo=Python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-blue?logo=Docker)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Docker-green?logo=Postgresql)](https://www.postgresql.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Docker-green?logo=Ollama)](https://ollama.com/)
[![Streamlit UI](https://img.shields.io/badge/Streamlit-Docker-green?logo=Streamlit)](https://docs.streamlit.io/)

[![Ollama](https://img.shields.io/badge/theLook_eCommerce-dataset-blue?logo=GoogleCloud)](https://console.cloud.google.com/marketplace/product/bigquery-public-data/thelook-ecommerce?project=bigquery-484420)


[![CI](https://github.com/Rafael-soares-oliveira/ecommerce_mlops_genai_pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Rafael-soares-oliveira/ecommerce_mlops_genai_pipeline/actions/workflows/ci.yml)
![Coverage](./coverage.svg)

<br>

## 1. Objetivo do Projeto

O objetivo primário desta arquitetura é fornecer uma plataforma analítica end-to-end altamente eficiente, projetada para operar em cenários de baixo recurso e com baixo/médio volume de dados, mas com máxima performance, robustez e precisão.

O sistema orquestra a ingestão e transformação de arquivos Parquet em tabelas relacionais de métricas de negócio, vetoriza metadados para busca semântica e disponibiliza uma interface interativa via Streamlit. Através de um Agente RAG (Retrieval-Augmented Generation), o usuário pode fazer perguntas em linguagem natural, que são convertidas em consultas SQL validadas. A orquestração da inteligência e a conexão com o banco de dados ocorrem de forma nativa e persistente na própria camada de interface (Streamlit), garantindo processamento com Zero-Copy via Apache Arrow, eliminando overheads de rede e serialização complexa.

<br>

## 2. Arquitetura do Sistema

O fluxo de dados abaixo descreve a topologia dos containers Docker e o ciclo de vida dos dados, divididos entre o processamento em Batch (ETL) e a Inferência em Tempo Real (RAG e UI Interativa Unificada).

```mermaid
graph LR
    %% Estilização
    classDef infra fill:#2d3436,stroke:#dfe6e9,color:#fff
    classDef kedro fill:#6c5ce7,stroke:#a29bfe,color:#fff
    classDef db fill:#00b894,stroke:#55efc4,color:#fff
    classDef rag fill:#e17055,stroke:#fab1a0,color:#fff
    classDef ui fill:#d63031,stroke:#ff7675,color:#fff
    classDef viz fill:#fdcb6e,stroke:#e17055,color:#000
    classDef cron fill:#b2bec3,stroke:#636e72,color:#000

    subgraph Docker_Host ["Docker Host"]
        direction LR
        
        CRON(("⏰ Cron")):::cron

        subgraph UI_Container ["💻 Streamlit UI (Unificado)"]
            direction TB
            INPUT[/Pergunta do Usuário/]:::ui
            S_TRANS["🧠 Sentence-Transformers<br/>(Cache Local)"]:::rag
            ROUTER{{"Lógica RAG &<br/>Text-to-SQL"}}:::rag
            IBIS{"Ibis<br/>(Validador & Arrow)"}:::rag
            DASH["📊 Dashboard Dinâmico"]:::ui
        end

        subgraph RAG_Engine ["🧠 Ollama"]
            LLM["DeepSeek-r1:1.5b"]:::rag
        end

        subgraph Postgres_Container ["🗄️ PostgreSQL 18"]
            PG_ALL[("Schemas:<br/>raw_data<br/>metrics<br/>embeddings")]:::db
        end

        subgraph Kedro_Group ["⚙️ Profile: ETL (Efêmero)"]
            K_WORKER["Kedro Worker"]:::kedro
        end

        subgraph Kedro_Viz ["🔍 Profile: Debug"]
            K_VIZ["Kedro Viz"]:::viz
        end
    end

    %% Fluxos ETL (Batch)
    CRON -. "Dispara" .-> K_WORKER
    K_WORKER -- "Processa e Vetoriza" --> PG_ALL
    K_WORKER -. "Lê Metadata" .-> K_VIZ

    %% Fluxos RAG & UI (Real-time)
    INPUT --> S_TRANS
    S_TRANS -- "Busca Similaridade" --> PG_ALL
    S_TRANS --> ROUTER
    ROUTER -- "Envia Contexto e Pede SQL" --> LLM
    LLM -- "Retorna SQL" --> ROUTER
    ROUTER --> IBIS
    IBIS -- "Executa Query" --> PG_ALL
    PG_ALL -- "Retorna PyArrow" --> IBIS
    IBIS --> DASH
```


## 2.1. Detalhamento dos Componentes

### Infraestrutura e Pipeline Batch (ETL)
* ⏰ **Cron**: Agendador local responsável por disparar o script de orquestração (`run_job.sh`) em janelas de tempo pré-definidas para ingestão incremental.
* ⚙️ **Kedro Worker (Ibis + DuckDB)**: Container efêmero que encapsula a lógica de extração e transformação. Utiliza a engine do DuckDB via Ibis para processar os arquivos Parquet de forma vetorizada, mitigando o alto consumo de RAM. Após a execução, o container é encerrado, liberando recursos do Host.
* 🧠 **Sentence-Transfomers**: Etapa do pipeline responsável por ler o dicionário de dados e metadados estruturados, convertendo-os em representações vetoriais (embeddings) para carga no banco.
* 🔍 **Kedro Viz**: Serviço de documentação visual sob demanda. Lê os metadados gerados pelo Kedro Worker para exibir o grafo de dependências e a linhagem dos dados (*Data Lineage*). Só consome recursos quanto ativado manualmente.

### Camada de Persistência
* 🗄️ **PostgreSQL 18 (Tuned)**: Banco de dados relacional e vetorial tunado para alta performance analítica. Segmentado logicamente em schema (`raw_data`, `metrics`, `embeddings`), utiliza a extensão `pgvector` para buscas semânticas.

### Motor RAG e Inferência (Tempo Real)
* 💻 **Streamlit UI (Motor Unificado)**: Ponto central de contato e orquestração.
	* **Interface e Dashboard**: Captura a pergunta em linguagem natural e renderiza os DataFrames e gráficos dinâmicos.
	* **Sentence-Transformers (Real-time)**: Gera o *embedding* da pergunta do usuário localmente (via CPU) para consulta ao banco.
	* **Roteador & Text-to-SQL**: Lógica embutida no backend do Streamlit que envia o contexto (esquema do banco recuperado) para o motor SLM e recebe a consulta SQL estruturada.
	* **Ibis (Executor e Validador)**: Mantém uma conexão persistente (via `@st.cache_resource`) com o PostgreSQL. Executa o SQL gerado pelo RAG, valida a sintaxe e retorna os dados nativamente no formato **Apache Arrow**, evitando custos de conversão JSON.
* 🧠 **Ollama (Motor de Inferência SLM)**: Serviço isolado que hospeda o modelo na GPU. Atua estritamente como um gerador de texto a partir dos prompts estruturados enviados pelo Streamlit.

## 2.2. Tech Stack

* **Gerenciamento**:
	* [**UV**](https://docs.astral.sh/uv/): É um gerenciado de pacotes e instalador para Python extremamente rápido, escrito em Rust, projetado para substituir ferramentas como `pip`, `pip-tools` e `poetry` em um único executário.
* **Orquestração**:
	* [**Kedro**]([https://docs.kedro.org/en/stable/](https://docs.kedro.org/en/stable/getting-started/course/)): É um framework Python de código aberto que aplica princípios de engenharia de software - como modularidade, separação de conceitos e versionamento - à criação de pipelines de dados reproduzíveis e sustentáveis.
	* [**Kedro-Viz**](https://docs.kedro.org/projects/kedro-viz/en/stable/): É uma ferramenta de visualização interativa que renderiza graficamente o Grafo Acíclico Direcionado (DAG) do seu projeto, permitindo rastrear a linhagem dos dados e a estrutura das tarefas.
	* [**Kedro-Datasets**](https://docs.kedro.org/projects/kedro-datasets/en/kedro-datasets-9.2.0/): É um biblioteca de conectores curados que facilita a leitura e escrita de dados em diversos formatos (como CSV, Parquet e SQL) e sistemas de armazenamento (S3, Azure Blob, GCS) através de uma interface de configuração abstrata.
* **Processamento**:
	* [**Ibis**](https://ibis-project.org/): É um framework Python que oferece uma interface unificada e tipada para escrever consultas SQL complexas que podem ser executadas em múltiplos backends (como DuckDB e PostgreSQL) sem alterar o código.
	* [**PyArrow**](https://arrow.apache.org/docs/python/): É a implementação em Python do Apache Arrow que fornece uma camada de memória coluna de alto desempenho para processamento e intercâmbio eficiente de grandes conjuntos de dados.
* **Qualidade do Código**:
	* [**Ruff**](https://docs.astral.sh/ruff/): É um *linter* e formatador de código Python extremamente rápido, escrito em Rust, que substitui dezenas de ferramentas tradicionais (como *Flake8* e *Black*) com performance superior.
	* [**Ty**](https://docs.astral.sh/ty/#highlights): É um framework focado em **Type-Drive Development**, que simplifica a definição de tipos estáticos e validações em Python para aumentar a robustez do código.
	* [**Pytest**](https://docs.pytest.org/en/stable/): O framework de testes padrão da indústria que facilita a escrita de testes unitários e de integração simples, escaláveis e altamente legíveis.
* **Banco de Dados**:
	* [**PostgreSQL**](https://www.postgresql.org/docs/): Banco de dados relacional de código aberto mais avançado do mundo, servindo como uma base extensível, confiável e robusto para qualquer tipo de carga de trabalho de dados.
		* [**vchord (TensorChord)**](https://hub.docker.com/r/tensorchord/vchord-postgres): Um imagem Docker otimizada que combina o PostgreSQL com a extensão **pgvector**, focada em fornecer uma infraestrutura de alto desempenho para armazenamento e busca vetorial em aplicações de IA.
		* [**PostGIS**](https://postgis.net/documentation/): Uma extensão espacial poderosa que adiciona suporte a objetos geográficos ao PostgreSQL, permitindo a execução de consultas de localização, mapeamento e análise geométrica complexa.
		* [**TimescaleDB**](https://github.com/timescale/timescaledb?tab=readme-ov-file): Uma extensão que transforma o PostgreSQL em um banco de dados de séries temporais, utilizando "*hypertables*" para garantir ingestão rápida e consultas analíticas eficientes em dados temporais massivos.
	* [**DuckDB**](https://duckdb.org/docs/stable/clients/python/overview): Um sistema de gerenciamento de banco de dados OLAP analítico e embutido (*in-process*), otimizado para consultas SQL extremamente rápidas em arquivos locais ou memória.
	* [**ADBC (Arrow Database Connectivity)**](https://arrow.apache.org/adbc/current/index.html): 
* **Modelos IA**:
	* [**Sentence-Transformers**](https://huggingface.co/sentence-transformers): Uma biblioteca para gerar *embeddings* de texto de última geração, permitindo converter frases em vetores densos para busca semântica e RAG.
		* [**all_MiniLM-L6-v2**](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2): É um modelo de *sentence embedding* extremamente leve e eficiente, ideal para converter textos em vetores densos de 384 dimensões em tarefas de busca semântica e RAG com baixo custo computacional.
	* [**Ollama**](https://docs.ollama.com/): 
		* [**qwen2.5-coder:1.5b**](): É um modelo de linguagem compacto e especializado em programação, treinado pela Alibaba para oferecer alta performance em geração de código e raciocínio lógico, sendo perfeito para execução local via Ollama.

<br>

## 3. Escolhas Tecnológicas e Justificativas Arquiteturais

A stack foi selecionada sob a premissa de **"foco absoluto em eficiência, baixo volume de dados e otimização de VRAM/RAM"**.
* **Arquitetura Unificada (Streamlit + Ibis)**: A decisão de remover uma camada intermediária de API (como FastAPI/gRPC) e rodar o Ibis diretamente no processo persistente do Streamlit reduz o footprint de memória e elimina a latência de rede interna. O transporte de dados via PyArrow entre o banco e a interface ocorre com eficiência máxima (_Zero-Copy_).
- **Ollama (`OLLAMA_KEEP_ALIVE=5m`)**: Para proteger uma limitada VRAM e evitar travamentos no sistema operacional do Host, o Ollama foi configurado para descarregar o modelo SLM da memória da placa de vídeo após apenas 5 minutos de inatividade (_idle_). O modelo só ocupa VRAM quando ativamente consultado.
- **Limitação de Recursos no Docker (Deploy Limits)**: Cada serviço no `docker-compose.yml` possui limites rígidos de RAM. Isso garante que o sistema do Host tenha fôlego de sobra para o SO e operações de disco, prevenindo _Out of Memory (OOM) kills_.
- **PostgreSQL 18 Tunado (Timescale + pgvector)**: A imagem Docker base foi customizada.
    - A memória `maintenance_work_mem` foi ajustada para suportar a criação de índices HNSW sem estourar a memória do container.
    - O `jit` foi desabilitado, pois em consultas vetorizadas rápidas (típicas de RAG), a compilação _Just-in-Time_ adiciona latência desnecessária.
- **Kedro Worker Efêmero e Profiles Docker**: Ferramentas de engenharia e observabilidade (Kedro e Kedro-Viz) não rodam continuamente. O uso de `profiles` no Docker Compose assegura que esses containers só consumam RAM e CPU durante as janelas de processamento batch (ETL) ou depuração.
- **Cache de Modelos no Docker Build (UV)**: O `Dockerfile.app` utiliza o gerenciador de pacotes `uv` e a montagem de cache (`--mount=type=cache`) para baixar o modelo `Sentence-Transformer` durante o _build_. Isso isola o ambiente e garante inicializações instantâneas.

<br>

## 4. Pipeline de Dados: Passo a Passo e Decisões de Engenharia

O projeto é dividido em dois ciclos operacionais distintos: o processamento em Batch (ETL) e a inferência em tempo real.

### Fase 1: Ingestão e Preparação Batch (Execução Efêmera)

1. **Extração e Transformação Ibis/DuckDB**: O Kedro executa transformações usando o Ibis, que delega o processamento para o DuckDB. Isso garante velocidade vetorizada na leitura dos arquivos de origem (Parquet) sem consumir RAM excessiva, substituindo as operações custosas do Pandas.
2. **Carga no PostgreSQL via Custom Dataset (Ibis Upsert)**: O Kedro não possui um conector robusto para realizar operações de UPSERT nativas via Ibis no PostgreSQL. O desenvolvimento de um Custom Dataset garante que os dados em `raw_data` e as métricas geradas sejam inseridos de forma **idempotente**. Execuções repetidas do `run_job.sh` não duplicarão os registros.
3. **Vetorização (Sentence-Transformers)**: Após a criação das métricas, os metadados (esquemas, descrições, dicionários de dados) são passados pelo cache do modelo local (configurado no `.env` via `HF_HOME`) e salvos no schema `embeddings` via `pgvector`.

### Fase 2: Motor Analítico RAG

1. **Input do Usuário**: O usuário envia uma pergunta na interface do Streamlit.
2. **Vetorização Local**: O próprio backend persistente do Streamlit gera o _embedding_ da pergunta usando CPU.
3. **Busca Semântica (Hybrid Search)**: O Streamlit, através de sua conexão persistente do Ibis, aciona o banco para realizar uma busca nos `embeddings`, utilizando recursos avançados (como `pg_trgm` ou índices dedicados), recuperando as tabelas e colunas com maior relevância.
4. **Prompt Roteador (Text-to-SQL)**: O contexto recuperado é formatado e enviado ao serviço do Ollama, que atua apenas como motor de inferência, retornando a query SQL gerada.
5. **Loop de Validação Automática**: O Streamlit tenta compilar a query recebida via Ibis. Se ocorrer erro de sintaxe ou mapeamento incorreto (ex: coluna alucinada pelo SLM), o erro é capturado pela aplicação e enviado de volta ao Ollama para correção (Self-Correction), protegendo a interface de quebras.
6. **Entrega e Visualização**: Com a query validada, o Ibis executa a consulta no PostgreSQL. Os resultados trafegam de volta para o Streamlit em formato binário **PyArrow**, garantindo máxima velocidade de carregamento para a renderização do Dashboard.

<br>

## 5. Engenharia de Dados: Orquestração e Padrões com Kedro

A camada de preparação de dados foi arquitetada sobre o framework **Kedro**, operando de forma efêmera e contêinerizada. Para garantir que o pipeline respeite as premissas de baixo consumo de recursos e alta performance, o comportamento padrão do Kedro foi estendido através de Hooks customizados e Custom Dataset do Kedro-datasets.

## 5.1. Observabilidade e Monitoramento de Recursos (Hooks e Logging)

Em ambientes contêinerizados com limites estritos de memória, vazamentos (*memory leaks*) na etapa de ETL podem derrubar o *Docker Host*. Para mitigar isso, implementamos:
* **Logging Estruturado (`logging.yml`)**: Separação clara entre logs informativos e de erro, com rotatividade automática (`RotatingFileHandler` com backup limitado). Evita o inchaço do armazenamento local.
* **`ResourceMonitoringHook`**: Um hook injetado no ciclo de vida do Kedro que atua como um inspetor de recursos.
	* Utiliza a biblioteca `psutil` para capturar a memória RAM exata (*RSS*) antes e depois da execução de cada *Node*.
	* Mede o delta de memória e o tempo de execução (em segundos).
	* Dispara *flags* de alerta (`HIGH MEMORY`) no log caso um nó ultrapasse o limite seguro estipulado no `parameters.yml`. Isso permite identificar imediatamente transformações não-otimizadas.

## 5.2. Otimização de Banco de Dados via Ciclo de Vida `CreateIndexesHook`

A manipulação de dados em massa (Bulk Load) em tabelas que possuem índices complexos — especialmente os índices vetoriais `HNSW` do *pgvector* — sofre de grave degradação de performance.
Para resolver isso, o `CreateIndexesHook` altera o fluxo padrão de DDL (Data Definition Language):
1. `before_pipeline_run`: Conecta ao PostgreSQL e executa os scripts DDL iniciais para garantir que as tabelas do schema `raw_data` existam (sem índices).
2. `after_pipeline_run`: Apenas após toda a carga de dados ser finalizada, o hook executa a criação dos índices (B-Tree para métricas e HNSW para vetores). Criar índices sobre tabelas já populadas é mais rápido e eficiente do que atualizar o índice linha a linha durante o *Insert*.

## 5.3. Ingestão de Alta Performance `IbisUpsertDataset`

O gargalo de qualquer pipeline ETL moderno é a etapa de escrita no banco de dados. O Kedro nativo não oferece suporte eficiente para operações idempotentes de `UPSERT` usando Ibis. A classe `IbisUpsertDataset` foi criada combinando o padrão *Factory* com serialização em baixo nível.
Como funciona:
1. **Zero-Copy e Arrow**: Os dados transformados pelo DuckDB são mantidos em `PyArrow`.
2. **Protocolo Binário (`pgpq`)**: O dataset utiliza a biblioteca `pgpq` para codificar os dados do Arrow diretamente para o formato binário nativo do PostgreSQL, evitando a geração custosa de strings `INSERT INTO`.
3. **Carga em Memória (COPY)**: Usa a instrução `COPY FROM STDIN WITH (FORMAT BINARY)` para carregar os dados em uma tabela temporária quase instantaneamente.
4. **Merge Inteligente (Upsert)**: Compara a tabela temporária com a tabela final, gerando dinamicamente um `ON CONFLICT DO UPDATE` que só sobrescreve o dado se houver diferença real (`IS DISTINCT FROM`). Isso reduz o I/O de disco e o inchaço do *Write-Ahead Log* (WAL).

## 5.4. Catálogo Dinâmico e DRY `catalog.yml`

O Catálogo de Dados foi desenhado seguindo o princípio *DRY* (*Don't Repeat Yourself*).
* **Padrões Dinâmicos (`{table}`)**: A sintaxe de fábrica (ex:`raw_{table}`) mapeia automaticamente qualquer arquivo `.parquet` na camada `01_raw` através da engine do DuckDB, eliminando mapeamentos manuais extensivos.
* **YAML Anchors**: Configurações repetitivas (credenciais, uso da classe `IbisUpsertDataset`) são encapsuladas no *anchor* `&postgres_upsert_base`. Adicionar uma nova entidade exige apenas referenciar a base e definir o `table_name`.

## 5.5. Pipeline de Processamento e Qualidade de Dados (`data_processing`)

O pipeline de extração e transformação (`data_processing`) atua como a barreira de qualidade. Utiliza o **Ibis** para delegar a computação pesada ao DuckDB e ao PostgreSQL de forma vetorizada.

### A. Validação de Qualidade em Passagem Única (Single-Pass Validation)

* `schema_rules.py`: Define contratos estritos de dados (regras de linha e estruturais).
* `_validate_ibis_table`: Em vez de loops de validação custosos, compila todas as regras em um **único bloco de agregações Ibis**. Executa a query no banco/engine, abortando o pipeline com um `ValueError` detalhando caso qualquer regra retorne uma violação (`> 0`). Garante a política "Lixo não entra".

### B. Proteção de Integridade Referencial Dinâmica (Cross-Engine Joins)

Para evitar quebras de pipeline por erros de chave estrangeira (FK), durante o `INSERT`:
1. IDs validados do PostgreSQL são convertidos em `PyArrow` e carregados como `ibis.memtable` (tabela virtual em memória).
2. Realiza-se um Cross-Engine Join entre a origem (DuckDB/Parquet) e as FKs validadas:
	* **Anti-Join**: Identifica e registra nos logs (como *warnings*) os registros órfãos.
	* **Semi-Join**: Filtra a base original, enviando para o Upsert apenas as linhas com correspondência válida no banco destino.

### C. Estratégias de Carga Incremental

Para manter a carga leve:
* **Watermarking**: Tabelas de log (ex: `inventory_items`)consultam o destino para a data máxima inserida (`max(created_at)`), processando apenas registros novos.
* **Moving Window**: Tabelas transacionais mutáveis (`orders` e `order_items`), usam um `lookback` configurável em dias, atualizando apenas pedidos recentes e ignorando históricos estáticos.

### D. Imutabilidade e Consistência Funcional

A lógica de transformação de negócio em `transform_tables.py` segue programação funcional (recebe `ibis.Table`, retorna `ibis.Table`).
Para injetar as validações sem poluir a execução do Kedro, o utilitário `create_node_func` (`functools.partial`) aplica os contratos de esquema de forma transparente, garantindo que a observabilidade no `kedro-viz` e nos logs reflita as operações reais.

## 5.6 Pipeline de Busca Semântica e Geo-Vetorização (`data_embeddings`)

Esta camada é responsável por transformar dados estruturados em representações vetoriais (embeddings) e espaciais (PostGIS), permitindo que o Agente RAG realize buscas semânticas e análises geográficas complexas.

### A. Arquitetura de Inferência "Zero-Copy" com Polars

Diferente do pipeline de ETL tradicional, a geração de embeddings exige alta densidade de processamento em memória. Implementamos um fluxo otimizado:
1. **Extração via Arrow**: O Ibis extrai os dados do PostgreSQL/DuckDB diretamente para memória no formato Apache Arrow.
2. **Materialização em Polars**: O dado é convertido para um DataFrame Polars sem cópia de memória desnecessária.
3. **Inferência Batch**: Utilizamos o `SentenceTransformer` para processar a coluna `chunk_text` em lotes (batch size: 256), aproveitando a paralelização de CPU/GPU.
4. **Tipagem de Vetores**: O resultado é injetado como um `pl.Array(pl.Float32, 384)`, garantindo compatibilidade binária exata com o `pgvector`.

### B. Enriquecimento de Contexto Semântico (Chunks)

Os nós de preparação (`prepare_nodes`) consolidam metadados espalhados em uma única string descritiva, otimizando a capacidade de recuperação do modelo:
* **Produtos** Combina Nome, Marca, Categoria e Preço em uma narrativa técnica.
* **Usuários (Logística Semântica)**: Realiza um join em tempo de execução para calcular o ticket médio por usuário e consolidar sua localização geográfica em uma descrição textual.

### C. Ingestão de Alta Performance com ADBC (`PolarsVectorADBCDataset`)

Para superar as limitações de latência do SQLAlchemy ao lidar com tipos complexos (`vector` e `geography`), desenvolvemos um dataset customizado baseado no driver **ADBC (Arrow Database Connectivity)**:
1. **Staging Table**: O Polars descarrega o DataFrame em uma tabela temporária via protocolo binário Arrow.
2. **Casting Dinâmico**: O dataset executa uma transação SQL que realiza o cast das strings para o formato `vector` (pgvector) e converte coordenadas `lat/long` no tipo `geography` do PostGIS de forma nativa.
3. **Atomicidade**: Todo o processo de carga da staging para a produção ocorre dentro de uma transação única, garantindo a integridade dos dados mesmo em falhas.

### D. Operações Geoespaciais (PostGIS & H3)

Além dos vetores, o pipeline orquestra scripts SQL via `PostGISScriptsDataset` para:
* **Map Hotspots (H3)***: Agregação de densidade de usuário utilizando indexação hierárquica hexagonal H3.
* **User Logistics**: Cálculo de matrizes de distância entre centros de distribuição e usuários finais para métricas de eficiência logística.


## Estrutura do Repositório

``` plaintext
.
├── conf # Configurações do Kedro
│   ├── base/                     # Configurações padrão e compartilhadas
│   │   ├── catalog.yml           # Data Catalog
│   │   ├── globals.yml           # Parâmetros compartilhados entre YML
│   │   └── parameters.yml        # Parâmetros dos pipelines
│
│   ├── local/                    # Sobrescrições locais e credenciais (ignorado no git)
│   ├── logging.yml               # Configuração do Logger
│   └── README.md                 # Documentação dos arquivos de configuração
│
├── data/                         # Armazenamento local particionado pelas camadas do Kedro
│   ├── 01_raw/                   # Dados brutos e imutáveis
│   ├── 02_intermediate/          # Dados limpos e tipados
│   ├── 03_primary/               # Dados padronizados para o modelo de domínio
│   ├── 04_feature/               # Features de machine learning
│   ├── 05_model_input/           # Matrizes e tensores para treinamento
│   ├── 06_models/                # Modelos serializados
│   ├── 07_model_output/          # Inferências e predições
│   └── 08_reporting/             # Dados agregados para visualização
│
├── junit/                        # Relatórios de testes exportados pelo Pytest/GitHub Actions
├── logs/                         # Arquivos de log locais
├── notebooks/                    # Rascunhos e experimentações (ignora no git)
├── pyproject.toml                # Configurações do projeto e ferramentas
├── README.md                     # Este arquivo
├── sql/                          # Scripts e queries SQL
│   ├── embeddings/               # Scripts para criação e indexação de tabelas de vetores
│   ├── init.sql                  # Script de inicialização do banco de dados (junto com o Docker)
│   ├── metrics/                  # Scripts para criação e indexação de tabela de métricas
│   └── raw_data/                 # Scripts para criação e indexação de tabelas pós-tratamento
│
├── src/
│   └── thelook_ecommerce_analysis/
│       ├── datasets/             # Implementação de datasets customizados
│       ├── hooks.py              # Hooks de execução do Kedro
│       ├── pipeline_registry.py  # Registro central dos pipelines disponíveis
│       ├── settings.py           # Configurações globais de execução do Kedro
│       ├── utils/                # Funções utilitárias
│       └── pipelines             # Pipelines de dados
│           ├── data_processing   # Extração, transformação e carga inicial
│           └── data_embeddings   # Criação de tabelas de vetores para auxílio do RAG
│
├── tests/                        # Testes unitários espelhando a estrutura do src/
│   ├── datasets/                 # Testes dos custom datasets
│   ├── kedro_settings            # Testes das configurações do Kedro
│   ├── pipelines                 # Testes das lógicas dos pipelines e nodes
│   └── utils                     # Teste das funções utilitárias
│
├── docker-compose.yml            # Definição dos serviços
├── Dockerfile                    # Imagem do banco de dados PostgreSQL
├── Dockerfile.app                # Imagem da aplicação Kedro
├── start.sh                      # Script para iniciar serviços de infra
├── run_job.sh                    # Instancia o container efêmero do Kedro para execução
├── down.sh                       # Encerra serviços e limpa volumes
└── uv.lock                       # Lockfile de dependências gerenciado pelo UV
```

## Como Executar

### Pré-requisitos

- [Docker Engine](https://docs.docker.com/engine/install) (Pode ser configurado para [Podman](https://podman.io/docs/installation))
- GPU Nvidia (mudar configuração para outras GPUs) / CPU também disponível, porém mais lento

1. **Clone o repositório**:

```
git clone https://github.com/Rafael-soares-oliveira/ecommerce_mlops_genai_pipeline
cd ecommerce_mlops_genai_pipeline
```

2. **Configure o ambiente**: Crie uma cópia do arquivo de variáveis de ambiente.
```
cp .env.example .env
```

3. **Inicie a infraestrutura base**: Este script levanta o banco de dados e o servidor Ollama, detectando automaticamente o uso de GPU.
```
bash start.sh
```

4. **Execute o pipeline de dados (ETL)**: Dispara o container efêmero do Kedro para ingestão, transformação e geração de embeddings.
```
bash run_job.sh
```

5. **Acesse as interfaces**:
* **Streamlit (UI)**: `http://localhost:8501`
* **Kedro-Viz (Lineage)**: `http://localhost:4141`
* **pgAdmin**: `http://localhost:8080`

## Tabelas de Métricas

- **Métricas de Vendas e Receita**: Focada no desempenho financeiro.
  - **Tabelas Fonte**: `order_items`, `orders`, `products`.
  - **Métricas**:
    - **GMV (Gross Merchandise Value)**: Soma total do valor das vendas (`sale_price`).
    - **Ticket Médio (AOV)**: Média de gasto por pedido.
    - **Taxa de Cancelamento**: % de pedidos com status `Cancelled`.
- **Métricas de Clientes (CRM e Retenção)**: Focada no comportamento e valor do usuário ao longo do tempo.
  - **Tabelas Fonte**: `users`, `orders`.
  - **Métricas**:
    - **LTV (Lifetime Value)**: Valor total gasto por usuário desde o cadastro.
    - **Análise de Cohort**: Retenção de usuário agrupados pelo mês de aquisição (safra).
    - **RFM (Recência, Frequência, Monetário)**: Segmentação de clientes para marketing.
    - **Novos vs. Recorrentes**: Proporção de vendas de primeira compra vs. recompra.
- **Métricas de Produto e Estoque**: Focada na logística e atratividade do item.
  - **Tabelas Fonte**: `inventory_items`, `products`, `order_items`, `distribution_center`.
  - **Métricas**:
    - **Taxa de Devolução**: % de itens com status `Returned`.
    - **Tempo de Envio**: Diferença entre `created_at` e `shipped_at`.
    - **Margem de Produto**: Diferença entre `sale_price` e `cost`.
    - **Aging do Estoque**: Tempo que os itens ficam no inventário antes da venda.
- **Métricas de Navegação (Web Analytics)**: Focada no funil de conversão no site.
  - **Tabelas Fonte**: `events`.
  - **Métricas Possíveis**:
    - **Taxa de Conversão de Sessão**: Visitantes únicos que compram / Total de visitantes.
    - **Abandono de Carrinho**: Usuários que adicionam ao carrinho (`cart`) mas não compram (`purchase`).
    - **Origem de Tráfego**: Análise da coluna `traffic_source`.

## Roadmap de Implementação (Planejamento)

Este planejamento foca nas entregas lógicas, sem datas fixas.

### Fase 1: Fundação & Infraestrutura

- [X] Configurar repositório com `.gitignore` e `pyproject.toml`.
- [X] Criar `docker-compose.yml`, `Dockerfile` e scripts `sh`.
- [X] Configurar/Validar conexão com o Banco de Dados.

### Fase 2: Core Engineering (Kedro ETL)

- [X] Inicializar projeto Kedro (`kedro new`).
- [X] Configurar `crendentials.yml` e `parameters.yml`.
- [X] Configurar `conf/base/logging.yml` e configurar Hooks do Kedro.
- [X] Criar testes unitários para testar hooks.py e settings.py
- [X] Registrar datasets no `catalog.yml`.
- [X] Implementar **Pipeline de Transformação**:
  - [X] Limpeza com Ibis.
  - [X] Lógica de Watermark (Upsert) lendo do Postgres.
- [X] Criar testes com pelo menos 90% coverage
- [X] Configurar pipeline de CI (GitHub Actions) para rodar `ruff`, `ty`, `pytest` e gerar relatórios.
- [X] Documentar no README.md

### Fase 3: Métricas, Vetores e AI

- [X] Implementar **Pipeline de Embeddings**:
  - [X] Node para gerar vetores de descrições de produtos.
  - [X] Criar testes com pelo menos 90% coverage
  - [X] Documentar no README.md
- [ ] Implementar **Pipeline de Métricas**:
  - [ ] Node para criar tabelas de métricas
  - [ ] Criar testes com pelo menos 90% coverage
  - [ ] Documentar no README.md
- [ ] Implementar **Pipeline de SLM Batch**:
  - [ ] Configurar modelo e contexto
  - [ ] Node que agrega métricas diárias.
  - [ ] Integração com API do Ollama para gerar resumos textuais.

### Fase 4: Consumo e Visualização

- [ ] Configurar API REST.
- [ ] Configurar Streamlit.
- [ ] Cria dashboard modelo no Streamlit.
- [ ] Criar Dashboard no Streamlit.
- [ ] Implementar Chatbot RAG no Streamlit.

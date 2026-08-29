-- Registro: base própria do sistema (Spec §2), esquema `registro` num único
-- PostgreSQL compartilhado com o checkpointer do LangGraph (esquema separado,
-- gerenciado pela biblioteca — não definido aqui).
--
-- Decisões aplicadas:
--   D-001: o Registro é a fonte da verdade; a aprovação tácita é carimbo de
--          estado na rodada, sem leitura de volta da planilha.
--   Retenção: parâmetro pendente nº 9 — NULO. Nenhum TTL ou expurgo definido.
--   Imóveis excluídos não são guardados (Spec §2.1, decisão explícita).

CREATE SCHEMA IF NOT EXISTS registro;

-- Uma linha por execução (Spec §2.1 "rodada").
CREATE TABLE registro.rodada (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo                text NOT NULL CHECK (tipo IN ('decisao', 'acompanhamento')),
    inicio              timestamptz NOT NULL,
    fim                 timestamptz,
    estado              text CHECK (estado IN ('completa', 'degradada', 'abortada')),
    etapas              jsonb NOT NULL DEFAULT '{}'::jsonb,  -- situação de pronto por etapa
    motivo_degradacao   text,                                -- qual etapa falhou e por quê
    tentativas_por_etapa jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- D-001: aprovação tácita como carimbo; não há verificação de conteúdo.
    aprovada_em         timestamptz,
    modo_aprovacao      text CHECK (modo_aprovacao IN ('tacita', 'manual')),
    CONSTRAINT aprovacao_consistente CHECK ((aprovada_em IS NULL) = (modo_aprovacao IS NULL))
);

-- Cópia integral dos parâmetros vigentes na execução (Spec §2.1):
-- "sem ela, comparar duas semanas é comparar coisas diferentes sem saber".
CREATE TABLE registro.parametros_da_rodada (
    rodada_id   bigint PRIMARY KEY REFERENCES registro.rodada (id),
    parametros  jsonb NOT NULL
);

-- Padrões que o Analista encontrou na semana (Spec §2.1 "perfil_da_rodada").
CREATE TABLE registro.perfil_da_rodada (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rodada_id           bigint NOT NULL REFERENCES registro.rodada (id),
    dimensoes           jsonb NOT NULL,  -- uma ou duas por resultado (Spec §6.2: nunca as cinco)
    valores             jsonb NOT NULL,  -- faixa, região, quantidade — os valores de cada dimensão
    vendas_sustentam    integer NOT NULL CHECK (vendas_sustentam >= 0),
    classificacao       text NOT NULL CHECK (classificacao IN ('robusto', 'fragil'))
);
CREATE INDEX ON registro.perfil_da_rodada (rodada_id);

-- Uma linha por imóvel ESCOLHIDO, ~7 mil por rodada (Spec §2.1 "decisao_imovel").
CREATE TABLE registro.decisao_imovel (
    rodada_id           bigint NOT NULL REFERENCES registro.rodada (id),
    imovel_id           bigint NOT NULL,  -- identificador interno do Newcore
    nivel               text NOT NULL CHECK (nivel IN ('destaque', 'super_destaque')),
    posicao_ranking     integer NOT NULL CHECK (posicao_ranking >= 1),  -- dentro do nível
    nota_perfil         numeric NOT NULL,
    nota_desempenho     numeric NOT NULL,
    nota_gestor         numeric NOT NULL,
    pen_janela_anterior numeric NOT NULL DEFAULT 0,
    pen_sem_avaliacao   numeric NOT NULL DEFAULT 0,
    pen_sem_lead_180d   numeric NOT NULL DEFAULT 0,
    nota_final          numeric NOT NULL,
    perfil_id           bigint REFERENCES registro.perfil_da_rodada (id),  -- perfil que casou
    perfil_evidencia    integer,          -- nº de vendas que sustentam o perfil casado
    regra_relaxada      text CHECK (regra_relaxada IN
                            ('fotos', 'cadastro_completo', 'atualizacao_90d',
                             'gestor_produtivo', 'capacidade_distrito')),  -- NULL = entrou sem relaxamento
    PRIMARY KEY (rodada_id, imovel_id)
);
CREATE UNIQUE INDEX ON registro.decisao_imovel (rodada_id, nivel, posicao_ranking);

-- Uma linha por regra cedida em cada rodada (Spec §2.1 "relaxamento").
-- Invariante 7: só posições de destaque relaxam.
CREATE TABLE registro.relaxamento (
    rodada_id            bigint NOT NULL REFERENCES registro.rodada (id),
    regra_cedida         text NOT NULL CHECK (regra_cedida IN
                             ('fotos', 'cadastro_completo', 'atualizacao_90d',
                              'gestor_produtivo', 'capacidade_distrito')),
    posicoes_dependentes integer NOT NULL CHECK (posicoes_dependentes >= 0),
    posicoes_vazias      integer NOT NULL CHECK (posicoes_vazias >= 0),
    PRIMARY KEY (rodada_id, regra_cedida)
);

-- Histórico que alimenta a penalidade por janela (Spec §2.1 "janela_destaque").
-- Única entidade lida pelo Decisor durante a rodada (Spec §5).
CREATE TABLE registro.janela_destaque (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    imovel_id           bigint NOT NULL,
    nivel               text NOT NULL CHECK (nivel IN ('destaque', 'super_destaque')),
    inicio              date NOT NULL,
    fim                 date,             -- NULL = janela em curso
    leads_gerados       integer NOT NULL DEFAULT 0,
    semanas_consecutivas integer NOT NULL DEFAULT 1
);
CREATE INDEX ON registro.janela_destaque (imovel_id, inicio DESC);

-- O que a rodada de segunda apurou (Spec §2.1 "resultado_carga").
CREATE TABLE registro.resultado_carga (
    rodada_acompanhamento_id bigint NOT NULL REFERENCES registro.rodada (id),
    rodada_decisao_id        bigint NOT NULL REFERENCES registro.rodada (id),  -- carga de referência
    imovel_id                bigint NOT NULL,
    leads_gerados            integer NOT NULL DEFAULT 0,
    leads_sem_tratamento     integer NOT NULL DEFAULT 0,  -- sem atendimento E sem contato (Spec §4.2)
    PRIMARY KEY (rodada_acompanhamento_id, imovel_id)
);

-- Trilha de mudanças de parâmetro (Spec §2.1 "alteracao_parametro").
CREATE TABLE registro.alteracao_parametro (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parametro       text NOT NULL,
    valor_anterior  jsonb,
    valor_novo      jsonb,
    autor           text NOT NULL,
    data            timestamptz NOT NULL DEFAULT now()
);

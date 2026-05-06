from __future__ import annotations

import re
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_TSE_DIR = PROJECT_ROOT / "data" / "raw" / "tse_bvr_legal"
RAW_IBGE_DIR = PROJECT_ROOT / "data" / "raw" / "ibge"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "tse_bvr"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean" / "tse_bvr"
CLEAN_IBGE_DIR = PROJECT_ROOT / "data" / "clean" / "ibge"
IBGE_MUNICIPALITIES_PATH = CLEAN_IBGE_DIR / "ibge_municipalities.csv"
LOG_DIR = PROJECT_ROOT / "outputs" / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"

VALID_UFS = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


def ensure_directories() -> None:
    for path in [RAW_TSE_DIR, RAW_IBGE_DIR, INTERIM_DIR, CLEAN_DIR, CLEAN_IBGE_DIR, LOG_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def slugify_url(url: str) -> str:
    cleaned = re.sub(r"^https?://", "", url.strip())
    cleaned = cleaned.replace("/", "__")
    cleaned = cleaned.replace("?", "__q__")
    cleaned = cleaned.replace("=", "_")
    cleaned = cleaned.replace("&", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", cleaned)
    return cleaned


def normalize_name(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("'", " ")
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def zone_to_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


TSE_SOURCE_CATALOG = [
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/res/2008/resolucao-no-22-713-de-28-de-fevereiro-de-2008",
        "source_type": "legal_act",
        "title": "Resolucao no 22.713, de 28 de fevereiro de 2008",
        "issue_date": "2008-02-28",
        "treatment_reference_year": 2008,
        "annex_url": "",
        "notes": "Pilot election-use act for Colorado do Oeste, Fatima do Sul, and Sao Joao Batista.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2010/provimento-no-1-cge-de-2-de-fevereiro-de-2010",
        "source_type": "legal_act",
        "title": "Provimento no 1 - CGE, de 2 de fevereiro de 2010",
        "issue_date": "2010-02-02",
        "treatment_reference_year": 2010,
        "annex_url": "",
        "notes": "Third-stage 2010 biometric revision act. Annex text is exposed on the compiled page.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2010/provimento-no-7-cge-de-70-de-outubro-de-2010",
        "source_type": "legal_act",
        "title": "Provimento no 7 - CGE, de 27 de outubro de 2010",
        "issue_date": "2010-10-27",
        "treatment_reference_year": 2010,
        "annex_url": "",
        "notes": "Fourth-stage 2010 biometric revision act. The TSE slug contains a typo in the day field but resolves correctly.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/res/2010/resolucao-no-23-208-de-11-de-fevereiro-de-2010",
        "source_type": "legal_act",
        "title": "Resolucao no 23.208, de 11 de fevereiro de 2010",
        "issue_date": "2010-02-11",
        "treatment_reference_year": 2010,
        "annex_url": "",
        "notes": "Election-day biometric voting procedures for municipalities using biometrics in 2010.",
    },
    {
        "source_url": "https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/revisao-eleitoral",
        "source_type": "official_summary_page",
        "title": "Revisao eleitoral",
        "issue_date": "",
        "treatment_reference_year": 2012,
        "annex_url": "https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012",
        "notes": "Official TSE summary page with direct archive links for 2010 and 2012 municipality lists.",
    },
    {
        "source_url": "https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-cidades-onde-houve-votacao-em-urnas-com-leitor-biometrico-nas-eleicoes-2010",
        "source_type": "official_attachment",
        "title": "Lista de cidades onde houve votacao em urnas com leitor biometrico nas eleicoes de 2010",
        "issue_date": "",
        "treatment_reference_year": 2010,
        "annex_url": "",
        "notes": "Official TSE ZIP attachment containing an XLS with the 2010 election-use list.",
    },
    {
        "source_url": "https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012",
        "source_type": "official_attachment",
        "title": "Lista de localidades onde havera recadastramento biometrico em 2012",
        "issue_date": "",
        "treatment_reference_year": 2012,
        "annex_url": "",
        "notes": "Official TSE ZIP attachment containing an XLS with municipalities apt for biometric identification in 2012.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2011/Dezembro/tse-aprova-revisao-eleitoral-para-uso-da-biometria-em-mais-37-municipios",
        "source_type": "official_news",
        "title": "TSE aprova revisao eleitoral para uso da biometria em mais 37 municipios",
        "issue_date": "2011-12-02",
        "treatment_reference_year": 2012,
        "annex_url": "https://agencia.tse.gov.br/sadAdmAgencia/arquivoSearch.do?acao=getBin&arqId=1528991",
        "notes": "Official TSE news page stating the listed municipalities were being habilitated for the Eleicoes 2012; direct archive host is not resolvable from this environment.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2013/Marco/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014",
        "source_type": "official_news",
        "title": "Eleitores de todos os Estados serao identificados pela biometria nas eleicoes de 2014",
        "issue_date": "2013-03-04",
        "treatment_reference_year": 2014,
        "annex_url": "https://www.justicaeleitoral.jus.br/arquivos/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014",
        "notes": "Official TSE article explicitly tying the archived municipality list to the 2014 election cycle.",
    },
    {
        "source_url": "https://www.justicaeleitoral.jus.br/arquivos/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014",
        "source_type": "official_attachment",
        "title": "Programa de Identificacao Biometrica 2013-2014",
        "issue_date": "2013-03-04",
        "treatment_reference_year": 2014,
        "annex_url": "",
        "notes": "Official TSE PDF attachment listing municipalities targeted for biometric identification in 2014.",
    },
    {
        "source_url": "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2014.zip",
        "source_type": "official_open_data",
        "title": "Perfil do eleitorado 2014",
        "issue_date": "",
        "treatment_reference_year": 2014,
        "annex_url": "",
        "notes": "Official TSE election-year electorate file used as an administrative backstop for the 2014 biometric municipality benchmark.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2012/provimento-no-12-cge-de-3-de-outubro-de-2012",
        "source_type": "legal_act",
        "title": "Provimento no 12 - CGE, de 3 de outubro de 2012",
        "issue_date": "2012-10-03",
        "treatment_reference_year": 2012,
        "annex_url": "http://sintse.tse.jus.br/documentos/2012/Out/5/diario-da-justica-eletronico-tse/provimento-no-12-de-3-de-outubro-de-2012-torna",
        "notes": "Legal act for 2012 revision. Annex link is identified but returns 403 to requests and Playwright in this environment.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2012/provimento-no-15-cge-de-12-de-dezembro-de-2012",
        "source_type": "legal_act",
        "title": "Provimento no 15 - CGE, de 12 de dezembro de 2012",
        "issue_date": "2012-12-12",
        "treatment_reference_year": 2014,
        "annex_url": "http://sintse.tse.jus.br/documentos/2012/Dez/17/diario-da-justica-eletronico-tse/provimento-no-15-de-12-de-dezembro-de-2012-torna",
        "notes": "Legal act for 2013-2014 revision cycle. Annex link identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2012/provimento-no-25-cge-de-20-de-dezembro-de-2012",
        "source_type": "legal_act",
        "title": "Provimento no 25 - CGE, de 20 de dezembro de 2012",
        "issue_date": "2012-12-20",
        "treatment_reference_year": 2014,
        "annex_url": "http://sintse.tse.jus.br/documentos/2012/Dez/24/diario-da-justica-eletronico-tse/provimento-no-25-de-24-de-dezembro-de-2012-torna#page=2",
        "notes": "Complementary 2013-2014 revision act. Annex link identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2015/provimento-no-3-cge-de-25-de-marco-de-2015",
        "source_type": "legal_act",
        "title": "Provimento no 3 - CGE, de 25 de marco de 2015",
        "issue_date": "2015-03-25",
        "treatment_reference_year": 2016,
        "annex_url": "http://sintse.tse.jus.br/documentos/2015/Abr/16/diario-da-justica-eletronico-tse/republicacao-provimento-no-3-de-25-de-marco-de#page=2",
        "notes": "Base act for the 2015-2016 project. Annex identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2015/provimento-no-5-cge-de-9-de-abril-de-2015",
        "source_type": "legal_act",
        "title": "Provimento no 5 - CGE, de 9 de abril de 2015",
        "issue_date": "2015-04-09",
        "treatment_reference_year": 2016,
        "annex_url": "http://sintse.tse.jus.br/documentos/2015/Abr/23/diario-da-justica-eletronico-tse/republicacao-provimento-no-5-de-9-de-abril-de-2015",
        "notes": "Complementary act for the 2015-2016 project. Annex identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2016/provimento-no-10-cge-de-27-de-junho-de-2016",
        "source_type": "legal_act",
        "title": "Provimento no 10 - CGE, de 27 de junho de 2016",
        "issue_date": "2016-06-27",
        "treatment_reference_year": 2016,
        "annex_url": "http://sintse.tse.jus.br/documentos/2016/Jul/1/diario-da-justica-eletronico-tse/provimento-no-10-de-27-de-junho-de-2016-torna",
        "notes": "Amendment for the 2015-2016 project. Annex link identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2016/provimento-no-16-cge-de-6-de-dezembro-de-2016",
        "source_type": "legal_act",
        "title": "Provimento no 16 - CGE, de 6 de dezembro de 2016",
        "issue_date": "2016-12-06",
        "treatment_reference_year": 2018,
        "annex_url": "http://sintse.tse.jus.br/documentos/2016/Dez/9/diario-da-justica-eletronico-tse/provimento-no-16-de-6-de-dezembro-de-2016-torna-publica-relacao-de-localidades-a-serem-submetidas-a-revisao-de-eleitorado-com-coleta-de-dados-biometricos-pertinente-ao-programa-de-identificacao-biometrica-2017-2018#page=2",
        "notes": "Base act for the 2017-2018 program. Annex link identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/legislacao/compilada/prv-cge/2017/provimento-no-4-cge",
        "source_type": "legal_act",
        "title": "Provimento no 4 - CGE, de 23 de marco de 2017",
        "issue_date": "2017-03-23",
        "treatment_reference_year": 2018,
        "annex_url": "http://sintse.tse.jus.br/documentos/2017/Mar/24/diario-da-justica-eletronico-tse/provimento-no-4-de-23-de-marco-de-2017-torna-publica-relacao-de-localidades-a-serem-submetidas-a-revisao-de-eleitorado-com-coleta-de-dados-biometricos-pertinente-ao-programa-de-identificacao-biometrica-2017-2018-mediante-alteracao-do-anexo-do-provimento-cge-no-16-2016",
        "notes": "2017 amendment to the 2017-2018 program. Annex identified but blocked to programmatic access.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2016/Outubro/justica-eleitoral-define-revisao-de-eleitorado-com-biometria-em-185-municipios",
        "source_type": "official_news",
        "title": "Justica Eleitoral acrescenta mais um municipio a revisao de eleitorado com biometria",
        "issue_date": "2016-10-21",
        "treatment_reference_year": 2016,
        "annex_url": "http://sintse.tse.jus.br/documentos/2016/Out/20/provimento-no-14-de-18-de-outubro-de-2016-torna-publica-relacao-de-localidades-a-serem-submetidas-a-revisao-de-eleitorado-com-coleta-de-dados-biometricos-pertinente-ao-projeto-biometria-2015-2016-mediante-alteracao-do-anexo-do-provimento-no-5-cge-2015",
        "notes": "Official TSE news page with state-level summary of the 2016 cycle and a blocked annex link.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2016/Maio/tres-tem-ate-amanha-20-para-informar-cidades-onde-havera-eleicao-com-identificacao-biometrica-hibrida",
        "source_type": "official_news",
        "title": "TREs tem ate dia 20 para informar cidades onde havera eleicao com identificacao biometrica hibrida",
        "issue_date": "2016-05-19",
        "treatment_reference_year": 2016,
        "annex_url": "",
        "notes": "Official TSE note documenting hybrid identification as a first-order 2016 edge case.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2018/Janeiro/biometria-ultrapassa-50-do-eleitorado-brasileiro",
        "source_type": "official_news",
        "title": "Biometria ultrapassa 50 por cento do eleitorado brasileiro",
        "issue_date": "2018-01-30",
        "treatment_reference_year": 2018,
        "annex_url": "",
        "notes": "Official TSE summary page with election-use counts for 2008, 2010, 2012, 2014, and 2016.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2016/Agosto/27-dos-eleitores-estao-aptos-a-serem-identificados-biometricamente-nas-eleicoes-2016",
        "source_type": "official_news",
        "title": "27 por cento dos eleitores estao aptos a ser identificados biometricamente nas Eleicoes 2016",
        "issue_date": "2016-08-01",
        "treatment_reference_year": 2016,
        "annex_url": "",
        "notes": "Official TSE article stating that 1,540 municipalities would vote totalmente com biometria and 840 would vote em sistema hibrido in 2016.",
    },
    {
        "source_url": "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2016.zip",
        "source_type": "official_open_data",
        "title": "Perfil do eleitorado 2016",
        "issue_date": "",
        "treatment_reference_year": 2016,
        "annex_url": "",
        "notes": "Official TSE open-data electorate file used to identify municipalities with full biometric voting in 2016 via municipality-level biometric-elector share.",
    },
    {
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2018/Setembro/faltam-21-dias-cadastramento-biometrico-completa-10-anos-e-alcanca-a-mais-de-87-milhoes-de-eleitores",
        "source_type": "official_news",
        "title": "Faltam 21 dias cadastramento biometrico completa 10 anos e alcanca a mais de 87 milhoes de eleitores",
        "issue_date": "2018-09-16",
        "treatment_reference_year": 2018,
        "annex_url": "",
        "notes": "Official TSE article stating that 2,793 municipalities would vote exclusivamente com biometria and 1,533 em sistema hibrido in 2018.",
    },
    {
        "source_url": "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2018.zip",
        "source_type": "official_open_data",
        "title": "Perfil do eleitorado 2018",
        "issue_date": "",
        "treatment_reference_year": 2018,
        "annex_url": "",
        "notes": "Official TSE open-data electorate file used to identify municipalities marked as Biometrico or Hibrido in the 2018 election-year snapshot.",
    },
]

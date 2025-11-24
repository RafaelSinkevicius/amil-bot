import json
from pathlib import Path
import csv

from utils.logger import setup_logger
from utils.file_manager import OUTPUT_DIR, REDE_COMPLETA_DIR
from utils.delays import pausa_estrategica
from scraper.amil_scraper import AmilBot

SCRIPT_DIR = Path(__file__).resolve().parent


# =====================================================
# 🔹 NOVO — Função para gerar planilha com links públicos
# =====================================================
def gerar_planilha_simples(resultado_por_cidade: list[dict]):
    """
    Cria uma planilha CSV com:
    id ; cidade ; estado ; link_pdf_publico
    """
    planilha_dir = REDE_COMPLETA_DIR / "planilhas"
    planilha_dir.mkdir(parents=True, exist_ok=True)

    caminho_csv = planilha_dir / "planilha_simples.csv"

    # Base pública do GitHub Pages
    BASE_URL = "https://rafaelsinkevicius.github.io/amil-bot/pdfs"

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["id", "cidade", "estado", "link_pdf"])

        for idx, item in enumerate(resultado_por_cidade, start=1):
            cidade = item["cidade"]
            uf = item["uf"]

            pdf_name = f"{cidade}-{uf}.pdf"
            link_publico = f"{BASE_URL}/{uf}/{pdf_name}"

            writer.writerow([idx, cidade, uf, link_publico])

    print(f"📄 Planilha gerada em: {caminho_csv}")


# =====================================================
# Carregar arquivo JSON das cidades
# =====================================================
def carregar_mapa_estados() -> dict:
    caminho_json = SCRIPT_DIR / "estados_cidades_amil.json"
    with open(caminho_json, encoding="utf-8") as f:
        return json.load(f)


# =====================================================
# Logs finais (continua igual)
# =====================================================
def salvar_logs_finais(resultado_por_cidade, cidades_com_erro) -> None:
    REDE_COMPLETA_DIR.mkdir(parents=True, exist_ok=True)

    caminho_json_erros = REDE_COMPLETA_DIR / "cidades_com_erro.json"
    with open(caminho_json_erros, "w", encoding="utf-8") as f:
        json.dump(cidades_com_erro, f, ensure_ascii=False, indent=2)

    caminho_log = REDE_COMPLETA_DIR / "log_execucao.txt"
    total_ok = len(resultado_por_cidade)
    total_erro = sum(len(cidades) for cidades in cidades_com_erro.values())

    with open(caminho_log, "w", encoding="utf-8") as log:
        log.write("📊 RESUMO FINAL\n")
        log.write(f"✅ Cidades concluídas com sucesso: {total_ok}\n")
        log.write(f"❌ Cidades com erro: {total_erro}\n\n")
        log.write("📍 Prestadores por cidade:\n")
        for item in sorted(resultado_por_cidade, key=lambda x: (x["uf"], x["cidade"])):
            log.write(
                f"- {item['cidade']}/{item['uf']}: {item['prestadores']} prestadores\n"
            )


# =====================================================
# MAIN
# =====================================================
def main() -> None:
    logger = setup_logger("amil_bot", OUTPUT_DIR / "amil_bot.log")
    mapa = carregar_mapa_estados()

    resultado_por_cidade_global = []
    cidades_com_erro_global = {}
    contador_cidades = 0

    try:
        for uf, cidades in mapa.items():
            logger.info(f"====== Iniciando UF {uf} ({len(cidades)} cidades) ======")
            with AmilBot(uf, pasta_base=REDE_COMPLETA_DIR, logger=logger) as bot:
                for cidade in cidades:
                    bot.processar_cidade(cidade)

                    # coleta resultados
                    resultado_por_cidade_global.extend(bot.resultado_por_cidade)
                    for k, v in bot.cidades_com_erro.items():
                        cidades_com_erro_global.setdefault(k, []).extend(v)

                    # limpa buffers do bot
                    bot.resultado_por_cidade.clear()
                    bot.cidades_com_erro.clear()

                    contador_cidades += 1
                    pausa_estrategica(contador_cidades)

    except KeyboardInterrupt:
        logger.warning("⛔ Execução interrompida manualmente. Gerando logs parciais...")

    # salva logs normais
    salvar_logs_finais(resultado_por_cidade_global, cidades_com_erro_global)

    # 🔥 NOVO — gerar planilha pública
    gerar_planilha_simples(resultado_por_cidade_global)

    logger.info("✅ Execução finalizada.")


if __name__ == "__main__":
    main()
import json
from pathlib import Path
import csv

from utils.logger import setup_logger
from utils.file_manager import OUTPUT_DIR, DOCS_PDFS_DIR
from utils.delays import pausa_estrategica
from scraper.amil_scraper import AmilBot

SCRIPT_DIR = Path(__file__).resolve().parent


# =====================================================
# 🔹 Função para gerar/atualizar planilha com links públicos
# =====================================================
def gerar_planilha_simples(resultado_por_cidade: list[dict], modo_append: bool = False):
    """
    Cria ou atualiza uma planilha CSV com:
    id ; cidade ; estado ; link_pdf_publico
    
    Args:
        resultado_por_cidade: Lista de resultados a serem adicionados
        modo_append: Se True, adiciona ao arquivo existente. Se False, recria o arquivo.
    """
    # 🔥 MUDANÇA: planilha salva em docs/pdfs/planilhas/
    planilha_dir = DOCS_PDFS_DIR / "planilhas"
    planilha_dir.mkdir(parents=True, exist_ok=True)

    caminho_csv = planilha_dir / "planilha_simples.csv"
    
    # Verificar se o arquivo já existe e se tem conteúdo
    arquivo_existe = caminho_csv.exists() and caminho_csv.stat().st_size > 0

    # Base pública do GitHub Pages
    # 🔥 CORREÇÃO: quando GitHub Pages serve de /docs/, a pasta docs/ vira a raiz
    # Então docs/pdfs/ fica acessível como /pdfs/
    BASE_URL = "https://rafaelsinkevicius.github.io/amil-bot/pdfs"

    # Modo de abertura: append se modo_append=True e arquivo existe, senão write
    modo_abertura = "a" if (modo_append and arquivo_existe) else "w"
    
    with open(caminho_csv, modo_abertura, encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        
        # Só escreve cabeçalho se for modo write (novo arquivo)
        if modo_abertura == "w":
            writer.writerow(["id", "cidade", "estado", "link_pdf"])
        
        # Se for append, precisamos saber qual foi o último ID usado
        ultimo_id = 0
        if modo_abertura == "a" and arquivo_existe:
            # Ler o arquivo para pegar o último ID
            try:
                with open(caminho_csv, "r", encoding="utf-8") as f_read:
                    linhas = f_read.readlines()
                    if len(linhas) > 1:  # Tem pelo menos cabeçalho + 1 linha
                        # Pegar o último ID da última linha
                        ultima_linha = linhas[-1].strip()
                        if ultima_linha:
                            ultimo_id = int(ultima_linha.split(";")[0])
            except:
                pass
        
        # Escrever as novas cidades
        for item in resultado_por_cidade:
            ultimo_id += 1
            cidade = item["cidade"]
            uf = item["uf"]

            # 🔥 CORREÇÃO: usar o mesmo formato do get_pdf_path (espaços viram _)
            nome_arquivo = f"{cidade}-{uf}".replace(" ", "_")
            pdf_name = f"{nome_arquivo}.pdf"
            link_publico = f"{BASE_URL}/{uf}/{pdf_name}"

            writer.writerow([ultimo_id, cidade, uf, link_publico])

    print(f"📄 Planilha {'atualizada' if modo_append else 'gerada'} em: {caminho_csv}")


# =====================================================
# Carregar arquivo JSON das cidades
# =====================================================
def carregar_mapa_estados() -> dict:
    caminho_json = SCRIPT_DIR / "estados_cidades_amil.json"
    with open(caminho_json, encoding="utf-8") as f:
        return json.load(f)


# =====================================================
# Logs finais (salva em output/ apenas para logs)
# =====================================================
def salvar_logs_finais(resultado_por_cidade, cidades_com_erro) -> None:
    # 🔥 MUDANÇA: logs salvos em output/ (não em docs/)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    caminho_json_erros = OUTPUT_DIR / "cidades_com_erro.json"
    with open(caminho_json_erros, "w", encoding="utf-8") as f:
        json.dump(cidades_com_erro, f, ensure_ascii=False, indent=2)

    caminho_log = OUTPUT_DIR / "log_execucao.txt"
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
    
    # Flag para controlar se já criou o cabeçalho da planilha
    primeira_vez = True

    try:
        for uf, cidades in mapa.items():
            logger.info(f"====== Iniciando UF {uf} ({len(cidades)} cidades) ======")
            # 🔥 MUDANÇA: usar DOCS_PDFS_DIR ao invés de REDE_COMPLETA_DIR
            with AmilBot(uf, pasta_base=DOCS_PDFS_DIR, logger=logger) as bot:
                for cidade in cidades:
                    bot.processar_cidade(cidade)

                    # coleta resultados
                    resultado_por_cidade_global.extend(bot.resultado_por_cidade)
                    for k, v in bot.cidades_com_erro.items():
                        cidades_com_erro_global.setdefault(k, []).extend(v)

                    # 🔥 NOVO — salvar planilha incrementalmente após cada cidade
                    if bot.resultado_por_cidade:
                        gerar_planilha_simples(
                            bot.resultado_por_cidade, 
                            modo_append=not primeira_vez
                        )
                        primeira_vez = False

                    # limpa buffers do bot
                    bot.resultado_por_cidade.clear()
                    bot.cidades_com_erro.clear()

                    contador_cidades += 1
                    pausa_estrategica(contador_cidades)

    except KeyboardInterrupt:
        logger.warning("⛔ Execução interrompida manualmente. Gerando logs parciais...")

    # salva logs normais
    salvar_logs_finais(resultado_por_cidade_global, cidades_com_erro_global)

    # A planilha já foi gerada incrementalmente durante o processamento
    # Não precisa regenerar no final, mas pode fazer se quiser garantir consistência
    # gerar_planilha_simples(resultado_por_cidade_global)  # Opcional

    logger.info("✅ Execução finalizada.")


if __name__ == "__main__":
    main()
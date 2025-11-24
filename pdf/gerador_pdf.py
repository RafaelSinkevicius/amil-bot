import os
import shutil
from pathlib import Path
import pdfkit
from datetime import datetime
import locale

from utils.file_manager import (
    SCRIPT_DIR,
    REDE_COMPLETA_DIR,
    get_estado_dir,
    get_pdf_path,
)

# ---------------------------------------------------------------------
#    CONFIGURAÇÃO DE LOCALIZAÇÃO – GARANTE MÊS EM PORTUGUÊS
# ---------------------------------------------------------------------
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "pt_BR")
    except:
        pass

# ---------------------------------------------------------------------
#    WKHTMLTOPDF CONFIG
# ---------------------------------------------------------------------
WKHTMLTOPDF_PATH = os.getenv(
    "WKHTMLTOPDF_PATH",
    r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
)

PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
TEMPLATE_DIR = Path(__file__).parent / "templates"


def _carregar_template(nome_arquivo: str) -> str:
    caminho = TEMPLATE_DIR / nome_arquivo
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read()


# =====================================================================
#                    COPIAR PDF PARA GITHUB PAGES
# =====================================================================
def _copiar_para_github_pages(pdf_path: Path, uf: str) -> None:
    """
    Copia o PDF gerado para a pasta docs/pdfs para GitHub Pages.
    """
    try:
        destino_base = SCRIPT_DIR / "docs" / "pdfs"
        destino_uf = destino_base / uf
        destino_uf.mkdir(parents=True, exist_ok=True)
        
        destino_pdf = destino_uf / pdf_path.name
        
        # Copiar apenas se o arquivo foi modificado ou não existe
        precisa_copiar = True
        if destino_pdf.exists():
            if pdf_path.stat().st_mtime <= destino_pdf.stat().st_mtime:
                precisa_copiar = False
        
        if precisa_copiar:
            shutil.copy2(pdf_path, destino_pdf)
            print(f"📤 PDF copiado para GitHub Pages: {destino_pdf}")
    except Exception as e:
        # Não interrompe o processo se falhar a cópia
        print(f"⚠️  Aviso: não foi possível copiar para GitHub Pages: {e}")


# =====================================================================
#                    GERAR PDF — PRESTADORES
# =====================================================================
def gerar_pdf_prestadores(uf: str,
                          cidade: str,
                          prestadores: list[dict],
                          pasta_base: Path | None = None) -> None:
    """
    Gera o PDF normal com lista de prestadores.
    """
    if pasta_base is None:
        pasta_base = REDE_COMPLETA_DIR

    get_estado_dir(uf, pasta_base)
    pdf_path = get_pdf_path(uf, cidade, pasta_base)

    template = _carregar_template("prestadores.html")

    # LOGOS
    logo_amil = (SCRIPT_DIR / "amil_dental.jpg").resolve().as_uri()
    logo_ativa = (SCRIPT_DIR / "logo_ativa.jpg").resolve().as_uri()

    # Cabeçalho mês/ano
    hoje = datetime.now()
    mes_ano = hoje.strftime("%B / %Y").capitalize()

    # Gera os blocos dos prestadores
    html_prestadores = []
    for p in prestadores:
        bloco = (
            "<div class='prestador'>"
            f"<strong>Nome:</strong> {p['nome']}<br>"
            f"<strong>Bairro:</strong> {p['bairro']}<br>"
            f"<strong>Endereço:</strong> {p['endereco']}<br>"
            f"<strong>Telefone:</strong> {p['telefone']}"
            "</div>"
        )
        html_prestadores.append(bloco)

    # Insere tudo no template
    html = (
        template
        .replace("{{LOGO_AMIL}}", logo_amil)
        .replace("{{LOGO_ATIVA}}", logo_ativa)
        .replace("{{REFERENCIA}}", mes_ano)
        .replace("{{CIDADE}}", cidade)
        .replace("{{UF}}", uf)
        .replace("{{TOTAL_PRESTADORES}}", str(len(prestadores)))
        .replace("<!--PRESTADORES-->", "\n".join(html_prestadores))
    )

    options_pdf = {"enable-local-file-access": ""}

    pdfkit.from_string(html, str(pdf_path), configuration=PDFKIT_CONFIG, options=options_pdf)
    print(f"✅ PDF salvo: {pdf_path}")
    
    # 🔥 NOVO — copiar automaticamente para GitHub Pages
    _copiar_para_github_pages(pdf_path, uf)


# =====================================================================
#            GERAR PDF — SEM ESPECIALIDADE
# =====================================================================
def gerar_pdf_sem_especialidade(uf: str,
                                cidade: str,
                                pasta_base: Path | None = None) -> None:
    """
    Gera o PDF para cidades sem CLÍNICA GERAL.
    """
    if pasta_base is None:
        pasta_base = REDE_COMPLETA_DIR

    get_estado_dir(uf, pasta_base)
    pdf_path = get_pdf_path(uf, cidade, pasta_base)

    template = _carregar_template("sem_especialidade.html")

    # Cabeçalho mês/ano
    hoje = datetime.now()
    mes_ano = hoje.strftime("%B / %Y").capitalize()

    html = (
        template
        .replace("{{REFERENCIA}}", mes_ano)
        .replace("{{CIDADE}}", cidade)
        .replace("{{UF}}", uf)
    )

    options_pdf = {"enable-local-file-access": ""}

    pdfkit.from_string(html, str(pdf_path), configuration=PDFKIT_CONFIG, options=options_pdf)
    print(f"⚠️ PDF sem especialidade gerado: {pdf_path}")
    
    # 🔥 NOVO — copiar automaticamente para GitHub Pages
    _copiar_para_github_pages(pdf_path, uf)
"""
Script para copiar PDFs para a pasta docs/pdfs do GitHub Pages

Execute este script após gerar os PDFs para atualizar o GitHub Pages.
Os PDFs serão copiados mantendo a estrutura de pastas por UF.

Uso:
    python scripts/copiar_pdfs_para_github.py
"""
import sys
import shutil
from pathlib import Path

# Adicionar o diretório raiz ao PYTHONPATH para permitir imports
SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

# Agora podemos importar os módulos do projeto
from utils.file_manager import REDE_COMPLETA_DIR

# Caminhos
ORIGEM = REDE_COMPLETA_DIR
DESTINO = SCRIPT_DIR / "docs" / "pdfs"


def copiar_pdfs():
    """
    Copia todos os PDFs para a pasta docs/pdfs mantendo a estrutura de pastas por UF.
    """
    print("🔄 Iniciando cópia de PDFs para GitHub Pages...\n")
    
    # Verificar se a pasta de origem existe
    if not ORIGEM.exists():
        print(f"❌ Pasta de origem não encontrada: {ORIGEM}")
        print("💡 Execute o bot primeiro para gerar os PDFs!")
        return False
    
    # Criar pasta destino
    DESTINO.mkdir(parents=True, exist_ok=True)
    print(f"📁 Pasta destino criada/verificada: {DESTINO}\n")
    
    # Contadores
    total_copiados = 0
    total_atualizados = 0
    erros = []
    
    # Copiar estrutura de pastas por UF
    for uf_dir in sorted(ORIGEM.iterdir()):
        if not uf_dir.is_dir():
            continue
        
        uf = uf_dir.name
        destino_uf = DESTINO / uf
        destino_uf.mkdir(parents=True, exist_ok=True)
        
        # Copiar PDFs de cada UF
        pdfs_uf = list(uf_dir.glob("*.pdf"))
        if not pdfs_uf:
            continue
        
        print(f"📂 Processando {uf} ({len(pdfs_uf)} PDFs)...")
        
        for pdf_file in sorted(pdfs_uf):
            try:
                destino_pdf = destino_uf / pdf_file.name
                
                # Verificar se precisa copiar (arquivo novo ou modificado)
                precisa_copiar = True
                if destino_pdf.exists():
                    # Comparar timestamps
                    if pdf_file.stat().st_mtime <= destino_pdf.stat().st_mtime:
                        precisa_copiar = False
                
                if precisa_copiar:
                    shutil.copy2(pdf_file, destino_pdf)
                    if destino_pdf.exists() and destino_pdf.stat().st_size > 0:
                        total_copiados += 1
                        print(f"  ✅ {pdf_file.name}")
                    else:
                        erros.append(f"{uf}/{pdf_file.name}")
                        print(f"  ⚠️  Erro ao copiar: {pdf_file.name}")
                else:
                    total_atualizados += 1
                    print(f"  ⏭️  {pdf_file.name} (já atualizado)")
                    
            except Exception as e:
                erros.append(f"{uf}/{pdf_file.name}: {str(e)}")
                print(f"  ❌ Erro ao copiar {pdf_file.name}: {e}")
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DA CÓPIA")
    print("="*60)
    print(f"✅ PDFs copiados/atualizados: {total_copiados}")
    print(f"⏭️  PDFs já atualizados: {total_atualizados}")
    print(f"❌ Erros: {len(erros)}")
    
    if erros:
        print("\n⚠️  Erros encontrados:")
        for erro in erros:
            print(f"   - {erro}")
    
    print(f"\n📦 Total processado: {total_copiados + total_atualizados} PDFs")
    print(f"📁 Destino: {DESTINO}")
    
    if total_copiados > 0 or total_atualizados > 0:
        print("\n💡 Próximos passos:")
        print("   1. Verifique os arquivos em docs/pdfs/")
        print("   2. Faça commit: git add docs/pdfs/")
        print("   3. Faça push: git push")
        print("   4. O GitHub Pages será atualizado automaticamente!")
    
    return len(erros) == 0


def limpar_pdfs_antigos():
    """
    Remove PDFs do destino que não existem mais na origem.
    Útil para manter sincronizado.
    """
    print("\n🧹 Verificando PDFs obsoletos...")
    
    if not DESTINO.exists():
        print("   Nenhum arquivo para limpar (pasta destino não existe)")
        return
    
    pdfs_origem = set()
    for uf_dir in ORIGEM.iterdir():
        if uf_dir.is_dir():
            for pdf in uf_dir.glob("*.pdf"):
                pdfs_origem.add((uf_dir.name, pdf.name))
    
    removidos = 0
    for uf_dir in DESTINO.iterdir():
        if not uf_dir.is_dir():
            continue
        
        for pdf_file in uf_dir.glob("*.pdf"):
            if (uf_dir.name, pdf_file.name) not in pdfs_origem:
                try:
                    pdf_file.unlink()
                    removidos += 1
                    print(f"   🗑️  Removido: {uf_dir.name}/{pdf_file.name}")
                except Exception as e:
                    print(f"   ⚠️  Erro ao remover {pdf_file.name}: {e}")
    
    if removidos > 0:
        print(f"\n   ✅ {removidos} arquivo(s) obsoleto(s) removido(s)")
    else:
        print("   ✅ Nenhum arquivo obsoleto encontrado")


if __name__ == "__main__":
    # Verificar argumentos
    limpar = "--limpar" in sys.argv or "-l" in sys.argv
    
    try:
        sucesso = copiar_pdfs()
        
        if limpar:
            limpar_pdfs_antigos()
        
        sys.exit(0 if sucesso else 1)
        
    except KeyboardInterrupt:
        print("\n\n⛔ Operação cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
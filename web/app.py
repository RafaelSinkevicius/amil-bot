from flask import Flask, render_template, jsonify, request, send_file
from pathlib import Path
import json
import threading
import os
from datetime import datetime
import time # �� NOVO — Importar módulo time

# Importar módulos do bot
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.file_manager import DOCS_PDFS_DIR, OUTPUT_DIR
from main import executar_bot_com_callbacks

app = Flask(__name__)

# Status global da execução
status_execucao = {
    "rodando": False,
    "progresso": 0,
    "total": 0,
    "cidade_atual": "",
    "uf_atual": "",
    "log": [],
    "erro": None,
    "inicio": None,
    "fim": None
}

# Thread de execução
thread_execucao = None
stop_flag = threading.Event()

@app.route('/')
def index():
    """Página principal."""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Retorna status atual da execução."""
    return jsonify(status_execucao)

@app.route('/api/iniciar', methods=['POST'])
def iniciar_bot():
    """Inicia a execução do bot."""
    global thread_execucao, stop_flag
    
    # 🔥 CORREÇÃO — Verificar se thread anterior ainda está rodando
    if status_execucao["rodando"]:
        return jsonify({"erro": "Bot já está em execução"}), 400
    
    # 🔥 CORREÇÃO — Verificar se thread anterior ainda existe e está viva
    if thread_execucao is not None and thread_execucao.is_alive():
        return jsonify({"erro": "Thread anterior ainda está rodando. Aguarde alguns segundos."}), 400
    
    # 🔥 NOVO — Verificar se quer continuar progresso
    data = request.get_json() or {}
    continuar_progresso = data.get("continuar_progresso", True)
    
    # 🔥 CORREÇÃO — Carregar progresso ANTES de resetar status para mostrar na interface
    progresso_anterior = None
    if continuar_progresso:
        from main import carregar_progresso
        progresso_anterior = carregar_progresso()
    
    # Resetar status
    status_execucao["rodando"] = True
    status_execucao["progresso"] = 0
    status_execucao["total"] = 0
    # 🔥 CORREÇÃO — Se tem progresso, mostrar cidade anterior
    if progresso_anterior:
        status_execucao["cidade_atual"] = progresso_anterior["cidade"]
        status_execucao["uf_atual"] = progresso_anterior["uf"]
    else:
        status_execucao["cidade_atual"] = ""
        status_execucao["uf_atual"] = ""
    status_execucao["log"] = []
    status_execucao["erro"] = None
    status_execucao["inicio"] = datetime.now().isoformat()
    status_execucao["fim"] = None
    stop_flag.clear()
    
    # Iniciar em thread separada
    thread_execucao = threading.Thread(
        target=executar_bot_com_status, 
        args=(continuar_progresso,)  # 🔥 NOVO — Passar flag
    )
    thread_execucao.daemon = True
    thread_execucao.start()
    
    mensagem = "Bot iniciado com sucesso"
    if continuar_progresso and progresso_anterior:
        mensagem += f" (continuando de {progresso_anterior['cidade']}-{progresso_anterior['uf']})"
    elif continuar_progresso:
        mensagem += " (começando do zero - nenhum progresso salvo)"
    else:
        from main import limpar_progresso
        limpar_progresso()
        mensagem += " (começando do zero - progresso anterior limpo)"
    
    return jsonify({"mensagem": mensagem})

@app.route('/api/parar', methods=['POST'])
def parar_bot():
    """Para a execução do bot."""
    global stop_flag
    stop_flag.set()
    status_execucao["rodando"] = False
    status_execucao["erro"] = None  # Limpar erro ao parar
    return jsonify({"mensagem": "Parando bot..."})

# 🔥 NOVO — Rota para limpar erro
@app.route('/api/limpar-erro', methods=['POST'])
def limpar_erro():
    """Limpa o erro do status."""
    status_execucao["erro"] = None
    return jsonify({"mensagem": "Erro limpo"})

# 🔥 NOVO — Rota para verificar progresso
@app.route('/api/progresso')
def get_progresso():
    """Retorna o progresso salvo."""
    try:
        from main import carregar_progresso
        progresso = carregar_progresso()
        return jsonify({"progresso": progresso})
    except Exception as e:
        import traceback
        traceback.print_exc()  # 🔥 NOVO — Debug
        return jsonify({"progresso": None, "erro": str(e)}), 500

# 🔥 NOVO — Rota para limpar progresso
@app.route('/api/limpar-progresso', methods=['POST'])
def limpar_progresso_route():
    """Limpa o progresso salvo."""
    from main import limpar_progresso
    limpar_progresso()
    return jsonify({"mensagem": "Progresso limpo"})

@app.route('/api/planilha')
def download_planilha():
    """Download da planilha Excel."""
    caminho = DOCS_PDFS_DIR / "planilhas" / "planilha_simples.xlsx"
    if caminho.exists():
        return send_file(str(caminho), as_attachment=True, download_name="planilha_amil.xlsx")
    return jsonify({"erro": "Planilha não encontrada"}), 404

@app.route('/api/logs')
def get_logs():
    """Retorna logs recentes do arquivo."""
    caminho_log = OUTPUT_DIR / "amil_bot.log"
    if caminho_log.exists():
        try:
            with open(caminho_log, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
                return jsonify({"logs": linhas[-200:]})  # Últimas 200 linhas
        except:
            return jsonify({"logs": []})
    return jsonify({"logs": []})

@app.route('/api/estatisticas')
def get_estatisticas():
    """Retorna estatísticas dos PDFs gerados."""
    try:
        total_pdfs = 0
        estados = {}
        
        # 🔥 CORREÇÃO — Verificar se o diretório existe
        if not DOCS_PDFS_DIR.exists():
            return jsonify({
                "total_pdfs": 0,
                "estados": {},
                "erro": "Diretório de PDFs não encontrado"
            })
        
        # 🔥 CORREÇÃO — Tratar erro se não conseguir iterar
        try:
            for uf_dir in DOCS_PDFS_DIR.iterdir():
                if uf_dir.is_dir() and uf_dir.name != "planilhas":
                    pdfs = list(uf_dir.glob("*.pdf"))
                    total_pdfs += len(pdfs)
                    estados[uf_dir.name] = len(pdfs)
        except Exception as e:
            import traceback
            traceback.print_exc()  # 🔥 NOVO — Debug
            return jsonify({
                "total_pdfs": 0,
                "estados": {},
                "erro": f"Erro ao ler diretórios: {str(e)}"
            }), 500
        
        return jsonify({
            "total_pdfs": total_pdfs,
            "estados": estados
        })
    except Exception as e:
        import traceback
        traceback.print_exc()  # 🔥 NOVO — Debug
        return jsonify({
            "total_pdfs": 0,
            "estados": {},
            "erro": str(e)
        }), 500

def executar_bot_com_status(continuar_progresso=True):  # 🔥 NOVO — Parâmetro
    """Executa o bot atualizando status."""
    def callback_progresso(uf, cidade, total, atual):
        status_execucao["uf_atual"] = uf
        status_execucao["cidade_atual"] = cidade
        status_execucao["total"] = total
        status_execucao["progresso"] = atual
        status_execucao["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Processando {cidade}-{uf}")
        if len(status_execucao["log"]) > 100:
            status_execucao["log"] = status_execucao["log"][-100:]
    
    def callback_log(mensagem):
        status_execucao["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {mensagem}")
        if len(status_execucao["log"]) > 100:
            status_execucao["log"] = status_execucao["log"][-100:]
    
    try:
        executar_bot_com_callbacks(callback_progresso, callback_log, stop_flag, continuar_progresso)  # 🔥 NOVO
        status_execucao["progresso"] = status_execucao["total"]
        status_execucao["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Bot finalizado com sucesso!")
    except Exception as e:
        status_execucao["erro"] = str(e)
        status_execucao["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erro: {e}")
    finally:
        status_execucao["rodando"] = False
        status_execucao["fim"] = datetime.now().isoformat()
        # �� NOVO — Limpar erro após 3 segundos (tempo para o frontend mostrar)
        import threading
        import time
        def limpar_erro_depois():
            time.sleep(3)
            if not status_execucao["rodando"]:
                status_execucao["erro"] = None
        threading.Thread(target=limpar_erro_depois, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

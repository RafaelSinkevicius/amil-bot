import random
import time
import os
import shutil
from pathlib import Path
from typing import Any
import tempfile  # 🔥 NOVO

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.delays import delay_humano
from utils.file_manager import get_pdf_path, REDE_COMPLETA_DIR
from scraper.anti_bot import build_chrome_options, apply_stealth
from scraper.navegacao import (
    aguardar_pagina_carregar,
)

from pdf.gerador_pdf import gerar_pdf_prestadores, gerar_pdf_sem_especialidade


# ============================================================
#  PROXIES OPCIONAIS (não usados se lista estiver vazia)
# ============================================================
PROXIES: list[str] = []


# ============================================================
#              BOT AMIL — ESTÁVEL FINAL (V.B)
# ============================================================
class AmilBot:
    def __init__(
        self,
        uf: str,
        pasta_base: Path | None = None,
        logger=None,
        proxies: list[str] | None = None,
        stop_flag=None,  # 🔥 NOVO
    ) -> None:

        self.uf = uf
        self.pasta_base = pasta_base or REDE_COMPLETA_DIR
        self.logger = logger
        self.stop_flag = stop_flag  # 🔥 NOVO

        self.driver = None
        self.wait: WebDriverWait | None = None
        self.wait_dropdown: WebDriverWait | None = None

        self.resultado_por_cidade = []
        self.cidades_com_erro = {}

        self.proxies = proxies if proxies is not None else PROXIES

    # ---------------------- utils ----------------------

    def _log(self, msg: str) -> None:
        if self.logger:
            self.logger.info(msg)
        else:
            print(msg)

    def _escolher_proxy(self) -> str | None:
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def _cooldown(self) -> None:
        """Cooldown entre cidades para parecer humano."""
        # 🔥 OTIMIZADO: Cooldown reduzido - perfil único garante fingerprint diferente
        # Base: 10-18 segundos (reduzido de 15-25s)
        cooldown_base = random.uniform(10.0, 18.0)
        
        # Cooldown progressivo: aumenta com o número de cidades processadas
        if hasattr(self, '_cidades_processadas_uf'):
            cooldown_extra = min(self._cidades_processadas_uf * 0.3, 15)  # Reduzido de 0.5 para 0.3, max 15s
            cooldown_time = cooldown_base + cooldown_extra
        else:
            cooldown_time = cooldown_base
        
        self._log(f"⏳ Cooldown de {cooldown_time:.1f}s entre cidades...")
        time.sleep(cooldown_time)

        # Não precisa fazer scroll se não há driver (já foi fechado)
        if not self.driver:
            return

        # movimentos aleatórios mais realistas
        for _ in range(random.randint(3, 6)):
            try:
                x = random.randint(0, 800)
                y = random.randint(0, 600)
                self.driver.execute_script(f"window.scrollTo({x}, {y});")
                time.sleep(random.uniform(0.3, 0.7))
            except:
                pass

    # 🔥 NOVO — Verificar se há bloqueio/captcha
    def _verificar_bloqueio(self) -> bool:
        """Verifica se o site bloqueou ou pediu captcha."""
        try:
            # Verificar textos comuns de bloqueio
            bloqueios = [
                "captcha",
                "verificação",
                "bloqueado",
                "suspenso",
                "acesso negado",
                "too many requests",
                "rate limit",
            ]
            
            page_text = self.driver.page_source.lower()
            for bloqueio in bloqueios:
                if bloqueio in page_text:
                    self._log(f"⚠️ Possível bloqueio detectado: {bloqueio}")
                    return True
            
            # Verificar se há iframe de captcha
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if "captcha" in src.lower() or "recaptcha" in src.lower():
                        self._log("⚠️ Captcha detectado!")
                        return True
            except:
                pass
                
            return False
        except:
            return False

    # 🔥 NOVO — Limpar completamente dados do navegador
    def _limpar_dados_navegador(self):
        """Limpa todos os dados do navegador antes de fechar."""
        if not self.driver:
            return
        
        try:
            # Limpar cookies
            self.driver.delete_all_cookies()
            self._log("🧹 Cookies limpos")
        except:
            pass
        
        try:
            # Limpar localStorage
            self.driver.execute_script("window.localStorage.clear();")
        except:
            pass
        
        try:
            # Limpar sessionStorage
            self.driver.execute_script("window.sessionStorage.clear();")
        except:
            pass
        
        try:
            # Limpar IndexedDB
            self.driver.execute_script("""
                if (window.indexedDB) {
                    indexedDB.databases().then(dbs => {
                        dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                    });
                }
            """)
        except:
            pass

    def _fechar_navegador_completamente(self):
        """Fecha o navegador e limpa completamente todos os dados."""
        import shutil
        
        if self.driver:
            try:
                # Limpar dados do navegador
                self._limpar_dados_navegador()
                
                # Fechar navegador
                self.driver.quit()
                
                # 🔥 NOVO — Aguardar processo terminar
                time.sleep(random.uniform(2.0, 4.0))
                
            except Exception as e:
                self._log(f"⚠️ Erro ao fechar navegador: {e}")
            finally:
                self.driver = None
                self.wait = None
                self.wait_dropdown = None
        
        # 🔥 NOVO — Limpar perfil temporário
        if hasattr(self, '_perfil_temp') and self._perfil_temp:
            try:
                import shutil
                if os.path.exists(self._perfil_temp):
                    shutil.rmtree(self._perfil_temp, ignore_errors=True)
                    self._log("🧹 Perfil temporário removido")
            except Exception as e:
                self._log(f"⚠️ Erro ao remover perfil: {e}")
            finally:
                self._perfil_temp = None

    # ---------------------- contexto ----------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    # ------------------------------------------------------
    #         ABRIR NAVEGADOR — SEMPRE LIMPO POR CIDADE
    # ------------------------------------------------------
    def _abrir_navegador(self):
        import tempfile
        import os
        
        # 🔥 CORREÇÃO — Tentar sem perfil temporário primeiro (pode estar causando problema)
        # Se continuar dando problema, podemos voltar a usar perfil temporário
        usar_perfil_temp = False  # 🔥 DESABILITADO temporariamente para testar
        
        if usar_perfil_temp:
            perfil_temp = tempfile.mkdtemp(prefix="chrome_profile_")
        else:
            perfil_temp = None
        
        ua = random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        ])

        proxy = self._escolher_proxy()
        if proxy:
            self._log(f"🌐 Usando proxy: {proxy}")
        else:
            self._log("🌐 Conexão direta (sem proxy).")

        options = build_chrome_options(user_agent=ua, proxy=proxy)
        
        # 🔥 CORREÇÃO — Usar perfil temporário apenas se habilitado
        if usar_perfil_temp and perfil_temp:
            options.add_argument(f"--user-data-dir={perfil_temp}")
        
        # 🔥 NOVO — Variação no viewport para parecer mais humano
        viewport_width = random.randint(1280, 1920)
        viewport_height = random.randint(720, 1080)
        options.add_argument(f"--window-size={viewport_width},{viewport_height}")

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        self.wait = WebDriverWait(self.driver, 25)
        self.wait_dropdown = WebDriverWait(self.driver, 15)
        
        # 🔥 NOVO — Guardar caminho do perfil para limpar depois
        self._perfil_temp = perfil_temp

        # 🔥 CORREÇÃO — Aplicar stealth DEPOIS de carregar a página (não antes)
        # apply_stealth(self.driver)  # REMOVIDO - aplicar depois

        # 🔥 OTIMIZADO: Mais tempo antes de carregar página
        time.sleep(random.uniform(2.0, 4.0))

        # 🔥 CORREÇÃO — Tentar carregar a página com retry
        max_tentativas_carregar = 3
        pagina_carregou = False
        
        for tentativa in range(max_tentativas_carregar):
            try:
                self._log(f"🌐 Tentando carregar página (tentativa {tentativa + 1}/{max_tentativas_carregar})...")
                
                self.driver.get(
                    "https://www.amil.com.br/institucional/#/servicos/saude/rede-credenciada/amil/busca-avancada"
                )

                # 🔥 CORREÇÃO — Melhorar verificação de carregamento para SPAs
                aguardar_pagina_carregar(self.driver, self.wait)
                
                # 🔥 NOVO — Aguardar mais tempo para JavaScript carregar
                time.sleep(random.uniform(3.0, 5.0))
                
                # 🔥 CORREÇÃO — Verificar se a página não está em branco
                page_source = self.driver.page_source
                
                # Verificar tamanho mínimo
                if len(page_source) < 1000:
                    self._log(f"⚠️ Página muito pequena ({len(page_source)} chars), tentando recarregar...")
                    if tentativa < max_tentativas_carregar - 1:
                        time.sleep(random.uniform(2.0, 4.0))
                        continue
                    else:
                        raise Exception("Página não carregou corretamente (muito pequena)")
                
                # Verificar se há conteúdo esperado
                page_lower = page_source.lower()
                if "amil" not in page_lower and "rede" not in page_lower and "credenciada" not in page_lower:
                    self._log("⚠️ Conteúdo da página não parece correto, tentando recarregar...")
                    if tentativa < max_tentativas_carregar - 1:
                        time.sleep(random.uniform(2.0, 4.0))
                        continue
                    else:
                        raise Exception("Conteúdo da página não parece correto")
                
                # Verificar se há body com conteúdo
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    if len(body_text.strip()) < 50:
                        self._log("⚠️ Body da página está vazio, tentando recarregar...")
                        if tentativa < max_tentativas_carregar - 1:
                            time.sleep(random.uniform(2.0, 4.0))
                            continue
                except:
                    pass
                
                # Se chegou aqui, página carregou corretamente
                pagina_carregou = True
                self._log(f"✅ Página carregada com sucesso ({len(page_source)} chars)")
                break
                
            except Exception as e:
                self._log(f"⚠️ Erro ao carregar página (tentativa {tentativa + 1}): {e}")
                if tentativa < max_tentativas_carregar - 1:
                    self._log("🔄 Tentando recarregar...")
                    time.sleep(random.uniform(3.0, 5.0))
                else:
                    raise Exception(f"Falha ao carregar página após {max_tentativas_carregar} tentativas: {e}")
        
        if not pagina_carregou:
            raise Exception("Página não carregou corretamente após todas as tentativas")
        
        # 🔥 CORREÇÃO — Aplicar stealth DEPOIS de carregar a página
        try:
            apply_stealth(self.driver)
        except Exception as e:
            self._log(f"⚠️ Erro ao aplicar stealth: {e}")
        
        # 🔥 OTIMIZADO: Mais tempo após carregar
        time.sleep(random.uniform(2.0, 3.0))

        try:
            self.wait.until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            ).click()
            time.sleep(random.uniform(1.0, 2.0))
        except:
            pass

        try:
            self.driver.maximize_window()
            time.sleep(random.uniform(1.0, 2.0))
        except:
            pass
        
        # Verificar bloqueio após abrir
        if self._verificar_bloqueio():
            self._log("⚠️ Bloqueio detectado após abrir navegador!")
            raise Exception("Site bloqueou o acesso")

    # ------------------------------------------------------
    #                   PROCESSAR CIDADE
    # ------------------------------------------------------
    def processar_cidade(self, cidade: str) -> None:
        if self.stop_flag and self.stop_flag.is_set():
            self._log("⛔ Execução interrompida pelo usuário")
            raise Exception("Execução interrompida pelo usuário")

        caminho_pdf = get_pdf_path(self.uf, cidade, self.pasta_base)
        if caminho_pdf.exists():
            self._log(f"⏭️ PDF já existe — pulando {cidade}-{self.uf}")
            # 🔥 OTIMIZADO: Cooldown mesmo quando pula
            time.sleep(random.uniform(5.0, 10.0))
            return

        self._log(f"\n🔄 Processando {cidade}-{self.uf}")
        self._current_city = cidade

        # 🔥 OTIMIZADO: Cooldown maior antes de abrir navegador
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        # 🔥 OTIMIZADO: Cooldown antes de abrir navegador (reduzido - perfil único agora)
        # Cooldown antes de abrir navegador
        time.sleep(random.uniform(5.0, 10.0))  # Reduzido de 10-18s para 5-10s

        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        # navegador limpo sempre
        self._abrir_navegador()
        
        # Verificar bloqueio após abrir
        if self._verificar_bloqueio():
            self._log("⚠️ Bloqueio detectado! Aguardando muito mais tempo...")
            time.sleep(random.uniform(60, 120))  # 1-2 minutos
            if self._verificar_bloqueio():
                raise Exception("Site bloqueou o acesso após espera")

        try:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            self._passo1()
            time.sleep(random.uniform(1.5, 3.0))
            
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            self._passo2(cidade)
            time.sleep(random.uniform(1.5, 3.0))
            
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            self._passo3(cidade)
            time.sleep(random.uniform(2.0, 4.0))
            
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            prestadores = self._capturar()

            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")

            # VALIDAÇÃO: só gera PDF se houver prestadores válidos
            if prestadores and len(prestadores) > 0:
                gerar_pdf_prestadores(self.uf, cidade, prestadores, self.pasta_base)
                self._log(f"📄 PDF gerado: {cidade}-{self.uf} ({len(prestadores)} prestadores)")
                
                self.resultado_por_cidade.append({
                    "cidade": cidade,
                    "uf": self.uf,
                    "prestadores": len(prestadores)
                })
                
                # 🔥 NOVO — Incrementar contador para cooldown progressivo
                if not hasattr(self, '_cidades_processadas_uf'):
                    self._cidades_processadas_uf = 0
                self._cidades_processadas_uf += 1
            else:
                self._log(f"⚠️ Nenhum prestador válido encontrado em {cidade}-{self.uf}. Tentando novamente...")
                raise Exception("Nenhum prestador válido encontrado")

        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                self._log("⛔ Execução interrompida pelo usuário")
                raise Exception("Execução interrompida pelo usuário")
            
            # 🔥 NOVO — Verificar se é exceção de especialidade não encontrada
            if "Especialidade não encontrada" in str(e):
                self._log(f"✅ PDF vazio gerado para {cidade}-{self.uf} (sem especialidade)")
                
                # Adicionar ao resultado com 0 prestadores
                self.resultado_por_cidade.append({
                    "cidade": cidade,
                    "uf": self.uf,
                    "prestadores": 0
                })
                
                # 🔥 NOVO — Incrementar contador para cooldown progressivo
                if not hasattr(self, '_cidades_processadas_uf'):
                    self._cidades_processadas_uf = 0
                self._cidades_processadas_uf += 1
                
                # Fechar navegador normalmente
                if self.driver:
                    try:
                        self._limpar_dados_navegador()
                        self.driver.quit()
                    except:
                        pass
                    finally:
                        self.driver = None
                        self.wait = None
                        self.wait_dropdown = None
                
                # Retornar normalmente (não fazer retry)
                return
            
            # Se não for exceção de especialidade, tratar como erro normal
            self._log(f"⚠️ Falha em {cidade}-{self.uf}: {e}")
            self._log("🛑 Fechando navegador antes do cooldown...")

            # 🔥 CORREÇÃO — Fechar navegador completamente
            self._fechar_navegador_completamente()

            # 🔥 OTIMIZADO: Cooldown muito maior em caso de erro
            cooldown = random.uniform(60, 120)  # 1-2 minutos
            self._log(f"⏳ Aguardando {cooldown:.1f} segundos para limpar fingerprint...")
            time.sleep(cooldown)

            self._log("🔁 Reabrindo navegador e tentando novamente...")

            try:
                return self.processar_cidade(cidade)  # retry real
            except Exception as e2:
                self._log(f"❌ Falha definitiva em {cidade}-{self.uf}: {e2}")
                self.cidades_com_erro.setdefault(self.uf, []).append(cidade)

        finally:
            # 🔥 CORREÇÃO — Fechar navegador completamente
            self._fechar_navegador_completamente()
            
            # 🔥 OTIMIZADO: Cooldown maior no finally
            cooldown_final = random.uniform(20.0, 35.0)
            self._log(f"⏳ Cooldown final de {cooldown_final:.1f}s...")
            time.sleep(cooldown_final)

            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                # 🔥 NOVO — Aguardar mais tempo após fechar navegador
                time.sleep(random.uniform(5.0, 10.0))

    # ------------------------------------------------------
    #                     PASSO 1
    # ------------------------------------------------------
    def _passo1(self):
        # 🔥 NOVO — Verificar stop_flag antes de começar
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")
        
        w = self.wait_dropdown

        try:
            w.until(EC.element_to_be_clickable((By.CLASS_NAME, "rw-dropdown-list-input"))).click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em dropdown: {e}")
        
        delay_humano(0.15, 0.30)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            w.until(EC.element_to_be_clickable((By.XPATH, "//li[text()='DENTAL']"))).click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao selecionar DENTAL: {e}")
        
        delay_humano(0.15, 0.25)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            selects = w.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "rw-btn-select")))
            selects[1].click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em selects: {e}")
        
        delay_humano(0.15, 0.25)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            plano = w.until(EC.presence_of_element_located((By.XPATH, "//li[text()='Amil Dental Nacional']")))
            self.driver.execute_script("arguments[0].click();", plano)
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao selecionar plano: {e}")
        
        delay_humano(0.18, 0.28)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "test_btn_firststep_submit")))
            self.driver.execute_script("arguments[0].click();", btn)
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em botão submit: {e}")
        
        delay_humano(0.18, 0.28)

    def _escape_xpath_text(self, text: str) -> str:
        """Permite usar texto com apóstrofos no XPATH."""
        if "'" not in text:
            return f"'{text}'"
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

    # ------------------------------------------------------
    #                     PASSO 2
    # ------------------------------------------------------
    def _passo2(self, cidade: str):
        # 🔥 NOVO — Verificar stop_flag antes de começar
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")
        
        w = self.wait_dropdown

        try:
            estado = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Estado')]/following::button[1]")))
            estado.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em Estado: {e}")
        
        delay_humano(0.15, 0.25)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            uf_op = w.until(EC.element_to_be_clickable((By.XPATH, f"//li[text()='{self.uf}']")))
            uf_op.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao selecionar UF {self.uf}: {e}")
        
        delay_humano(0.16, 0.28)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            muni = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Municipio')]/following::button[1]")))
            muni.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em Município: {e}")
        
        delay_humano(0.15, 0.25)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        xpath_cidade = self._escape_xpath_text(cidade)
        try:
            cidade_op = w.until(
                EC.element_to_be_clickable((By.XPATH, f"//li[text()={xpath_cidade}]"))
            )
            cidade_op.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao selecionar cidade {cidade}: {e}")
        
        delay_humano(0.16, 0.28)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            bairro = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Bairro')]/following::button[1]")))
            bairro.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em Bairro: {e}")
        
        delay_humano(0.15, 0.25)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            todos = w.until(EC.element_to_be_clickable((By.XPATH, "//li[text()='TODOS OS BAIRROS']")))
            todos.click()
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao selecionar TODOS OS BAIRROS: {e}")
        
        delay_humano(0.18, 0.30)
        
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        try:
            cont = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.test_btn_secondstep_submit")))
            self.driver.execute_script("arguments[0].click();", cont)
        except Exception as e:
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            raise Exception(f"Erro ao clicar em botão continuar: {e}")
        
        delay_humano(0.20, 0.35)

    # ------------------------------------------------------
    #                     PASSO 3
    # ------------------------------------------------------
    def _passo3(self, cidade: str):
        w = self.wait_dropdown

        btn = w.until(
            EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Especialidade')]/following::button[1]"))
        )
        btn.click()
        delay_humano(0.15, 0.25)

        w.until(EC.presence_of_element_located((By.XPATH, "//ul[contains(@id,'listbox')]//li")))

        candidatos = [
            "//li[text()='CLINICA GERAL']",
            "//li[contains(text(),'CLÍNICA GERAL')]",
            "//li[contains(text(),'CLINICA GERAL')]",
        ]

        op = None
        for xp in candidatos:
            try:
                op = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                break
            except:
                continue

        if not op:
            self._log(f"⚠️ Especialidade não encontrada em {cidade}-{self.uf}")
            gerar_pdf_sem_especialidade(self.uf, cidade, self.pasta_base)
            raise Exception("Especialidade não encontrada")

        self.driver.execute_script("arguments[0].scrollIntoView();", op)
        delay_humano(0.15, 0.25)

        try:
            op.click()
        except:
            self.driver.execute_script("arguments[0].click();", op)

        delay_humano(0.20, 0.30)

    # ------------------------------------------------------
    #          BUSCAR + CAPTURAR RESULTADOS
    # ------------------------------------------------------
    def _capturar(self) -> list[dict]:
        """
        Tentativa REAL inicial (tempo padrão).
        Se falhar, entra no retry com restart progressivo.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        import time as time_module
        
        # 🔥 NOVO — Timeout máximo total para evitar travamento infinito
        inicio_captura = time_module.time()
        timeout_maximo_total = 180  # 3 minutos máximo para toda a captura
        
        # 🔥 NOVO — Verificar stop_flag no início
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")

        # ============================================================
        #   TENTATIVA INICIAL (SEM FECHAR O NAVEGADOR)
        # ============================================================
        self._log("🔍 Tentativa inicial (sem restart)...")

        try:
            # 🔥 NOVO — Verificar timeout máximo
            if time_module.time() - inicio_captura > timeout_maximo_total:
                raise Exception("Timeout máximo atingido na captura")
            
            # Verificar bloqueio antes de buscar
            if self._verificar_bloqueio():
                self._log("⚠️ Bloqueio detectado antes de buscar!")
                raise Exception("Bloqueio detectado")

            # 🔥 NOVO — Verificar stop_flag antes de clicar
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")

            # 🔥 CORREÇÃO — Timeout menor e verificação de stop_flag durante espera
            try:
                btn = WebDriverWait(self.driver, 10).until(
                    lambda d: (
                        self.stop_flag.is_set() if self.stop_flag and self.stop_flag.is_set() else
                        EC.element_to_be_clickable((By.CLASS_NAME, "test_btn_thirdstep_submit"))(d)
                    )
                )
                if self.stop_flag and self.stop_flag.is_set():
                    raise Exception("Execução interrompida pelo usuário")
            except Exception as e:
                if "interrompida" in str(e):
                    raise
                # Se não encontrou o botão, tentar encontrar de outra forma
                try:
                    btn = self.driver.find_element(By.CLASS_NAME, "test_btn_thirdstep_submit")
                except:
                    raise Exception("Botão de buscar não encontrado")
            
            # Movimento de mouse antes de clicar
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(btn).perform()
                time.sleep(random.uniform(0.3, 0.7))
            except:
                pass
            
            # 🔥 NOVO — Verificar stop_flag antes de clicar
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            self.driver.execute_script("arguments[0].click();", btn)

            self._log("⏳ Aguardando resultados aparecerem...")

            # Aguardar mais tempo para JavaScript carregar
            time.sleep(random.uniform(3.0, 5.0))

            # 🔥 NOVO — Verificar stop_flag durante espera
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            # 🔥 NOVO — Verificar timeout máximo
            if time_module.time() - inicio_captura > timeout_maximo_total:
                raise Exception("Timeout máximo atingido na captura")

            # Verificar bloqueio após buscar
            if self._verificar_bloqueio():
                self._log("⚠️ Bloqueio detectado após buscar!")
                raise Exception("Bloqueio após buscar")

            # 🔥 NOVO — Aguardar um pouco mais para JavaScript carregar
            time.sleep(2)

            # 🔥 NOVO — Verificar se há mensagem de "sem resultados"
            try:
                # Verificar se aparece mensagem de "nenhum resultado encontrado"
                mensagens_sem_resultado = [
                    "//*[contains(text(), 'nenhum resultado')]",
                    "//*[contains(text(), 'Nenhum resultado')]",
                    "//*[contains(text(), 'não encontrado')]",
                    "//*[contains(text(), 'Não encontrado')]",
                ]
                for xpath in mensagens_sem_resultado:
                    try:
                        elemento = self.driver.find_element(By.XPATH, xpath)
                        if elemento.is_displayed():
                            self._log("⚠️ Site retornou mensagem de 'sem resultados'")
                            return []
                    except:
                        pass
            except:
                pass

            # 🔥 CORREÇÃO — Timeout menor e verificação de stop_flag
            try:
                WebDriverWait(self.driver, 15).until(  # Reduzido de 20 para 15
                    lambda d: (
                        self.stop_flag.is_set() if self.stop_flag and self.stop_flag.is_set() else
                        EC.any_of(
                            EC.presence_of_element_located((By.ID, "result-legend")),
                            EC.presence_of_element_located((By.CLASS_NAME, "accredited-network__result")),
                        )(d)
                    )
                )
                if self.stop_flag and self.stop_flag.is_set():
                    raise Exception("Execução interrompida pelo usuário")
            except Exception as e:
                if "interrompida" in str(e):
                    raise
                self._log("⚠️ Timeout aguardando indicadores de resultado")

            # 🔥 NOVO — Fazer scroll para carregar resultados (scroll infinito)
            try:
                # Scroll até o final da página para carregar todos os resultados
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scrolls = 5
                
                while scroll_attempts < max_scrolls:
                    # 🔥 NOVO — Verificar timeout máximo e stop_flag durante scroll
                    if time_module.time() - inicio_captura > timeout_maximo_total:
                        self._log("⚠️ Timeout máximo atingido durante scroll")
                        break
                    
                    if self.stop_flag and self.stop_flag.is_set():
                        raise Exception("Execução interrompida pelo usuário")
                    
                    # Scroll para baixo
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)  # Aguardar carregar
                    
                    # Verificar se a página cresceu (novos resultados carregados)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break  # Não há mais conteúdo para carregar
                    last_height = new_height
                    scroll_attempts += 1
                
                # Scroll de volta para o topo
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
            except Exception as e:
                if "interrompida" in str(e):
                    raise
                self._log(f"⚠️ Erro ao fazer scroll: {e}")

            # 🔥 CORREÇÃO — Timeout menor e não bloquear se não encontrar
            try:
                WebDriverWait(self.driver, 10).until(  # Reduzido de 20 para 10
                    lambda d: (
                        self.stop_flag.is_set() if self.stop_flag and self.stop_flag.is_set() else
                        EC.presence_of_element_located((By.CLASS_NAME, "accredited-network__result"))(d)
                    )
                )
                if self.stop_flag and self.stop_flag.is_set():
                    raise Exception("Execução interrompida pelo usuário")
            except Exception as e:
                if "interrompida" in str(e):
                    raise
                self._log("⚠️ Timeout aguardando blocos de resultado - continuando mesmo assim")

            # 🔥 NOVO — Tentar múltiplos seletores (caso a classe tenha mudado)
            blocos = []
            seletores = [
                (By.CLASS_NAME, "accredited-network__result"),
                (By.CSS_SELECTOR, "[class*='accredited-network']"),
                (By.CSS_SELECTOR, "[class*='result']"),
            ]
            
            for by, selector in seletores:
                try:
                    blocos = self.driver.find_elements(by, selector)
                    if blocos:
                        self._log(f"✅ Encontrados {len(blocos)} blocos com seletor: {selector}")
                        break
                except:
                    continue

            # 🔥 NOVO — Debug: salvar screenshot se não encontrar resultados
            if not blocos:
                try:
                    screenshot_path = f"debug_no_results_{self.uf}_{self._current_city}.png"
                    self.driver.save_screenshot(screenshot_path)
                    self._log(f"📸 Screenshot salvo para debug: {screenshot_path}")
                    
                    # Salvar HTML da página para análise
                    html_path = f"debug_no_results_{self.uf}_{self._current_city}.html"
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    self._log(f"📄 HTML salvo para debug: {html_path}")
                except:
                    pass

            if blocos:
                self._log(f"✅ Resultados carregados na tentativa inicial ({len(blocos)} blocos).")
                return self._extrair_prestadores(blocos)

            # nenhum bloco, mas tentativa feita → cai para retry
            self._log("⚠️ Nenhum bloco encontrado na tentativa inicial.")

        except Exception as e:
            # Se foi interrompido, não fazer retry
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            # 🔥 NOVO — Se timeout máximo atingido, não fazer retry
            if "Timeout máximo" in str(e):
                self._log(f"⏱️ {e}")
                return []
            
            self._log(f"⚠️ Tentativa inicial falhou: {e}")

        # =====================================================================
        # SE CHEGOU AQUI → iniciar ciclo de retry com restart
        # =====================================================================
        # 🔥 NOVO — Verificar timeout máximo antes de iniciar retry
        if time_module.time() - inicio_captura > timeout_maximo_total:
            self._log("⏱️ Timeout máximo atingido - não fazendo mais tentativas")
            return []
        
        # 🔥 NOVO — Verificar stop_flag antes de iniciar retry
        if self.stop_flag and self.stop_flag.is_set():
            raise Exception("Execução interrompida pelo usuário")
        
        self._log("🔁 Iniciando tentativas com restart progressivo...")

        from selenium.webdriver.common.by import By

        tentativas = [15, 25, 45, 60]  # 🔥 Aumentado tempos de espera

        for idx, espera in enumerate(tentativas, start=1):
            # 🔥 NOVO — Verificar timeout máximo antes de cada tentativa
            if time_module.time() - inicio_captura > timeout_maximo_total:
                self._log(f"⏱️ Timeout máximo atingido após {idx-1} tentativas")
                return []
            
            # 🔥 NOVO — Verificar stop_flag antes de cada tentativa
            if self.stop_flag and self.stop_flag.is_set():
                raise Exception("Execução interrompida pelo usuário")
            
            # ... resto do código de retry ...


    def _extrair_prestadores(self, blocos):
        prestadores = []
        from selenium.webdriver.common.by import By

        for b in blocos:
            try: 
                nome = b.find_element(By.TAG_NAME, "h3").text.strip()
            except: 
                nome = "NOME NÃO ENCONTRADO"

            try: 
                endereco = b.find_element(
                    By.CSS_SELECTOR,
                    ".accredited-network__result__address-name p:nth-child(1)"
                ).text.strip()
            except: 
                endereco = "ENDEREÇO NÃO ENCONTRADO"

            try: 
                bairro = b.find_element(
                    By.CSS_SELECTOR,
                    ".accredited-network__result__neighbourhood p"
                ).text.strip()
            except: 
                bairro = "BAIRRO NÃO ENCONTRADO"

            try: 
                telefone = b.find_element(
                    By.CSS_SELECTOR,
                    ".accredited-network__result__address-name p:nth-child(3)"
                ).text.strip()
            except: 
                telefone = "TELEFONE NÃO ENCONTRADO"

            # 🔥 VALIDAÇÃO: só adiciona se for prestador válido
            textos_invalidos = [
                "NOME NÃO ENCONTRADO",
                "ENDEREÇO NÃO ENCONTRADO",
                "Sua busca não localizou nenhum prestador",
                "nenhum prestador",
                "Nenhum prestador",
                "Legenda de ícones",
                "",
            ]
            
            # Validar se é prestador válido
            if (nome not in textos_invalidos and 
                endereco not in textos_invalidos and
                len(nome) > 3 and
                len(endereco) > 5):
                
                prestadores.append({
                    "nome": nome,
                    "endereco": endereco,
                    "bairro": bairro if bairro != "BAIRRO NÃO ENCONTRADO" else "",
                    "telefone": telefone if telefone != "TELEFONE NÃO ENCONTRADO" else "",
                })

        return prestadores
import random
import time
from pathlib import Path
from typing import Any

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
    ) -> None:

        self.uf = uf
        self.pasta_base = pasta_base or REDE_COMPLETA_DIR
        self.logger = logger

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
        """Cooldown curto entre cidades para parecer humano."""
        time.sleep(random.uniform(1.8, 3.8))

        if not self.driver:
            return

        # movimentos aleatórios
        for _ in range(random.randint(2, 4)):
            try:
                x = random.randint(0, 400)
                y = random.randint(0, 400)
                self.driver.execute_script(f"window.scrollTo({x}, {y});")
                time.sleep(random.uniform(0.15, 0.35))
            except:
                pass

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

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        self.wait = WebDriverWait(self.driver, 25)
        self.wait_dropdown = WebDriverWait(self.driver, 15)

        apply_stealth(self.driver)

        time.sleep(0.05)

        self.driver.get(
            "https://www.amil.com.br/institucional/#/servicos/saude/rede-credenciada/amil/busca-avancada"
        )

        aguardar_pagina_carregar(self.driver, self.wait)

        try:
            self.wait.until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            ).click()
        except:
            pass

        try:
            self.driver.maximize_window()
        except:
            pass

    # ------------------------------------------------------
    #                   PROCESSAR CIDADE
    # ------------------------------------------------------
    def processar_cidade(self, cidade: str) -> None:

        caminho_pdf = get_pdf_path(self.uf, cidade, self.pasta_base)
        if caminho_pdf.exists():
            self._log(f"⏭️ PDF já existe — pulando {cidade}-{self.uf}")
            time.sleep(random.uniform(0.5, 1.1))
            return

        self._log(f"\n🔄 Processando {cidade}-{self.uf}")
        self._current_city = cidade

        # navegador limpo sempre
        self._abrir_navegador()

        try:
            self._passo1()
            self._passo2(cidade)
            self._passo3(cidade)
            prestadores = self._capturar()

            if prestadores:
                gerar_pdf_prestadores(self.uf, cidade, prestadores, self.pasta_base)
                self._log(f"📄 PDF gerado: {cidade}-{self.uf}")
            else:
                self._log(f"⚠️ Sem prestadores em {cidade}-{self.uf}")

        except Exception as e:
            self._log(f"⚠️ Falha em {cidade}-{self.uf}: {e}")
            self._log("🛑 Fechando navegador antes do cooldown...")

            # FECHAR navegador imediatamente
            try:
                if self.driver:
                    self.driver.quit()
            except:
                pass
            finally:
                self.driver = None
                self.wait = None
                self.wait_dropdown = None

            # AGORA SIM: cooldown humano com navegador fechado
            cooldown = 10
            self._log(f"⏳ Aguardando {cooldown} segundos para limpar fingerprint...")
            time.sleep(cooldown)

            # REABRIR navegador limpo
            self._log("🔁 Reabrindo navegador e tentando novamente...")

            try:
                return self.processar_cidade(cidade)  # retry real
            except Exception as e2:
                self._log(f"❌ Falha definitiva em {cidade}-{self.uf}: {e2}")
                self.cidades_com_erro.setdefault(self.uf, []).append(cidade)

        finally:
            self._cooldown()

            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None

    # ------------------------------------------------------
    #                     PASSO 1
    # ------------------------------------------------------
    def _passo1(self):
        w = self.wait_dropdown

        w.until(EC.element_to_be_clickable((By.CLASS_NAME, "rw-dropdown-list-input"))).click()
        delay_humano(0.15, 0.30)

        w.until(EC.element_to_be_clickable((By.XPATH, "//li[text()='DENTAL']"))).click()
        delay_humano(0.15, 0.25)

        selects = w.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "rw-btn-select")))
        selects[1].click()
        delay_humano(0.15, 0.25)

        plano = w.until(EC.presence_of_element_located((By.XPATH, "//li[text()='Amil Dental Nacional']")))
        self.driver.execute_script("arguments[0].click();", plano)
        delay_humano(0.18, 0.28)

        btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "test_btn_firststep_submit")))
        self.driver.execute_script("arguments[0].click();", btn)
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
        w = self.wait_dropdown

        estado = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Estado')]/following::button[1]")))
        estado.click()
        delay_humano(0.15, 0.25)

        uf_op = w.until(EC.element_to_be_clickable((By.XPATH, f"//li[text()='{self.uf}']")))
        uf_op.click()
        delay_humano(0.16, 0.28)

        muni = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Municipio')]/following::button[1]")))
        muni.click()
        delay_humano(0.15, 0.25)

        xpath_cidade = self._escape_xpath_text(cidade)
        cidade_op = w.until(
            EC.element_to_be_clickable((By.XPATH, f"//li[text()={xpath_cidade}]"))
        )
        cidade_op.click()
        delay_humano(0.16, 0.28)

        bairro = w.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(text(),'Bairro')]/following::button[1]")))
        bairro.click()
        delay_humano(0.15, 0.25)

        todos = w.until(EC.element_to_be_clickable((By.XPATH, "//li[text()='TODOS OS BAIRROS']")))
        todos.click()
        delay_humano(0.18, 0.30)

        cont = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.test_btn_secondstep_submit")))
        self.driver.execute_script("arguments[0].click();", cont)
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

        # ============================================================
        #   TENTATIVA INICIAL (SEM FECHAR O NAVEGADOR)
        # ============================================================
        self._log("🔍 Tentativa inicial (sem restart)...")

        try:
            btn = self.wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "test_btn_thirdstep_submit"))
            )
            self.driver.execute_script("arguments[0].click();", btn)

            self._log("⏳ Aguardando resultados aparecerem...")

            # 1) Aguardar qualquer sinal (resultado ou mensagem)
            WebDriverWait(self.driver, 18).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "result-legend")),
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "accredited-network__result")
                    ),
                )
            )

            # 2) Aguardar blocos reais
            WebDriverWait(self.driver, 18).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "accredited-network__result")
                )
            )

            blocos = self.driver.find_elements(
                By.CLASS_NAME, "accredited-network__result"
            )

            if blocos:
                self._log(f"✅ Resultados carregados na tentativa inicial ({len(blocos)} blocos).")
                return self._extrair_prestadores(blocos)

            # nenhum bloco, mas tentativa feita → cai para retry
            self._log("⚠️ Nenhum bloco encontrado na tentativa inicial.")

        except Exception as e:
            self._log(f"⚠️ Tentativa inicial falhou: {e}")

        # =====================================================================
        # SE CHEGOU AQUI → iniciar ciclo de retry com restart
        # =====================================================================
        self._log("🔁 Iniciando tentativas com restart progressivo...")

        from selenium.webdriver.common.by import By

        tentativas = [10, 20, 40, 60]

        for idx, espera in enumerate(tentativas, start=1):
            self._log(f"🔄 Tentativa {idx}/4 — timeout={espera}s, reiniciando navegador...")

            # ---------------- FECHAR NAVEGADOR ----------------
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None

            # ---------------- COOLDOWN ----------------
            time.sleep(espera)

            # ---------------- ABRIR NOVO NAVEGADOR ----------------
            self._abrir_navegador()

            try:
                # refazer passos
                self._passo1()
                self._passo2(self._current_city)
                self._passo3(self._current_city)

                # clicar buscar
                btn = self.wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "test_btn_thirdstep_submit"))
                )
                self.driver.execute_script("arguments[0].click();", btn)

                self._log("⏳ Aguardando resultados aparecerem...")

                # Aguardar qualquer indicador
                WebDriverWait(self.driver, espera).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "result-legend")),
                        EC.presence_of_element_located(
                            (By.CLASS_NAME, "accredited-network__result")
                        ),
                    )
                )

                # Aguardar blocos reais
                WebDriverWait(self.driver, espera).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "accredited-network__result")
                    )
                )

                blocos = self.driver.find_elements(
                    By.CLASS_NAME, "accredited-network__result"
                )

                if blocos:
                    self._log(f"✅ Sucesso na tentativa {idx} ({len(blocos)} blocos).")
                    return self._extrair_prestadores(blocos)

                self._log(f"⚠️ Tentativa {idx}: sem blocos.")

            except Exception as e:
                self._log(f"❌ Tentativa {idx} falhou: {e}")

        # =====================================================================
        # Se nenhuma tentativa deu certo
        # =====================================================================
        raise Exception("❌ Todas as tentativas falharam (com restart).")


        return prestadores


    def _extrair_prestadores(self, blocos):
        prestadores = []
        from selenium.webdriver.common.by import By

        for b in blocos:
            try: nome = b.find_element(By.TAG_NAME, "h3").text.strip()
            except: nome = "NOME NÃO ENCONTRADO"

            try: endereco = b.find_element(
                By.CSS_SELECTOR,
                ".accredited-network__result__address-name p:nth-child(1)"
            ).text.strip()
            except: endereco = "ENDEREÇO NÃO ENCONTRADO"

            try: bairro = b.find_element(
                By.CSS_SELECTOR,
                ".accredited-network__result__neighbourhood p"
            ).text.strip()
            except: bairro = "BAIRRO NÃO ENCONTRADO"

            try: telefone = b.find_element(
                By.CSS_SELECTOR,
                ".accredited-network__result__address-name p:nth-child(3)"
            ).text.strip()
            except: telefone = "TELEFONE NÃO ENCONTRADO"

            prestadores.append({
                "nome": nome,
                "endereco": endereco,
                "bairro": bairro,
                "telefone": telefone,
            })

        return prestadores
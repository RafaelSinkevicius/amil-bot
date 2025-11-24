import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def fechar_abas_extras(driver) -> None:
    """
    Fecha todas as abas, exceto a primeira.
    """
    try:
        janelas = driver.window_handles
        if len(janelas) > 1:
            for i in range(len(janelas) - 1, 0, -1):
                driver.switch_to.window(janelas[i])
                driver.close()
            driver.switch_to.window(janelas[0])
            time.sleep(0.5)
    except Exception as e:
        print(f"⚠️ Aviso ao fechar abas extras: {e}")


def garantir_aba_principal(driver) -> None:
    """
    Garante que estamos na aba principal (primeira).
    """
    try:
        janelas = driver.window_handles
        if len(janelas) > 0:
            driver.switch_to.window(janelas[0])
    except Exception as e:
        print(f"⚠️ Aviso ao garantir aba principal: {e}")


def aguardar_pagina_carregar(driver, wait: WebDriverWait) -> None:
    """
    Aguarda o carregamento completo da página (document.readyState == 'complete').
    """
    try:
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(0.5)
    except Exception as e:
        print(f"⚠️ Aviso ao aguardar carregamento: {e}")


def clicar_com_retry(locator, driver, wait: WebDriverWait, max_tentativas: int = 3) -> bool:
    """
    Tenta clicar em um elemento algumas vezes antes de desistir.
    """
    for tentativa in range(max_tentativas):
        try:
            elemento = wait.until(EC.element_to_be_clickable(locator))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            elemento.click()
            return True
        except Exception:
            if tentativa == max_tentativas - 1:
                raise
            time.sleep(0.5)
    return False
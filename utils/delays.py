import time
import random


def delay_humano(min_seg: float = 0.5, max_seg: float = 2.0) -> None:
    """Delay aleatório para simular comportamento humano."""
    time.sleep(random.uniform(min_seg, max_seg))


def pausa_estrategica(contador_cidades: int,
                      intervalo: int = 10,  # 🔥 REDUZIDO: a cada 10 cidades
                      pausa_base: int = 60,  # 🔥 AUMENTADO: 60 segundos base
                      pausa_max: int = 300) -> None:  # 🔥 NOVO: máximo 5 minutos
    """
    A cada `intervalo` cidades, faz uma pausa maior para ajudar a driblar bloqueios.
    Pausa aumenta progressivamente.
    """
    if contador_cidades and contador_cidades % intervalo == 0:
        # 🔥 NOVO — Pausa progressiva: aumenta com o número de cidades
        pausa_extra = min((contador_cidades // intervalo) * 30, pausa_max - pausa_base)
        pausa_total = pausa_base + pausa_extra
        
        print(f"♻️ Pausa estratégica ({contador_cidades} cidades processadas): {pausa_total}s para reiniciar sessão...")
        time.sleep(pausa_total)
        print("✅ Pausa concluída, continuando...")
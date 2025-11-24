import time
import random


def delay_humano(min_seg: float = 0.5, max_seg: float = 2.0) -> None:
    """Delay aleatório para simular comportamento humano."""
    time.sleep(random.uniform(min_seg, max_seg))


def pausa_estrategica(contador_cidades: int,
                      intervalo: int = 15,
                      pausa_seg: int = 15) -> None:
    """
    A cada `intervalo` cidades, faz uma pausa maior para ajudar a driblar bloqueios.
    """
    if contador_cidades and contador_cidades % intervalo == 0:
        print("♻️ Pausa estratégica para reiniciar sessão e driblar bloqueios...")
        time.sleep(pausa_seg)
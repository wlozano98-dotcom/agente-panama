"""Interruptor del aprendizaje nivel 2 (Andrés, 2026-10-26: todo listo pero APAGADO hasta el lanzamiento, porque lo
corregido y decidido hasta hoy son pruebas). Vive en D1 (tabla `config`, clave "aprendizaje") para que lo lean la
oficina (el Worker no guarda correcciones si está apagado) y la Mac (los agentes no las usan). Al encender se anota
"desde": solo cuenta lo corregido o decidido a partir de ese momento.

Uso: python3 cerebro/aprendizaje.py [estado | encender | apagar]
     python3 cerebro/aprendizaje.py encender <agente> [desde AAAA-MM-DD]     (solo un agente, p. ej. monitor = Paula)
     python3 cerebro/aprendizaje.py apagar <agente>
Por agente (Andrés, 2026-10-26: "solo préndelo para Paula"): clave "aprendizaje:<agente>" en config; para_agente()
mira primero la del agente y si no hay, la general.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT, actualizado TEXT)")


def estado():
    """{"activo": bool, "desde": "AAAA-MM-DDTHH:MM:SS" en UTC | None} (las correcciones
    del Worker están en UTC; las normas, en hora de Panamá: restar 5 horas); apagado si no hay nada o la base no responde."""
    try:
        f = d1.consulta("SELECT valor FROM config WHERE clave = 'aprendizaje'")
        return json.loads(f[0]["valor"]) if f else {"activo": False, "desde": None}
    except Exception:
        return {"activo": False, "desde": None}


def poner(activo):
    crear_tabla()
    import datetime
    valor = {"activo": activo, "desde": datetime.datetime.utcnow().isoformat(timespec="seconds") if activo else None}
    d1.consulta("INSERT OR REPLACE INTO config (clave, valor, actualizado) VALUES ('aprendizaje', ?, ?)",
                [json.dumps(valor), cerebro.ahora()])
    return valor


def para_agente(agente):
    """El interruptor que vale para un agente: el suyo si existe; si no, el general."""
    try:
        f = d1.consulta("SELECT valor FROM config WHERE clave = ?", [f"aprendizaje:{agente}"])
        if f:
            return json.loads(f[0]["valor"])
    except Exception:
        pass
    return estado()


def poner_agente(agente, activo, desde=None):
    crear_tabla()
    import datetime
    valor = {"activo": activo, "desde": (desde or datetime.datetime.utcnow().isoformat(timespec="seconds")) if activo else None}
    d1.consulta("INSERT OR REPLACE INTO config (clave, valor, actualizado) VALUES (?, ?, ?)",
                [f"aprendizaje:{agente}", json.dumps(valor), cerebro.ahora()])
    return valor


if __name__ == "__main__":
    cerebro.cargar_env()
    orden = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if len(sys.argv) > 2 and orden in ("encender", "apagar"):
        print(sys.argv[2], poner_agente(sys.argv[2], orden == "encender", sys.argv[4] if len(sys.argv) > 4 else None))
    elif orden == "encender":
        print("Aprendizaje ENCENDIDO desde", poner(True)["desde"], "(UTC)")
    elif orden == "apagar":
        poner(False)
        print("Aprendizaje apagado")
    else:
        print(estado())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ═════════════════════════════════════════════════════════════════════════════
# CORRECTOR EMPRESAULA - Gestión Comercial ODOO
# Módulo de Compras, Ventas e Inventario
# Ciclo Formativo: Administración y Finanzas
# ═════════════════════════════════════════════════════════════════════════════


import csv
import pandas as pd
import os
import sys
import re
from datetime import datetime, date, timedelta
from io import StringIO

# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE CONSOLA (sin dependencias externas)
# ═════════════════════════════════════════════════════════════════════════════

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

def c(text, color):
    return f"{color}{text}{Color.RESET}"

def ok(msg):
    print(f"  {c('✓', Color.GREEN)} {msg}")

def err(msg):
    print(f"  {c('✗', Color.RED)} {msg}")


def warn(msg):
    print(f"  {c('⚠', Color.YELLOW)} {msg}")


def info(msg):
    print(f"  {c('·', Color.CYAN)} {msg}")


def header(title):
    w = 66
    print()
    print(c("═" * w, Color.BLUE))
    print(c(f"  {title}", Color.BOLD + Color.WHITE))
    print(c("═" * w, Color.BLUE))


def subheader(title):
    print(f"\n{c('─'*50, Color.GRAY)}")
    print(c(f"  {title}", Color.CYAN + Color.BOLD))
    print(c("─" * 50, Color.GRAY))


def separador():
    print(c("·" * 50, Color.GRAY))


# ═════════════════════════════════════════════════════════════════════════════
# CARREGA DE DADES
# ═════════════════════════════════════════════════════════════════════════════

def normalizar_importe(valor):
    # Converteix imports amb coma decimal o punt decimal a float
    if pd.isna(valor):
        return 0.0
    # Elimina cometes dobles i espais
    s = str(valor).strip().replace('"',"").replace(" ", "")
    # Format europeu: 1.314,06 -> 1314.06
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0
        

def normalizar_fecha(valor, formatos=None):
    # Parsea fechas en multiples formatos
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    s = str(valor).strip()
    if formatos is None:
        formatos = ["%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(
                s[
                    :
                        len(
                            fmt.replace("%Y", "2000")
                            .replace("%m", "01")
                            .replace("%d", "01")
                            .replace("%H", "00")
                            .replace("%M", "00")
                            .replace("%S", "00")
                        )
                    ],
                    fmt,
                ).date()
        except:
            pass
    # Intentam format automatic PANDAS
    try:
        return pd.to_datetime(s).date()
    except:
        return None


def extraer_expediente(nombre_empresa):
    # Extreu el num. d'expedient del nom de l'empresa: Ej: 'ADG32 5796 NSACARES SL' → '5796'
    if pd.isna(nombre_empresa):          # Consistente con normalizar_fecha
        return None
    m = re.search(r"\b(\d{4,5})\b", str(nombre_empresa))
    if m:
        return m.group(1)
    else:
        return None   # None facilita detección de fallos
  


def leer_csv(ruta, separador=","):
    # llegeix un CSV tenint en compte "comillas" i separadors especials
    try:
        df = pd.read_csv(
            ruta,
            sep=separador,
            encoding="utf-8",
            dtype=str,
            quotechar='"',
            skipinitialspace=True,
        )
        # Netejar noms de columnes
        df.columns = df.columns.str.strip().str.replace('"', "")
        return df
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(
                ruta,
                sep=separador,
                encoding="latin-1",
                dtype=str,
                quotechar='"',
                skipinitialspace=True,
            )
            df.columns = df.columns.str.strip().str.replace('"', "")
            return df
        except Exception as e:
            print(c(f"     ERROR leyendo {ruta}: {e}", Color.RED))
            return None
    except Exception as e:
        print(c(f"     ERROR leyendo {ruta}: {e}", Color.RED))
        return None


# ═════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL: CORRECTOR
# ═════════════════════════════════════════════════════════════════════════════

class CorrectorEmpresaula:

    def __init__(self, directorio="."):
        self.dir = directorio
        self.errores_total = 0
        self.avisos_total = 0
        self.correctos_total = 0
        self.resumen_por_alumno = {}
    
    def _ruta(self, nombre):
        return os.path.join(self.dir, nombre)
    
    def _registrar(self, empresa, tipo, mensaje, nivel="error"):
        exp = extraer_expediente(empresa)
        if exp not in self.resumen_por_alumno:
            self.resumen_por_alumno[exp] = {
                "empresa": empresa,
                "errores": [],
                "avisos": [],
                "ok": [],
            }
        if nivel == "error":
            self.resumen_por_alumno[exp]["errores"].append(f"[{tipo}] {mensaje}")
            self.errores_total += 1
        elif nivel == "aviso":
            self.resumen_por_alumno[exp]["avisos"].append(f"[{tipo}] {mensaje}")
            self.avisos_total += 1
        else:
            self.resumen_por_alumno[exp]["ok"].append(f"[{tipo}] {mensaje}")
            self.correctos_total += 1

        # ------------------------------------------------------
        # MODULO 1: COMPRAS
        # ------------------------------------------------------


        def corregir_compras(self, fecha_entrega_str=None):
            header("MÓDULO 1: CORRECCIÓN DE COMPRAS")

    

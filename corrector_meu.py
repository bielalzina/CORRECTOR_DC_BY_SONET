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
        



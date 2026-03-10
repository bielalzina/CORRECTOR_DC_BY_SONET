#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ═════════════════════════════════════════════════════════════════════════════
# CORRECTOR EMPRESAULA - Gestión Comercial ODOO
# Módulo de Compras, Ventas e Inventario
# Ciclo Formativo: Administración y Finanzas
# ═════════════════════════════════════════════════════════════════════════════

import pandas as pd
import csv
import os
import sys
import re
from datetime import datetime, date, timedelta
from io import StringIO

# ══════════════════════════════════════════════════════════════
# UTILIDADES DE CONSOLA (sin dependencias externas)
# ══════════════════════════════════════════════════════════════

class Color:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BG_RED  = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'

def c(text, color): return f"{color}{text}{Color.RESET}"
def ok(msg):    print(f"  {c('✓', Color.GREEN)} {msg}")
def err(msg):   print(f"  {c('✗', Color.RED)} {msg}")
def warn(msg):  print(f"  {c('⚠', Color.YELLOW)} {msg}")
def info(msg):  print(f"  {c('·', Color.CYAN)} {msg}")

def header(title):
    w = 66
    print()
    print(c('═' * w, Color.BLUE))
    print(c(f"  {title}", Color.BOLD + Color.WHITE))
    print(c('═' * w, Color.BLUE))

def subheader(title):
    print(f"\n{c('─'*50, Color.GRAY)}")
    print(c(f"  {title}", Color.CYAN + Color.BOLD))
    print(c('─'*50, Color.GRAY))

def separador():
    print(c('·'*50, Color.GRAY))


# ══════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════

def normalizar_importe(valor):
    """Convierte importes con coma decimal o punto a float."""
    if pd.isna(valor):
        return 0.0
    s = str(valor).strip().replace('"', '').replace(' ', '')
    # Formato europeo: 1.314,06 → 1314.06
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

def normalizar_fecha(valor, formatos=None):
    """Parsea fechas en múltiples formatos."""
    if pd.isna(valor) or str(valor).strip() == '':
        return None
    s = str(valor).strip()
    if formatos is None:
        formatos = ['%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y']
    for fmt in formatos:
        try:
            return datetime.strptime(
                s[
                    :
                        len(
                            fmt.replace('%Y','2000')
                            .replace('%m','01')
                            .replace('%d','01')
                            .replace('%H','00')
                            .replace('%M','00')
                            .replace('%S','00')
                        )
                    ],
                    fmt,
                ).date()
        except:
            pass
    # Intentar pandas
    try:
        return pd.to_datetime(s).date()
    except:
        return None

def extraer_expediente(nombre_empresa):
    """Extrae el número de expediente del nombre de la empresa. Ej: 'ADG32 5796 NSACARES SL' → '5796'"""
    m = re.search(r'\b(\d{4,5})\b', str(nombre_empresa))
    return m.group(1) if m else str(nombre_empresa)











def leer_csv(ruta, separador=','):
    """Lee un CSV manejando comillas y separadores especiales."""
    try:
        df = pd.read_csv(
            ruta, 
            sep=separador, 
            encoding='utf-8', 
            dtype=str,
            quotechar='"', 
            skipinitialspace=True,
        )
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip().str.replace('"', '')
        return df
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(
                ruta, 
                sep=separador, 
                encoding='latin-1', 
                dtype=str,
                quotechar='"', 
                skipinitialspace=True,
            )
            df.columns = df.columns.str.strip().str.replace('"', '')
            return df
        except Exception as e:
            print(c(f"    ERROR leyendo {ruta}: {e}", Color.RED))
            return None
    except Exception as e:
        print(c(f"    ERROR leyendo {ruta}: {e}", Color.RED))
        return None



def cargar_fechas_entrega(directorio='.'):
    """
    Lee 4_FECHA_ENTREGA_TRABAJOS.csv y devuelve un dict {expediente: date}.
    Si el fichero no existe devuelve dict vacío.
    Columnas: Expediente, Empresa, Fecha_entrega, Estado_entrega
    """
    ruta = os.path.join(directorio, '4_FECHA_ENTREGA_TRABAJOS.csv')
    df = leer_csv(ruta)
    if df is None:
        warn("4_FECHA_ENTREGA_TRABAJOS.csv no encontrado — se usará sin fecha de entrega individual")
        return {}
    fechas = {}
    for _, row in df.iterrows():
        exp  = str(row.get('Expediente', '')).strip()
        fraw = str(row.get('Fecha_entrega', '')).strip()
        f    = normalizar_fecha(fraw)
        if exp and f:
            fechas[exp] = f
    ok(f"4_FECHA_ENTREGA_TRABAJOS.csv → {len(fechas)} fechas de entrega cargadas")
    for exp, f in sorted(fechas.items()):
        info(f"  Expediente {exp}: entrega {f}")
    return fechas

# ══════════════════════════════════════════════════════════════
# CLASE PRINCIPAL: CORRECTOR
# ══════════════════════════════════════════════════════════════

class CorrectorEmpresaula:

    def __init__(self, directorio='.'):
        self.dir = directorio
        self.errores_total = 0
        self.avisos_total = 0
        self.correctos_total = 0
        self.resumen_por_alumno = {}
        subheader("Cargando fechas de entrega individuales...")
        self.fechas_entrega = cargar_fechas_entrega(directorio)

    def _ruta(self, nombre):
        return os.path.join(self.dir, nombre)

    def _registrar(self, empresa, tipo, mensaje, nivel='error'):
        exp = extraer_expediente(empresa)
        if exp not in self.resumen_por_alumno:
            self.resumen_por_alumno[exp] = {'empresa': empresa, 'errores': [], 'avisos': [], 'ok': []}
        if nivel == 'error':
            self.resumen_por_alumno[exp]['errores'].append(f"[{tipo}] {mensaje}")
            self.errores_total += 1
        elif nivel == 'aviso':
            self.resumen_por_alumno[exp]['avisos'].append(f"[{tipo}] {mensaje}")
            self.avisos_total += 1
        else:
            self.resumen_por_alumno[exp]['ok'].append(f"[{tipo}] {mensaje}")
            self.correctos_total += 1

    # ──────────────────────────────────────────────────────────
    # MÓDULO 1: COMPRAS
    # ──────────────────────────────────────────────────────────

    def corregir_compras(self, fecha_entrega_str=None):
        header("MÓDULO 1: CORRECCIÓN DE COMPRAS")
        # fecha_entrega_str se ignora; se usa self.fechas_entrega por empresa
        if fecha_entrega_str:
            warn("Parámetro fecha_entrega ignorado: se usan fechas individuales del CSV 4_FECHA_ENTREGA_TRABAJOS.csv")

        # Cargar archivos
        subheader("Cargando archivos de compras...")
        df_real   = leer_csv(self._ruta('0_DATOS_COMPRAS_REALES.csv'))
        df_ped    = leer_csv(self._ruta('1_DATOS_PEDIDOS_COMPRA_ALUMNOS.csv'))
        df_alb    = leer_csv(self._ruta('2_DATOS_ALBARANES_COMPRA_ALUMNOS.csv'))
        df_fac    = leer_csv(self._ruta('3_DATOS_FACTURAS_COMPRA_ALUMNOS.csv'))

        archivos = [
            ('0_DATOS_COMPRAS_REALES.csv', df_real),
            ('1_DATOS_PEDIDOS_COMPRA_ALUMNOS.csv', df_ped),
            ('2_DATOS_ALBARANES_COMPRA_ALUMNOS.csv', df_alb),
            ('3_DATOS_FACTURAS_COMPRA_ALUMNOS.csv', df_fac),
        ]
        for nombre, df in archivos:
            if df is not None:
                ok(f"{nombre} → {len(df)} registros")
            else:
                err(f"{nombre} → NO ENCONTRADO")
                return

        # Normalizar importes y fechas en reales
        df_real['R_IMPORTE_C']      = df_real['R_IMPORTE_C'].apply(normalizar_importe)
        df_real['R_FECHA_EMISION_C']= df_real['R_FECHA_EMISION_C'].apply(normalizar_fecha)
        df_real['R_NUMERO_CP']      = df_real['R_NUMERO_CP'].astype(str).str.strip()
        df_real['R_NUMERO_CA']      = df_real['R_NUMERO_CA'].astype(str).str.strip()
        df_real['R_NUMERO_CF']      = df_real['R_NUMERO_CF'].astype(str).str.strip()
        df_real['R_EMPRESA_C']      = df_real['R_EMPRESA_C'].astype(str).str.strip()

        # Normalizar pedidos alumno
        df_ped['A_IMPORTE_CP']        = df_ped['A_IMPORTE_CP'].apply(normalizar_importe)
        df_ped['A_FECHA_EMISION_CP']  = df_ped['A_FECHA_EMISION_CP'].apply(normalizar_fecha)
        df_ped['A_FECHA_ALTA_ODOO_CP']= df_ped['A_FECHA_ALTA_ODOO_CP'].apply(normalizar_fecha)
        df_ped['A_NUMERO_CP']         = df_ped['A_NUMERO_CP'].astype(str).str.strip()
        df_ped['A_EMPRESA_CP']        = df_ped['A_EMPRESA_CP'].astype(str).str.strip()
        df_ped['A_PROVEEDOR_CP']      = df_ped['A_PROVEEDOR_CP'].astype(str).str.strip()
        df_ped['A_REF_ODOO_CP']       = df_ped['A_REF_ODOO_CP'].astype(str).str.strip()

        # Normalizar albaranes alumno
        df_alb['A_IMPORTE_CA']        = df_alb['A_IMPORTE_CA'].apply(normalizar_importe)
        df_alb['A_FECHA_EMISION_CA']  = df_alb['A_FECHA_EMISION_CA'].apply(normalizar_fecha)
        df_alb['A_NUMERO_CA']         = df_alb['A_NUMERO_CA'].astype(str).str.strip()
        df_alb['A_EMPRESA_CA']        = df_alb['A_EMPRESA_CA'].astype(str).str.strip()
        df_alb['A_ORIGEN_CA']         = df_alb['A_ORIGEN_CA'].astype(str).str.strip()
        df_alb['A_ESTADO_CA']         = df_alb['A_ESTADO_CA'].astype(str).str.strip()

        # Normalizar facturas alumno
        df_fac['A_IMPORTE_CF']        = df_fac['A_IMPORTE_CF'].apply(normalizar_importe)
        df_fac['A_FECHA_EMISION_CF']  = df_fac['A_FECHA_EMISION_CF'].apply(normalizar_fecha)
        df_fac['A_NUMERO_CF']         = df_fac['A_NUMERO_CF'].astype(str).str.strip()
        df_fac['A_EMPRESA_CF']        = df_fac['A_EMPRESA_CF'].astype(str).str.strip()
        df_fac['A_ORIGEN_CF']         = df_fac['A_ORIGEN_CF'].astype(str).str.strip()
        df_fac['A_ESTADO_PAGO_CF']    = df_fac['A_ESTADO_PAGO_CF'].astype(str).str.strip()

        # Construir índice: expediente + ref_odoo_pedido
        df_ped['EXPEDIENTE'] = df_ped['A_EMPRESA_CP'].apply(extraer_expediente)
        df_alb['EXPEDIENTE'] = df_alb['A_EMPRESA_CA'].apply(extraer_expediente)
        df_fac['EXPEDIENTE'] = df_fac['A_EMPRESA_CF'].apply(extraer_expediente)

        # Obtener empresas únicas
        empresas = df_real['R_EMPRESA_C'].unique()

        subheader(f"Verificando {len(empresas)} empresa(s)...")

        for empresa in sorted(empresas):
            exp = extraer_expediente(empresa)
            fecha_entrega = self.fechas_entrega.get(exp)
            print(f"\n{c('▶', Color.BOLD+Color.BLUE)} Empresa: {c(empresa, Color.WHITE+Color.BOLD)}")
            if fecha_entrega:
                info(f"Fecha de entrega: {c(str(fecha_entrega), Color.YELLOW)}")
            else:
                warn("Sin fecha de entrega registrada para esta empresa")

            reales_emp = df_real[df_real['R_EMPRESA_C'] == empresa].copy()
            peds_emp   = df_ped[df_ped['A_EMPRESA_CP'] == empresa].copy()
            albs_emp   = df_alb[df_alb['A_EMPRESA_CA'] == empresa].copy()
            facs_emp   = df_fac[df_fac['A_EMPRESA_CF'] == empresa].copy()

            errores_emp = 0

            # ── 1. Comprobar que están todos los pedidos ──
            print(f"  {c('1. PEDIDOS DE COMPRA', Color.CYAN)}")
            nums_reales = set(reales_emp['R_NUMERO_CP'].tolist())
            nums_alumno = set(peds_emp['A_NUMERO_CP'].tolist())

            pedidos_faltantes = nums_reales - nums_alumno
            pedidos_extra     = nums_alumno - nums_reales

            if not pedidos_faltantes:
                ok(f"Todos los pedidos reales están registrados ({len(nums_reales)})")
                self._registrar(empresa, 'PEDIDOS', f"Todos los pedidos presentes ({len(nums_reales)})", 'ok')
            else:
                for num in sorted(pedidos_faltantes):
                    real = reales_emp[reales_emp['R_NUMERO_CP'] == num].iloc[0]
                    err(f"PEDIDO FALTANTE: Nº {c(num, Color.YELLOW)} | {real['R_PROVEEDOR_C']} | {real['R_FECHA_EMISION_C']} | {real['R_IMPORTE_C']:.2f}€")
                    self._registrar(empresa, 'PEDIDO_FALTANTE', f"Pedido Nº{num} ({real['R_PROVEEDOR_C']}, {real['R_IMPORTE_C']:.2f}€)")
                    errores_emp += 1

            if pedidos_extra:
                for num in sorted(pedidos_extra):
                    warn(f"PEDIDO NO REAL: Nº {num} en ODOO pero no en EmpresAula")
                    self._registrar(empresa, 'PEDIDO_EXTRA', f"Pedido Nº{num} no existe en EmpresAula", 'aviso')

            # ── 2. Verificar datos de cada pedido ──
            for _, real_row in reales_emp.iterrows():
                num_cp = real_row['R_NUMERO_CP']
                ped_rows = peds_emp[peds_emp['A_NUMERO_CP'] == num_cp]
                if ped_rows.empty:
                    continue
                ped = ped_rows.iloc[0]

                # Proveedor
                if ped['A_PROVEEDOR_CP'].upper() != real_row['R_PROVEEDOR_C'].upper():
                    err(f"Pedido {num_cp}: PROVEEDOR incorrecto → alumno: '{ped['A_PROVEEDOR_CP']}' | real: '{real_row['R_PROVEEDOR_C']}'")
                    self._registrar(empresa, 'PROVEEDOR_ERROR', f"Pedido {num_cp}: alumno '{ped['A_PROVEEDOR_CP']}' vs real '{real_row['R_PROVEEDOR_C']}'")
                    errores_emp += 1

                # Fecha emisión
                if ped['A_FECHA_EMISION_CP'] != real_row['R_FECHA_EMISION_C']:
                    err(f"Pedido {num_cp}: FECHA EMISIÓN incorrecta → alumno: {ped['A_FECHA_EMISION_CP']} | real: {real_row['R_FECHA_EMISION_C']}")
                    self._registrar(empresa, 'FECHA_ERROR', f"Pedido {num_cp}: {ped['A_FECHA_EMISION_CP']} vs {real_row['R_FECHA_EMISION_C']}")
                    errores_emp += 1

                # Importe
                imp_real = real_row['R_IMPORTE_C']
                imp_alu  = ped['A_IMPORTE_CP']
                if abs(imp_real - imp_alu) > 0.02:
                    err(f"Pedido {num_cp}: IMPORTE incorrecto → alumno: {imp_alu:.2f}€ | real: {imp_real:.2f}€")
                    self._registrar(empresa, 'IMPORTE_ERROR', f"Pedido {num_cp}: {imp_alu:.2f}€ vs {imp_real:.2f}€")
                    errores_emp += 1

                # Estado pedido
                estado_cp = str(ped.get('A_ESTADO_CP', '')).strip()
                if estado_cp != 'Pedido de compra':
                    err(f"Pedido {num_cp}: ESTADO incorrecto → '{estado_cp}' (debe ser 'Pedido de compra')")
                    self._registrar(empresa, 'ESTADO_ERROR', f"Pedido {num_cp}: estado '{estado_cp}'")
                    errores_emp += 1

                # Estado facturación (depende fecha entrega)
                estado_fac = str(ped.get('A_ESTADO_FACTURACION_CP', '')).strip()
                fecha_emision = real_row['R_FECHA_EMISION_C']
                if fecha_entrega and fecha_emision:
                    if fecha_emision < fecha_entrega:
                        esperado = 'Totalmente facturado'
                    else:  # fecha_emision == fecha_entrega (no puede ser posterior)
                        esperado = 'Facturas en espera'
                    if estado_fac != esperado:
                        warn(f"Pedido {num_cp}: ESTADO FACTURACIÓN '{estado_fac}' → se esperaba '{esperado}' (emisión:{fecha_emision}, entrega:{fecha_entrega})")
                        self._registrar(empresa, 'ESTADO_FAC', f"Pedido {num_cp}: '{estado_fac}' vs esperado '{esperado}'", 'aviso')

            # ── 3. Albaranes ──
            print(f"  {c('2. ALBARANES DE COMPRA', Color.CYAN)}")
            # Cada pedido debe tener su albarán (trazabilidad por A_ORIGEN_CA = A_REF_ODOO_CP)
            refs_pedidos = set(peds_emp['A_REF_ODOO_CP'].tolist())
            refs_alb_origen = set(albs_emp['A_ORIGEN_CA'].tolist())

            sin_albaran = refs_pedidos - refs_alb_origen
            if not sin_albaran:
                ok(f"Todos los pedidos tienen su albarán ({len(refs_pedidos)})")
                self._registrar(empresa, 'ALBARANES', f"Trazabilidad pedido-albarán completa", 'ok')
            else:
                for ref in sorted(sin_albaran):
                    ped_row = peds_emp[peds_emp['A_REF_ODOO_CP'] == ref]
                    desc = f"Pedido {ped_row.iloc[0]['A_NUMERO_CP']}" if not ped_row.empty else ref
                    err(f"ALBARÁN FALTANTE para {c(desc, Color.YELLOW)} (ref ODOO: {ref})")
                    self._registrar(empresa, 'ALBARAN_FALTANTE', f"Sin albarán para {desc} (ref:{ref})")
                    errores_emp += 1

            # Verificar datos de albaranes
            for _, alb in albs_emp.iterrows():
                ref_origen = alb['A_ORIGEN_CA']
                ped_orig = peds_emp[peds_emp['A_REF_ODOO_CP'] == ref_origen]
                if ped_orig.empty:
                    warn(f"Albarán {alb['A_NUMERO_CA']}: origen '{ref_origen}' no corresponde a ningún pedido")
                    continue
                ped_o = ped_orig.iloc[0]
                num_ped = ped_o['A_NUMERO_CP']

                # Encontrar el real correspondiente
                real_rows = reales_emp[reales_emp['R_NUMERO_CP'] == num_ped]
                if real_rows.empty:
                    continue
                real_row = real_rows.iloc[0]

                # Proveedor albarán
                if str(alb['A_PROVEEDOR_CA']).strip().upper() != real_row['R_PROVEEDOR_C'].upper():
                    err(f"Albarán {alb['A_NUMERO_CA']}: PROVEEDOR incorrecto → '{alb['A_PROVEEDOR_CA']}' vs '{real_row['R_PROVEEDOR_C']}'")
                    self._registrar(empresa, 'ALB_PROVEEDOR', f"Albarán {alb['A_NUMERO_CA']}: proveedor incorrecto")
                    errores_emp += 1

                # Número albarán
                if str(alb['A_NUMERO_CA']).strip() != str(real_row['R_NUMERO_CA']).strip():
                    err(f"Albarán: NÚMERO incorrecto → alumno: {alb['A_NUMERO_CA']} | real: {real_row['R_NUMERO_CA']}")
                    self._registrar(empresa, 'ALB_NUMERO', f"Albarán Nº{alb['A_NUMERO_CA']} vs real Nº{real_row['R_NUMERO_CA']}")
                    errores_emp += 1

                # Fecha albarán (debe coincidir con fecha pedido)
                if alb['A_FECHA_EMISION_CA'] != real_row['R_FECHA_EMISION_C']:
                    err(f"Albarán {alb['A_NUMERO_CA']}: FECHA incorrecta → alumno: {alb['A_FECHA_EMISION_CA']} | real: {real_row['R_FECHA_EMISION_C']}")
                    self._registrar(empresa, 'ALB_FECHA', f"Albarán {alb['A_NUMERO_CA']}: {alb['A_FECHA_EMISION_CA']} vs {real_row['R_FECHA_EMISION_C']}")
                    errores_emp += 1

                # Importe albarán
                imp_real = real_row['R_IMPORTE_C']
                imp_alb  = alb['A_IMPORTE_CA']
                if abs(imp_real - imp_alb) > 0.02:
                    err(f"Albarán {alb['A_NUMERO_CA']}: IMPORTE incorrecto → {imp_alb:.2f}€ vs {imp_real:.2f}€")
                    self._registrar(empresa, 'ALB_IMPORTE', f"Albarán {alb['A_NUMERO_CA']}: {imp_alb:.2f}€ vs {imp_real:.2f}€")
                    errores_emp += 1

                # Estado albarán
                if alb['A_ESTADO_CA'] != 'Hecho':
                    err(f"Albarán {alb['A_NUMERO_CA']}: ESTADO '{alb['A_ESTADO_CA']}' → debe ser 'Hecho'")
                    self._registrar(empresa, 'ALB_ESTADO', f"Albarán {alb['A_NUMERO_CA']}: estado '{alb['A_ESTADO_CA']}'")
                    errores_emp += 1

            # ── 4. Facturas ──
            print(f"  {c('3. FACTURAS DE COMPRA', Color.CYAN)}")
            refs_fac_origen = set(facs_emp['A_ORIGEN_CF'].tolist())

            for _, ped in peds_emp.iterrows():
                ref_ped = ped['A_REF_ODOO_CP']
                fecha_emision_ped = normalizar_fecha(str(ped['A_FECHA_EMISION_CP']))

                # Determinar si la factura debería estar registrada
                factura_requerida = True
                if fecha_entrega and fecha_emision_ped:
                    if fecha_emision_ped >= fecha_entrega:
                        factura_requerida = False  # Factura emitida el mismo día que entrega → no disponible aún

                if factura_requerida:
                    if ref_ped not in refs_fac_origen:
                        err(f"FACTURA FALTANTE para pedido {ped['A_NUMERO_CP']} (ref: {ref_ped})")
                        self._registrar(empresa, 'FACTURA_FALTANTE', f"Sin factura para pedido {ped['A_NUMERO_CP']}")
                        errores_emp += 1
                    else:
                        fac_row = facs_emp[facs_emp['A_ORIGEN_CF'] == ref_ped].iloc[0]
                        num_ped = ped['A_NUMERO_CP']
                        real_rows = reales_emp[reales_emp['R_NUMERO_CP'] == num_ped]
                        if real_rows.empty:
                            continue
                        real_row = real_rows.iloc[0]

                        # Número factura
                        if str(fac_row['A_NUMERO_CF']).strip() != str(real_row['R_NUMERO_CF']).strip():
                            err(f"Factura pedido {num_ped}: NÚMERO incorrecto → alumno: {fac_row['A_NUMERO_CF']} | real: {real_row['R_NUMERO_CF']}")
                            self._registrar(empresa, 'FAC_NUMERO', f"Pedido {num_ped}: factura {fac_row['A_NUMERO_CF']} vs real {real_row['R_NUMERO_CF']}")
                            errores_emp += 1

                        # Importe factura
                        imp_real = real_row['R_IMPORTE_C']
                        imp_fac  = fac_row['A_IMPORTE_CF']
                        if abs(imp_real - imp_fac) > 0.02:
                            err(f"Factura {fac_row['A_NUMERO_CF']}: IMPORTE incorrecto → {imp_fac:.2f}€ vs {imp_real:.2f}€")
                            self._registrar(empresa, 'FAC_IMPORTE', f"Factura {fac_row['A_NUMERO_CF']}: {imp_fac:.2f}€ vs {imp_real:.2f}€")
                            errores_emp += 1

                        # Fecha factura (debe coincidir con fecha pedido)
                        if fac_row['A_FECHA_EMISION_CF'] != real_row['R_FECHA_EMISION_C']:
                            err(f"Factura {fac_row['A_NUMERO_CF']}: FECHA incorrecta → {fac_row['A_FECHA_EMISION_CF']} vs {real_row['R_FECHA_EMISION_C']}")
                            self._registrar(empresa, 'FAC_FECHA', f"Factura {fac_row['A_NUMERO_CF']}: fecha incorrecta")
                            errores_emp += 1

                        # Estado pago
                        estado_pago = str(fac_row['A_ESTADO_PAGO_CF']).strip()
                        if estado_pago not in ('Publicado', 'Pagada'):
                            err(f"Factura {fac_row['A_NUMERO_CF']}: ESTADO PAGO '{estado_pago}' → debe ser 'Publicado' o 'Pagada'")
                            self._registrar(empresa, 'FAC_ESTADO', f"Factura {fac_row['A_NUMERO_CF']}: estado '{estado_pago}'")
                            errores_emp += 1
                else:
                    info(f"Pedido {ped['A_NUMERO_CP']}: factura no requerida (emisión = fecha entrega)")

            # Resumen empresa compras
            if errores_emp == 0:
                ok(c(f"EMPRESA {empresa}: SIN ERRORES EN COMPRAS", Color.GREEN + Color.BOLD))
            else:
                err(c(f"EMPRESA {empresa}: {errores_emp} ERROR(ES) EN COMPRAS", Color.RED + Color.BOLD))




    # ──────────────────────────────────────────────────────────
    # MÓDULO 2: VENTAS
    # ──────────────────────────────────────────────────────────

    def corregir_ventas(self, fecha_entrega_str=None):
        header("MÓDULO 2: CORRECCIÓN DE VENTAS")
        if fecha_entrega_str:
            warn("Parámetro fecha_entrega ignorado: se usan fechas individuales del CSV 4_FECHA_ENTREGA_TRABAJOS.csv")

        subheader("Cargando archivos de ventas...")
        df_real = leer_csv(self._ruta('5_DATOS_VENTAS_REALES.csv'))
        df_ped  = leer_csv(self._ruta('6_DATOS_PEDIDOS_VENTA_ALUMNOS.csv'))
        df_alb  = leer_csv(self._ruta('7_DATOS_ALBARANES_VENTA_ALUMNOS.csv'))
        df_fac  = leer_csv(self._ruta('8_DATOS_FACTURAS_VENTA_ALUMNOS.csv'))

        for nombre, df in [('5_DATOS_VENTAS_REALES.csv', df_real),
                           ('6_DATOS_PEDIDOS_VENTA_ALUMNOS.csv', df_ped),
                           ('7_DATOS_ALBARANES_VENTA_ALUMNOS.csv', df_alb),
                           ('8_DATOS_FACTURAS_VENTA_ALUMNOS.csv', df_fac)]:
            if df is not None:
                ok(f"{nombre} → {len(df)} registros")
            else:
                err(f"{nombre} → NO ENCONTRADO")
                return

        # Normalizar
        df_real['R_IMPORTE_V']           = df_real['R_IMPORTE_V'].apply(normalizar_importe)
        df_real['R_FECHA_EMISION_VP']     = df_real['R_FECHA_EMISION_VP'].apply(normalizar_fecha)
        df_real['R_FECHA_MAX_FACTURACION_V'] = df_real['R_FECHA_MAX_FACTURACION_V'].apply(normalizar_fecha)
        df_real['R_NUMERO_VP']            = df_real['R_NUMERO_VP'].astype(str).str.strip()
        df_real['R_EMPRESA_V']            = df_real['R_EMPRESA_V'].astype(str).str.strip()
        df_real['R_CLIENTE_V']            = df_real['R_CLIENTE_V'].astype(str).str.strip()

        df_ped['A_IMPORTE_VP']            = df_ped['A_IMPORTE_VP'].apply(normalizar_importe)
        df_ped['A_FECHA_EMISION_VP']      = df_ped['A_FECHA_EMISION_VP'].apply(normalizar_fecha)
        df_ped['A_FECHA_ALTA_ODOO_VP']    = df_ped['A_FECHA_ALTA_ODOO_VP'].apply(normalizar_fecha)
        df_ped['A_NUMERO_VP']             = df_ped['A_NUMERO_VP'].astype(str).str.strip()
        df_ped['A_EMPRESA_VP']            = df_ped['A_EMPRESA_VP'].astype(str).str.strip()
        df_ped['A_REF_ODOO_VP']           = df_ped['A_REF_ODOO_VP'].astype(str).str.strip()
        df_ped['A_CLIENT_VP']             = df_ped['A_CLIENT_VP'].astype(str).str.strip()

        df_alb['A_IMPORTE_VA']            = df_alb['A_IMPORTE_VA'].apply(normalizar_importe)
        df_alb['A_FECHA_ALBARAN_VA']      = df_alb['A_FECHA_ALBARAN_VA'].apply(normalizar_fecha)
        df_alb['A_ORIGEN_VA']             = df_alb['A_ORIGEN_VA'].astype(str).str.strip()
        df_alb['A_EMPRESA_VA']            = df_alb['A_EMPRESA_VA'].astype(str).str.strip()
        df_alb['A_ESTADO_VA']             = df_alb['A_ESTADO_VA'].astype(str).str.strip()
        df_alb['A_CLIENT_VA']             = df_alb['A_CLIENT_VA'].astype(str).str.strip()

        df_fac['A_IMPORTE_VF']            = df_fac['A_IMPORTE_VF'].apply(normalizar_importe)
        df_fac['A_FECHA_FACTURA_VF']      = df_fac['A_FECHA_FACTURA_VF'].apply(normalizar_fecha) if 'A_FECHA_FACTURA_VF' in df_fac.columns else df_fac.get('A_FECHA_ALBARAN_VA', pd.Series()).apply(normalizar_fecha)
        df_fac['A_ORIGEN_VF']             = df_fac['A_ORIGEN_VF'].astype(str).str.strip()
        df_fac['A_EMPRESA_VF']            = df_fac['A_EMPRESA_VF'].astype(str).str.strip()
        df_fac['A_CLIENT_VF']             = df_fac['A_CLIENT_VF'].astype(str).str.strip()
        df_fac['A_NUM_FACTURA_VF']        = df_fac['A_NUM_FACTURA_VF.'].astype(str).str.strip() if 'A_NUM_FACTURA_VF.' in df_fac.columns else df_fac.get('A_NUM_FACTURA_VF', pd.Series(dtype=str))

        empresas = df_real['R_EMPRESA_V'].unique()
        subheader(f"Verificando {len(empresas)} empresa(s)...")

        for empresa in sorted(empresas):
            exp = extraer_expediente(empresa)
            fecha_entrega = self.fechas_entrega.get(exp)
            print(f"\n{c('▶', Color.BOLD+Color.BLUE)} Empresa: {c(empresa, Color.WHITE+Color.BOLD)}")
            if fecha_entrega:
                info(f"Fecha de entrega: {c(str(fecha_entrega), Color.YELLOW)}")
            else:
                warn("Sin fecha de entrega registrada para esta empresa")
            errores_emp = 0

            reales_emp = df_real[df_real['R_EMPRESA_V'] == empresa].copy()
            peds_emp   = df_ped[df_ped['A_EMPRESA_VP'] == empresa].copy()
            albs_emp   = df_alb[df_alb['A_EMPRESA_VA'] == empresa].copy()
            facs_emp   = df_fac[df_fac['A_EMPRESA_VF'] == empresa].copy()

            # ── 1. Pedidos de venta ──
            print(f"  {c('1. PEDIDOS DE VENTA', Color.CYAN)}")
            nums_reales = set(reales_emp['R_NUMERO_VP'].tolist())
            nums_alumno = set(peds_emp['A_NUMERO_VP'].tolist())

            faltantes = nums_reales - nums_alumno
            if not faltantes:
                ok(f"Todos los pedidos de venta registrados ({len(nums_reales)})")
                self._registrar(empresa, 'PED_VENTA', f"Todos los pedidos presentes ({len(nums_reales)})", 'ok')
            else:
                for num in sorted(faltantes):
                    real = reales_emp[reales_emp['R_NUMERO_VP'] == num].iloc[0]
                    err(f"PEDIDO FALTA: Nº {c(num, Color.YELLOW)} | {real['R_CLIENTE_V']} | {real['R_FECHA_EMISION_VP']} | {real['R_IMPORTE_V']:.2f}€")
                    self._registrar(empresa, 'PED_V_FALTANTE', f"Pedido venta Nº{num}")
                    errores_emp += 1

            # Verificar datos pedidos
            for _, real_row in reales_emp.iterrows():
                num_vp = real_row['R_NUMERO_VP']
                ped_rows = peds_emp[peds_emp['A_NUMERO_VP'] == num_vp]
                if ped_rows.empty:
                    continue
                ped = ped_rows.iloc[0]

                # Cliente
                if ped['A_CLIENT_VP'].upper() != real_row['R_CLIENTE_V'].upper():
                    err(f"Pedido venta {num_vp}: CLIENTE incorrecto → '{ped['A_CLIENT_VP']}' vs '{real_row['R_CLIENTE_V']}'")
                    self._registrar(empresa, 'PED_V_CLIENTE', f"Pedido {num_vp}: cliente incorrecto")
                    errores_emp += 1

                # Fecha
                if ped['A_FECHA_EMISION_VP'] != real_row['R_FECHA_EMISION_VP']:
                    err(f"Pedido venta {num_vp}: FECHA → alumno: {ped['A_FECHA_EMISION_VP']} | real: {real_row['R_FECHA_EMISION_VP']}")
                    self._registrar(empresa, 'PED_V_FECHA', f"Pedido {num_vp}: fecha incorrecta")
                    errores_emp += 1

                # Importe
                if abs(ped['A_IMPORTE_VP'] - real_row['R_IMPORTE_V']) > 0.02:
                    err(f"Pedido venta {num_vp}: IMPORTE → {ped['A_IMPORTE_VP']:.2f}€ vs {real_row['R_IMPORTE_V']:.2f}€")
                    self._registrar(empresa, 'PED_V_IMPORTE', f"Pedido {num_vp}: importe incorrecto")
                    errores_emp += 1

                # Estado
                estado = str(ped.get('A_ESTADO_VP', '')).strip()
                if estado != 'Pedido de venta':
                    err(f"Pedido venta {num_vp}: ESTADO '{estado}' → debe ser 'Pedido de venta'")
                    errores_emp += 1

                # Fecha máxima de facturación
                fecha_max = real_row['R_FECHA_MAX_FACTURACION_V']
                fecha_alta_odoo = ped['A_FECHA_ALTA_ODOO_VP']
                if fecha_alta_odoo and fecha_max and fecha_alta_odoo > fecha_max:
                    err(f"Pedido venta {num_vp}: introducido en ODOO ({fecha_alta_odoo}) DESPUÉS del límite de facturación ({fecha_max})")
                    self._registrar(empresa, 'PED_V_TARDIO', f"Pedido {num_vp}: introducido tardíamente")
                    errores_emp += 1

            # ── 2. Albaranes de venta ──
            print(f"  {c('2. ALBARANES DE VENTA', Color.CYAN)}")
            refs_pedidos_v = set(peds_emp['A_REF_ODOO_VP'].tolist())
            refs_alb_v     = set(albs_emp['A_ORIGEN_VA'].tolist())
            sin_albaran_v  = refs_pedidos_v - refs_alb_v

            if not sin_albaran_v:
                ok(f"Todos los pedidos tienen su albarán de venta")
                self._registrar(empresa, 'ALB_VENTA', "Trazabilidad pedido-albarán venta OK", 'ok')
            else:
                for ref in sorted(sin_albaran_v):
                    ped_row = peds_emp[peds_emp['A_REF_ODOO_VP'] == ref]
                    desc = f"pedido {ped_row.iloc[0]['A_NUMERO_VP']}" if not ped_row.empty else ref
                    err(f"ALBARÁN VENTA FALTANTE para {desc}")
                    self._registrar(empresa, 'ALB_V_FALTANTE', f"Sin albarán venta para {desc}")
                    errores_emp += 1

            # Verificar fechas y datos albarán venta
            for _, alb in albs_emp.iterrows():
                ref_origen = alb['A_ORIGEN_VA']
                ped_orig = peds_emp[peds_emp['A_REF_ODOO_VP'] == ref_origen]
                if ped_orig.empty:
                    warn(f"Albarán venta {alb.get('A_REF_ODOO_VA', '?')}: origen '{ref_origen}' no identificado")
                    continue
                ped_o = ped_orig.iloc[0]
                num_vp = ped_o['A_NUMERO_VP']
                real_rows = reales_emp[reales_emp['R_NUMERO_VP'] == num_vp]
                if real_rows.empty:
                    continue
                real_row = real_rows.iloc[0]

                # Fecha alta odoo <= fecha albarán <= fecha max facturación
                f_alta = ped_o['A_FECHA_ALTA_ODOO_VP']
                f_alb  = alb['A_FECHA_ALBARAN_VA']
                f_max  = real_row['R_FECHA_MAX_FACTURACION_V']

                if f_alta and f_alb and f_alta > f_alb:
                    err(f"Albarán venta pedido {num_vp}: fecha albarán ({f_alb}) ANTERIOR a alta ODOO del pedido ({f_alta})")
                    errores_emp += 1

                if f_alb and f_max and f_alb > f_max:
                    err(f"Albarán venta pedido {num_vp}: generado ({f_alb}) DESPUÉS del límite viernes ({f_max})")
                    self._registrar(empresa, 'ALB_V_TARDIO', f"Albarán pedido {num_vp}: generado tardíamente")
                    errores_emp += 1

                # Importe
                imp_real = real_row['R_IMPORTE_V']
                if abs(alb['A_IMPORTE_VA'] - imp_real) > 0.02:
                    err(f"Albarán venta pedido {num_vp}: IMPORTE → {alb['A_IMPORTE_VA']:.2f}€ vs {imp_real:.2f}€")
                    errores_emp += 1

                # Estado
                if alb['A_ESTADO_VA'] != 'Hecho':
                    err(f"Albarán venta pedido {num_vp}: ESTADO '{alb['A_ESTADO_VA']}' → debe ser 'Hecho'")
                    errores_emp += 1

                # Cliente
                if alb['A_CLIENT_VA'].upper() != real_row['R_CLIENTE_V'].upper():
                    err(f"Albarán venta pedido {num_vp}: CLIENTE '{alb['A_CLIENT_VA']}' vs '{real_row['R_CLIENTE_V']}'")
                    errores_emp += 1

            # ── 3. Facturas de venta ──
            print(f"  {c('3. FACTURAS DE VENTA', Color.CYAN)}")
            self._verificar_facturas_venta(empresa, peds_emp, facs_emp, reales_emp, errores_emp, fecha_entrega)

        subheader("Verificación de ventas completada")


    def _verificar_facturas_venta(self, empresa, peds_emp, facs_emp, reales_emp, errores_emp, fecha_entrega=None):
        """Verifica facturas de venta incluyendo facturación consolidada y numeración correlativa."""

        # Agrupar pedidos por semana y cliente para detectar consolidación
        semanas_clientes = {}
        for _, ped in peds_emp.iterrows():
            num_vp = ped['A_NUMERO_VP']
            real_rows = reales_emp[reales_emp['R_NUMERO_VP'] == num_vp]
            if real_rows.empty:
                continue
            real = real_rows.iloc[0]
            fecha_max = real['R_FECHA_MAX_FACTURACION_V']
            cliente = ped['A_CLIENT_VP']
            clave = (str(fecha_max), cliente)
            if clave not in semanas_clientes:
                semanas_clientes[clave] = []
            semanas_clientes[clave].append(ped['A_REF_ODOO_VP'])

        # Expandir A_ORIGEN_VF (puede contener múltiples refs separadas por coma)
        def get_origins(origen_str):
            return [o.strip() for o in str(origen_str).split(',') if o.strip()]

        facs_emp['ORIGINS'] = facs_emp['A_ORIGEN_VF'].apply(get_origins)

        # Comprobar que todos los pedidos están facturados
        todos_refs_facturados = set()
        for _, fac in facs_emp.iterrows():
            todos_refs_facturados.update(fac['ORIGINS'])

        refs_pedidos = set(peds_emp['A_REF_ODOO_VP'].tolist())
        sin_factura = refs_pedidos - todos_refs_facturados

        if not sin_factura:
            ok(f"Todos los pedidos de venta están facturados")
            self._registrar(empresa, 'FAC_VENTA', "Todos los pedidos facturados", 'ok')
        else:
            for ref in sorted(sin_factura):
                ped_row = peds_emp[peds_emp['A_REF_ODOO_VP'] == ref]
                desc = f"pedido {ped_row.iloc[0]['A_NUMERO_VP']}" if not ped_row.empty else ref
                err(f"FACTURA VENTA FALTANTE para {desc}")
                self._registrar(empresa, 'FAC_V_FALTANTE', f"Sin factura venta para {desc}")

        # Verificar que la fecha de las facturas no supera la fecha de entrega del alumno
        if fecha_entrega:
            col_fecha_fac = 'A_FECHA_FACTURA_VF' if 'A_FECHA_FACTURA_VF' in facs_emp.columns else None
            col_num_fac   = 'A_NUM_FACTURA_VF'
            if col_fecha_fac and col_num_fac in facs_emp.columns:
                for _, fac in facs_emp.iterrows():
                    f_fac = fac.get(col_fecha_fac)
                    if f_fac and f_fac > fecha_entrega:
                        err(f"Factura {fac[col_num_fac]}: fecha {f_fac} posterior a fecha entrega {fecha_entrega}")
                        self._registrar(empresa, 'FAC_V_TARDE', f"Factura {fac[col_num_fac]} emitida tras fecha entrega")

        # ── Verificar numeración correlativa de facturas ──
        print(f"  {c('3b. NUMERACIÓN CORRELATIVA FACTURAS VENTA', Color.CYAN)}")
        if 'A_NUM_FACTURA_VF' in facs_emp.columns or not facs_emp.empty:
            col_num = 'A_NUM_FACTURA_VF'
            col_fecha = 'A_FECHA_FACTURA_VF' if 'A_FECHA_FACTURA_VF' in facs_emp.columns else 'A_FECHA_ALBARAN_VA'

            if col_num in facs_emp.columns and col_fecha in facs_emp.columns:
                # Extraer número de orden de la referencia FV-1/2025/NNNNN
                def extraer_num_orden(ref):
                    m = re.search(r'/(\d+)$', str(ref))
                    return int(m.group(1)) if m else None

                facs_sorted = facs_emp.copy()
                facs_sorted['_orden'] = facs_sorted[col_num].apply(extraer_num_orden)
                facs_sorted['_fecha_dt'] = facs_sorted[col_fecha]
                facs_sorted = facs_sorted.dropna(subset=['_orden']).sort_values('_orden')

                # Verificar correlatividad
                ordenes = facs_sorted['_orden'].tolist()
                fechas  = facs_sorted['_fecha_dt'].tolist()

                errores_num = 0
                for i in range(len(ordenes)):
                    # Salto en la numeración
                    if i > 0 and ordenes[i] != ordenes[i-1] + 1:
                        err(f"NUMERACIÓN NO CORRELATIVA: falta factura Nº{ordenes[i-1]+1} (salta de {ordenes[i-1]} a {ordenes[i]})")
                        self._registrar(empresa, 'FAC_NUM_CORRELATIVA', f"Falta factura Nº{ordenes[i-1]+1}")
                        errores_num += 1

                    # Fecha no creciente
                    if i > 0 and fechas[i] and fechas[i-1] and fechas[i] < fechas[i-1]:
                        err(f"FECHA NO CORRELATIVA: factura Nº{ordenes[i]} ({fechas[i]}) es anterior a Nº{ordenes[i-1]} ({fechas[i-1]})")
                        self._registrar(empresa, 'FAC_FECHA_ORDEN', f"Factura Nº{ordenes[i]}: fecha anterior a anterior")
                        errores_num += 1

                if errores_num == 0:
                    ok(f"Numeración y fechas de facturas de venta: correctas ({len(ordenes)} facturas)")
                    self._registrar(empresa, 'FAC_V_NUM', "Numeración correlativa OK", 'ok')

                # Estado pago facturas
                col_pagada = 'A_PAGADA_VF' if 'A_PAGADA_VF' in facs_emp.columns else None
                if col_pagada:
                    for _, fac in facs_emp.iterrows():
                        estado = str(fac[col_pagada]).strip()
                        if estado not in ('Publicado', 'Pagada', 'Pagado parcialmente'):
                            err(f"Factura {fac[col_num]}: ESTADO '{estado}' → debe ser 'Publicado' o 'Pagada'")




    # ──────────────────────────────────────────────────────────
    # MÓDULO 3: INVENTARIO
    # ──────────────────────────────────────────────────────────

    def corregir_inventario(self, fecha_entrega_str=None):
        header("MÓDULO 3: CORRECCIÓN DE INVENTARIO")
        if fecha_entrega_str:
            warn("Parámetro fecha_entrega ignorado: se usan fechas individuales del CSV 4_FECHA_ENTREGA_TRABAJOS.csv")

        subheader("Cargando archivos de inventario...")
        df_inv = leer_csv(self._ruta('9_DATOS_INVENTARIO_ALUMNO.csv'))
        df_his = leer_csv(self._ruta('10_HISTORIAL_E_S_INVENTARIO_ALUMNO.csv'))

        for nombre, df in [('9_DATOS_INVENTARIO_ALUMNO.csv', df_inv),
                           ('10_HISTORIAL_E_S_INVENTARIO_ALUMNO.csv', df_his)]:
            if df is not None:
                ok(f"{nombre} → {len(df)} registros")
            else:
                err(f"{nombre} → NO ENCONTRADO")
                return

        # ── Diagnóstico y mapeo flexible de columnas ──
        df_inv.columns = df_inv.columns.str.strip()
        df_his.columns = df_his.columns.str.strip()

        info(f"Columnas inventario  : {list(df_inv.columns)}")
        info(f"Columnas historial   : {list(df_his.columns)}")

        # Mapeo tolerante: clave normalizada → nombre real en el CSV
        # Inventario  (incluye formato con prefijo A_ y sufijo _I)
        MAP_INV = {
            'EMPRESA':                 ['A_EMPRESA_I', 'EMPRESA', 'Empresa', 'empresa', 'COMPANY', 'Company'],
            'PRODUCTE':                ['A_PRODUCTE_I', 'PRODUCTE', 'PRODUCTO', 'Producto', 'producto', 'Product', 'PRODUCT'],
            'COST UNITARI':            ['A_COST_UNITARI_I', 'COST UNITARI', 'COSTE UNITARIO', 'Cost unitari',
                                        'Coste unitario', 'COST_UNITARI', 'Unit Cost', 'Cost', 'COST'],
            'IMPORT':                  ['A_IMPORT_I', 'IMPORT', 'IMPORTE', 'Import', 'Importe', 'VALUE', 'Value', 'VALOR'],
            'UNITATS REALS':           ['A_UNITATS_REALS_I', 'UNITATS REALS', 'UNIDADES REALES', 'Unitats reals',
                                        'Unidades reales', 'On Hand', 'On hand', 'QTY', 'Qty', 'QUANTITY'],
            'UNITATS DISPONIBLES':     ['A_UNITATS_DISPONIBLES_I', 'UNITATS DISPONIBLES', 'UNIDADES DISPONIBLES',
                                        'Forecasted Quantity', 'Forecasted', 'Disponible', 'Available'],
            'UNITATS PENDENTS ENTRAR': ['A_UNITATS_PENDENTS_ENTRAR_I', 'UNITATS PENDENTS ENTRAR',
                                        'UNIDADES PENDIENTES ENTRAR', 'Incoming', 'incoming', 'INCOMING'],
            'UNITATS PENDENTS SORTIR': ['A_UNITATS_PENDENTS_SORTIR_I', 'UNITATS PENDENTS SORTIR',
                                        'UNIDADES PENDIENTES SALIR', 'Outgoing', 'outgoing', 'OUTGOING'],
        }
        # Historial  (incluye formato con prefijo A_ y sufijo _HES)
        MAP_HIS = {
            'EMPRESA':   ['A_EMPRESA_HES', 'EMPRESA', 'Empresa', 'empresa', 'COMPANY', 'Company'],
            'Producto':  ['A_PRODUCTE_HES', 'Producto', 'PRODUCTO', 'PRODUCTE', 'Product', 'PRODUCT', 'producte'],
            'Fecha':     ['A_DATA_HES', 'Fecha', 'FECHA', 'Date', 'DATE', 'Scheduled Date', 'date'],
            'Referencia':['A_REFERENCIA_HES', 'Referencia', 'REFERENCIA', 'Reference', 'REFERENCE', 'Ref', 'REF'],
            'Desde':     ['A_ORIGEN_HES', 'Desde', 'DESDE', 'From', 'FROM', 'Source Location', 'Source'],
            'A':         ['A_DESTI_HES', 'A', 'To', 'TO', 'Destination Location', 'Destination', 'Dest'],
            'Cantidad':  ['A_UNITATS_HES', 'Cantidad', 'CANTIDAD', 'Quantity', 'QUANTITY', 'QTY', 'Qty', 'Done'],
        }

        def renombrar_columnas(df, mapa, nombre_df):
            cols_actuales = {c.strip(): c for c in df.columns}
            renombrar = {}
            faltantes = []
            for col_destino, candidatos in mapa.items():
                encontrada = False
                for cand in candidatos:
                    if cand in cols_actuales:
                        renombrar[cols_actuales[cand]] = col_destino
                        encontrada = True
                        break
                if not encontrada:
                    faltantes.append(col_destino)
            if faltantes:
                warn(f"{nombre_df}: columnas no encontradas → {faltantes}")
                warn(f"  Columnas disponibles: {list(df.columns)}")
            df = df.rename(columns=renombrar)
            return df

        df_inv = renombrar_columnas(df_inv, MAP_INV, '9_DATOS_INVENTARIO')
        df_his = renombrar_columnas(df_his, MAP_HIS, '10_HISTORIAL')

        # Normalizar inventario
        df_inv['EMPRESA']   = df_inv['EMPRESA'].astype(str).str.strip()
        df_inv['PRODUCTE']  = df_inv['PRODUCTE'].astype(str).str.strip()
        df_inv['COST UNITARI']  = df_inv['COST UNITARI'].apply(normalizar_importe)
        df_inv['IMPORT']        = df_inv['IMPORT'].apply(normalizar_importe)
        df_inv['UNITATS REALS'] = pd.to_numeric(df_inv['UNITATS REALS'], errors='coerce').fillna(0).astype(int)
        df_inv['UNITATS DISPONIBLES']   = pd.to_numeric(df_inv.get('UNITATS DISPONIBLES', pd.Series(0, index=df_inv.index)), errors='coerce').fillna(0).astype(int)
        df_inv['UNITATS PENDENTS ENTRAR'] = pd.to_numeric(df_inv.get('UNITATS PENDENTS ENTRAR', pd.Series(0, index=df_inv.index)), errors='coerce').fillna(0).astype(int)
        df_inv['UNITATS PENDENTS SORTIR'] = pd.to_numeric(df_inv.get('UNITATS PENDENTS SORTIR', pd.Series(0, index=df_inv.index)), errors='coerce').fillna(0).astype(int)

        # Normalizar historial
        df_his['EMPRESA']    = df_his['EMPRESA'].astype(str).str.strip()
        df_his['Producto']   = df_his['Producto'].astype(str).str.strip()
        df_his['Desde']      = df_his['Desde'].astype(str).str.strip()
        df_his['A']          = df_his['A'].astype(str).str.strip()
        df_his['Cantidad']   = pd.to_numeric(df_his['Cantidad'], errors='coerce').fillna(0).astype(int)
        df_his['Fecha']      = pd.to_datetime(df_his['Fecha'], errors='coerce')

        empresas = df_inv['EMPRESA'].unique()
        subheader(f"Verificando {len(empresas)} empresa(s)...")

        for empresa in sorted(empresas):
            exp = extraer_expediente(empresa)
            fecha_entrega = self.fechas_entrega.get(exp)
            print(f"\n{c('▶', Color.BOLD+Color.BLUE)} Empresa: {c(empresa, Color.WHITE+Color.BOLD)}")
            if fecha_entrega:
                info(f"Fecha de entrega: {c(str(fecha_entrega), Color.YELLOW)}")
            else:
                warn("Sin fecha de entrega registrada para esta empresa")
            errores_emp = 0

            inv_emp = df_inv[df_inv['EMPRESA'] == empresa].copy()
            his_emp = df_his[df_his['EMPRESA'] == empresa].copy()

            # ── 1. Valor máximo inventario (≤ 1000€) ──
            print(f"  {c('1. VALOR DEL INVENTARIO FINAL', Color.CYAN)}")
            total_inventario = inv_emp['IMPORT'].sum()

            if total_inventario <= 1000.0:
                ok(f"Valor total inventario: {c(f'{total_inventario:.2f}€', Color.GREEN)} (límite: 1.000€)")
                self._registrar(empresa, 'INV_VALOR', f"Inventario {total_inventario:.2f}€ ≤ 1.000€", 'ok')
            else:
                err(f"Valor total inventario: {c(f'{total_inventario:.2f}€', Color.RED)} SUPERA el límite de 1.000€")
                self._registrar(empresa, 'INV_VALOR', f"Inventario {total_inventario:.2f}€ supera 1.000€")
                errores_emp += 1

            # Detalle por producto
            for _, row in inv_emp.iterrows():
                coste = row['COST UNITARI']
                unid  = row['UNITATS REALS']
                imp   = row['IMPORT']
                calc  = round(coste * unid, 2)
                if abs(imp - calc) > 0.02 and not (imp == 0 and unid == 0):
                    err(f"Producto {row['PRODUCTE']}: IMPORT {imp:.2f}€ ≠ {coste:.2f}€ × {unid} = {calc:.2f}€")
                    errores_emp += 1

            # ── 2. Pendientes en viernes ──
            print(f"  {c('2. OPERACIONES PENDIENTES', Color.CYAN)}")
            # Si fecha_entrega es viernes, no deben existir pendientes
            if fecha_entrega and fecha_entrega.weekday() == 4:  # 4 = viernes
                for _, row in inv_emp.iterrows():
                    pend_ent = row['UNITATS PENDENTS ENTRAR']
                    pend_sal = row['UNITATS PENDENTS SORTIR']
                    if pend_ent != 0 or pend_sal != 0:
                        err(f"Producto {row['PRODUCTE']}: PENDIENTES en viernes → Entrar:{pend_ent} / Salir:{pend_sal}")
                        self._registrar(empresa, 'INV_PENDIENTES', f"{row['PRODUCTE']}: pendientes en viernes")
                        errores_emp += 1
                    else:
                        # Verificar: UNITATS REALS == UNITATS DISPONIBLES
                        if row['UNITATS REALS'] != row['UNITATS DISPONIBLES']:
                            warn(f"Producto {row['PRODUCTE']}: REALS({row['UNITATS REALS']}) ≠ DISPONIBLES({row['UNITATS DISPONIBLES']}) con pendientes=0")

            # ── 3. Stock negativo en historial ──
            print(f"  {c('3. ANÁLISIS DE STOCK NEGATIVO', Color.CYAN)}")

            productos = his_emp['Producto'].unique()
            stock_negativo_total = 0

            # Detectar si el historial ya tiene columnas precalculadas (formato A_STOCK_HES)
            tiene_stock_precalc = 'A_STOCK_HES' in his_emp.columns
            tiene_operacio      = 'A_OPERACIO_HES' in his_emp.columns
            if tiene_stock_precalc:
                info("Usando columna A_STOCK_HES precalculada para verificación de stock")

            for producto in sorted(productos):
                ops = his_emp[his_emp['Producto'] == producto].copy()
                ops = ops.sort_values('Fecha').reset_index(drop=True)
                # Limitar al período hasta la fecha de entrega del alumno
                if fecha_entrega:
                    ops = ops[ops['Fecha'].dt.date <= fecha_entrega]

                if tiene_stock_precalc:
                    # Usar el stock precalculado que ya viene en el CSV
                    stocks = pd.to_numeric(ops['A_STOCK_HES'], errors='coerce').fillna(0)
                    min_stock  = int(stocks.min())
                    stock_final = int(stocks.iloc[-1]) if len(stocks) > 0 else 0
                    if min_stock < 0:
                        idx_min = stocks.idxmin()
                        min_fecha = ops.loc[idx_min, 'Fecha']
                        min_ref   = ops.loc[idx_min, 'Referencia']
                    else:
                        min_fecha = min_ref = None
                else:
                    # Calcular el stock acumulado operación a operación
                    stock = 0
                    min_stock = 0
                    min_fecha = None
                    min_ref   = None
                    stock_final = 0

                    for _, op in ops.iterrows():
                        if op['Cantidad'] == 0:
                            continue
                        es_entrada = op['A']     == 'MGZ01/Stock'
                        es_salida  = op['Desde'] == 'MGZ01/Stock'
                        if es_entrada:
                            stock += op['Cantidad']
                        elif es_salida:
                            stock -= op['Cantidad']

                        if stock < min_stock:
                            min_stock = stock
                            min_fecha = op['Fecha']
                            min_ref   = op['Referencia']

                        stock_final = stock

                # Verificar stock negativo
                if min_stock < 0:
                    err(f"Producto {c(producto, Color.YELLOW)}: STOCK NEGATIVO → mínimo: {c(str(min_stock), Color.RED)} (en {min_fecha}, ref: {min_ref})")
                    self._registrar(empresa, 'STOCK_NEGATIVO', f"{producto}: stock mínimo {min_stock} en {min_fecha}")
                    errores_emp += 1
                    stock_negativo_total += 1
                else:
                    ok(f"Producto {producto}: stock mínimo OK ({min_stock}), stock final: {stock_final}")

                # Verificar que stock final del historial coincide con UNITATS REALS del inventario
                inv_prod = inv_emp[inv_emp['PRODUCTE'] == producto]
                if not inv_prod.empty:
                    unidades_reales = inv_prod.iloc[0]['UNITATS REALS']
                    if stock_final != unidades_reales:
                        err(f"Producto {producto}: stock historial ({stock_final}) ≠ UNITATS REALS inventario ({unidades_reales})")
                        self._registrar(empresa, 'STOCK_DISCREPANCIA', f"{producto}: historial {stock_final} vs inventario {unidades_reales}")
                        errores_emp += 1

            if stock_negativo_total == 0:
                ok(f"Sin stocks negativos detectados")
                self._registrar(empresa, 'STOCK', "Sin stocks negativos", 'ok')

            if errores_emp == 0:
                ok(c(f"EMPRESA {empresa}: SIN ERRORES EN INVENTARIO", Color.GREEN + Color.BOLD))
            else:
                err(c(f"EMPRESA {empresa}: {errores_emp} ERROR(ES) EN INVENTARIO", Color.RED + Color.BOLD))


    # ──────────────────────────────────────────────────────────
    # INFORME FINAL
    # ──────────────────────────────────────────────────────────

    def informe_final(self, exportar_csv=True):
        header("INFORME FINAL DE CORRECCIÓN")

        print(f"\n  {c('RESUMEN GLOBAL:', Color.BOLD+Color.WHITE)}")
        print(f"  {c('✓', Color.GREEN)} Verificaciones correctas : {c(str(self.correctos_total), Color.GREEN)}")
        print(f"  {c('⚠', Color.YELLOW)} Avisos                  : {c(str(self.avisos_total), Color.YELLOW)}")
        print(f"  {c('✗', Color.RED)} Errores totales          : {c(str(self.errores_total), Color.RED)}")


        


        subheader("RESUMEN POR ALUMNO")

        # Tabla resumen
        print(f"\n  {'EXPEDIENTE':<12} {'EMPRESA':<35} {'ERR':>5} {'AVI':>5} {'OK':>5}  CALIFICACIÓN")
        print(f"  {'-'*12} {'-'*35} {'-'*5} {'-'*5} {'-'*5}  {'-'*14}")

        filas_csv = []
        for exp, datos in sorted(self.resumen_por_alumno.items()):
            n_err = len(datos['errores'])
            n_avi = len(datos['avisos'])
            n_ok  = len(datos['ok'])
            empresa = datos['empresa'][:35]

            # Nota orientativa (ajustar criterios según necesidad)
            nota_max = 10.0
            descuento_err = 0.5
            descuento_avi = 0.1
            nota = max(0, nota_max - (n_err * descuento_err) - (n_avi * descuento_avi))

            color_nota = Color.GREEN if nota >= 7 else Color.YELLOW if nota >= 5 else Color.RED
            nota_str = c(f"{nota:.1f}/10", color_nota)
            err_str  = c(str(n_err), Color.RED) if n_err > 0 else str(n_err)
            avi_str  = c(str(n_avi), Color.YELLOW) if n_avi > 0 else str(n_avi)

            print(f"  {exp:<12} {empresa:<35} {n_err:>5} {n_avi:>5} {n_ok:>5}  {nota_str}")
            filas_csv.append({'EXPEDIENTE': exp, 'EMPRESA': datos['empresa'],
                              'ERRORES': n_err, 'AVISOS': n_avi, 'OK': n_ok, 'NOTA': round(nota, 1)})

        # Detalle errores por alumno
        subheader("DETALLE DE ERRORES POR ALUMNO")
        for exp, datos in sorted(self.resumen_por_alumno.items()):
            if datos['errores'] or datos['avisos']:
                print(f"\n  {c(exp, Color.BOLD+Color.WHITE)} — {datos['empresa']}")
                for e in datos['errores']:
                    print(f"    {c('✗', Color.RED)} {e}")
                for a in datos['avisos']:
                    print(f"    {c('⚠', Color.YELLOW)} {a}")

        # Exportar CSV
        if exportar_csv and filas_csv:
            ruta_out = self._ruta('INFORME_CORRECCIONES.csv')
            with open(ruta_out, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['EXPEDIENTE','EMPRESA','ERRORES','AVISOS','OK','NOTA'])
                writer.writeheader()
                writer.writerows(filas_csv)
            ok(f"\nInforme exportado a: {c(ruta_out, Color.CYAN)}")

        # Detalle completo por alumno (errores + avisos)
        ruta_det = self._ruta('INFORME_DETALLE.txt')
        with open(ruta_det, 'w', encoding='utf-8') as f:
            f.write("INFORME DETALLADO DE CORRECCIONES - EmpresAula\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*60 + "\n\n")
            for exp, datos in sorted(self.resumen_por_alumno.items()):
                f.write(f"ALUMNO: {datos['empresa']}\n")
                f.write("-"*40 + "\n")
                if datos['errores']:
                    f.write("ERRORES:\n")
                    for e in datos['errores']:
                        f.write(f"  ✗ {e}\n")
                if datos['avisos']:
                    f.write("AVISOS:\n")
                    for a in datos['avisos']:
                        f.write(f"  ⚠ {a}\n")
                if datos['ok']:
                    f.write(f"CORRECTOS: {len(datos['ok'])} verificaciones\n")
                f.write("\n")
        ok(f"Detalle exportado a: {c(ruta_det, Color.CYAN)}")


# ══════════════════════════════════════════════════════════════
# DIAGNÓSTICO
# ══════════════════════════════════════════════════════════════

def diagnostico_columnas(directorio='.'):
    """Muestra las columnas reales de cada CSV para depuración."""
    header("DIAGNÓSTICO DE COLUMNAS CSV")
    archivos = [
        '0_DATOS_COMPRAS_REALES.csv',
        '1_DATOS_PEDIDOS_COMPRA_ALUMNOS.csv',
        '2_DATOS_ALBARANES_COMPRA_ALUMNOS.csv',
        '3_DATOS_FACTURAS_COMPRA_ALUMNOS.csv',
        '4_FECHA_ENTREGA_TRABAJOS.csv',
        '5_DATOS_VENTAS_REALES.csv',
        '6_DATOS_PEDIDOS_VENTA_ALUMNOS.csv',
        '7_DATOS_ALBARANES_VENTA_ALUMNOS.csv',
        '8_DATOS_FACTURAS_VENTA_ALUMNOS.csv',
        '9_DATOS_INVENTARIO_ALUMNO.csv',
        '10_HISTORIAL_E_S_INVENTARIO_ALUMNO.csv',
    ]
    for nombre in archivos:
        ruta = os.path.join(directorio, nombre)
        df = leer_csv(ruta)
        if df is not None:
            print(f"\n  {c(nombre, Color.YELLOW)} ({len(df)} filas)")
            for i, col in enumerate(df.columns):
                print(f"    {c(str(i).rjust(2), Color.GRAY)}  {c(repr(col), Color.CYAN)}")
            if len(df) > 0:
                print(f"  {c('Primera fila (primeras columnas):', Color.GRAY)}")
                for col in list(df.columns)[:6]:
                    print(f"    {col}: {c(str(df.iloc[0][col])[:60], Color.WHITE)}")
        else:
            warn(f"{nombre}: no encontrado en {directorio}")


# ══════════════════════════════════════════════════════════════
# MENÚ INTERACTIVO
# ══════════════════════════════════════════════════════════════

def menu_principal():
    print(c("""
╔══════════════════════════════════════════════════════════════════╗
║         CORRECTOR EMPRESAULA v1.0                               ║
║         Gestión Comercial ODOO · Ciclo Admin y Finanzas         ║
╚══════════════════════════════════════════════════════════════════╝
""", Color.BOLD + Color.BLUE))

    print(f"  {c('1', Color.YELLOW)} → Corrección COMPRAS")
    print(f"  {c('2', Color.YELLOW)} → Corrección VENTAS")
    print(f"  {c('3', Color.YELLOW)} → Corrección INVENTARIO")
    print(f"  {c('4', Color.YELLOW)} → Corrección COMPLETA (todos los módulos)")
    print(f"  {c('5', Color.CYAN)}  → Diagnóstico columnas CSV")
    print(f"  {c('0', Color.GRAY)}  → Salir")
    print()

    opcion = input(c("  Selecciona opción: ", Color.CYAN)).strip()

    if opcion == '0':
        print(c("  Hasta pronto.", Color.GRAY))
        sys.exit(0)

    directorio = input(c("  Directorio con los CSVs [Enter = actual]: ", Color.CYAN)).strip()
    if not directorio:
        directorio = '.'

    if opcion == '5':
        diagnostico_columnas(directorio)
        return

    # Las fechas de entrega individuales se leen de 4_FECHA_ENTREGA_TRABAJOS.csv
    corrector = CorrectorEmpresaula(directorio)

    if opcion == '1':
        corrector.corregir_compras()
    elif opcion == '2':
        corrector.corregir_ventas()
    elif opcion == '3':
        corrector.corregir_inventario()
    elif opcion == '4':
        corrector.corregir_compras()
        # input("⏸ Presiona ENTER para continuar...")  # Bloquea hasta confirmar
        corrector.corregir_ventas()
        # input("⏸ Presiona ENTER para continuar...")  # Bloquea hasta confirmar
        corrector.corregir_inventario()
    else:
        print(c("  Opción no válida.", Color.RED))
        return

    corrector.informe_final()


def main():
    """Punto de entrada. Acepta args o lanza menú interactivo."""
    if len(sys.argv) > 1:
        modulo     = sys.argv[1].lower()
        directorio = sys.argv[2] if len(sys.argv) > 2 else '.'

        if modulo in ('diagnostico', 'diag', 'd', '5'):
            diagnostico_columnas(directorio)
            return

        corrector = CorrectorEmpresaula(directorio)
        if modulo in ('compras', 'c', '1'):
            corrector.corregir_compras()
        elif modulo in ('ventas', 'v', '2'):
            corrector.corregir_ventas()
        elif modulo in ('inventario', 'inv', '3'):
            corrector.corregir_inventario()
        elif modulo in ('todo', 'all', '4'):
            corrector.corregir_compras()
            corrector.corregir_ventas()
            corrector.corregir_inventario()
        else:
            print(f"Módulo desconocido: {modulo}")
            print("Uso: python corrector.py [compras|ventas|inventario|todo|diagnostico] [directorio]")
            return
        corrector.informe_final()
    else:
        menu_principal()


if __name__ == '__main__':
    main()

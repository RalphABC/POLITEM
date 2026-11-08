"""Genera tres cortes mensuales FICTICIOS de una matriz con la forma de la exportación de eSByE (semilla fija)."""
from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "data" / "matrices"
random.seed(2026)

UBICACIONES = {
    "DTIC - UNIDAD DE SOPORTE Y MANTENIMIENTO": ("Equipos informáticos", 44),
    "DTIC - UNIDAD DE REDES Y COMUNICACIONES": ("Redes", 38),
    "DIRECCIÓN ADMINISTRATIVA - BODEGA CENTRAL": ("Mobiliario", 60),
    "UNIDAD DE BIENES Y BODEGAS": ("Oficina", 32),
    "BIBLIOTECA CENTRAL": ("Mobiliario", 55),
    "FACULTAD DE INFORMÁTICA Y ELECTRÓNICA - LAB. 22": ("Laboratorio", 40),
    "FACULTAD DE INFORMÁTICA Y ELECTRÓNICA - DECANATO": ("Oficina", 26),
    "FACULTAD DE MECÁNICA - TALLER DE SOLDADURA": ("Maquinaria", 30),
    "DIRECCIÓN DE TALENTO HUMANO": ("Oficina", 28),
    "SECRETARÍA GENERAL": ("Oficina", 24),
    "EXTENSIÓN MORONA SANTIAGO - BODEGA": ("Mobiliario", 52),
    "AUDITORIO POLITÉCNICO": ("Audiovisual", 22),
}
POOLS = {
    "Equipos informáticos": [("Computador portátil", "Dell", "Latitude 5430", 3, 1100, 1700), ("Computador de escritorio", "HP", "ProDesk 400", 3, 700, 1200),
                             ("Monitor LED 24\"", "Samsung", "S24R350", 3, 150, 260), ("UPS", "APC", "Back-UPS 1500", 3, 200, 420),
                             ("Impresora láser", "HP", "LaserJet M404", 3, 250, 480), ("Disco duro externo", "WD", "Elements 2TB", 3, 70, 110)],
    "Redes": [("Switch administrable 48p", "Cisco", "C9200-48P", 5, 2500, 6200), ("Punto de acceso inalámbrico", "Ubiquiti", "U6-Pro", 5, 150, 260),
              ("Router", "MikroTik", "CCR2004", 5, 700, 1400), ("Servidor rack", "Dell", "PowerEdge R450", 5, 3800, 7800), ("UPS", "APC", "SRT3000", 3, 1500, 2600)],
    "Mobiliario": [("Escritorio metálico", "Pedrosa", "EM-120", 10, 90, 220), ("Silla giratoria", "Pedrosa", "SG-20", 10, 45, 120),
                   ("Archivador metálico 4 gavetas", "Metalex", "AM-4G", 10, 110, 230), ("Estantería metálica", "Metalex", "EST-6N", 10, 90, 200),
                   ("Mesa de reuniones", "Pedrosa", "MR-8", 10, 220, 480)],
    "Oficina": [("Computador de escritorio", "Lenovo", "ThinkCentre M70", 3, 650, 1100), ("Escritorio ejecutivo", "Pedrosa", "EE-160", 10, 180, 420),
                ("Silla ejecutiva", "Pedrosa", "SE-30", 10, 90, 210), ("Impresora multifunción", "Epson", "L6270", 3, 280, 460),
                ("Archivador aéreo", "Metalex", "AA-90", 10, 70, 140), ("Teléfono IP", "Grandstream", "GRP2614", 5, 90, 150)],
    "Laboratorio": [("Osciloscopio digital", "Tektronix", "TBS1052B", 10, 900, 1600), ("Fuente de poder DC", "Rigol", "DP832", 10, 450, 780),
                    ("Computador de escritorio", "HP", "EliteDesk 800", 3, 800, 1300), ("Multímetro de banco", "Keysight", "34461A", 10, 600, 1100),
                    ("Mesa de laboratorio", "Metalex", "ML-180", 10, 250, 520), ("Kit de desarrollo FPGA", "Intel", "DE10-Standard", 5, 300, 520)],
    "Maquinaria": [("Soldadora inversora", "Lincoln", "Invertec V205", 10, 1400, 3400), ("Torno paralelo", "Pinacho", "S90/200", 10, 6500, 14500),
                   ("Compresor de aire", "Campbell", "CA-100", 10, 600, 1400), ("Esmeril de banco", "Bosch", "GB-250", 10, 160, 420)],
    "Audiovisual": [("Proyector", "Epson", "PowerLite X49", 5, 520, 980), ("Parlante activo", "JBL", "EON615", 5, 420, 720),
                    ("Micrófono inalámbrico", "Shure", "SLX24", 5, 380, 720), ("Consola de audio", "Behringer", "X32", 5, 1800, 3200)],
}
NOMBRES = ["Marcelo Velasco", "Luis Orozco", "Patricia Cando", "Fernando Yumbo", "Sandra Paredes", "Diego Guamán", "Verónica Lema",
           "Carlos Chimbo", "Gabriela Naranjo", "Jorge Tenelema", "Rosa Pilco", "Hugo Barriga", "Lorena Sánchez", "Wilson Quishpi"]
TERCEROS = ["Alexandra Montalvo", "Iván Cárdenas", "Silvia Ortega"]


def tasa_mensual(vc: float, vida: float) -> float:
    return vc * 0.90 / (vida * 12)


def dep_a(vc: float, vida: float, ingreso: date, corte: date) -> float:
    meses = max(0, (corte.year - ingreso.year) * 12 + corte.month - ingreso.month)
    return round(min(vc * 0.90, tasa_mensual(vc, vida) * meses), 2)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    custodio_de = {u: random.choice(NOMBRES) for u in UBICACIONES}
    ced = {n: f"99{random.randint(10000000, 99999999)}"[:10] for n in NOMBRES + TERCEROS}
    bienes, n = [], 0
    for ubic, (pool, cant) in UBICACIONES.items():
        for _ in range(cant):
            n += 1
            d, marca, modelo, vida, lo, hi = random.choice(POOLS[pool])
            ing = date(random.randint(2014, 2025), random.randint(1, 12), random.randint(1, 28))
            vc = round(random.uniform(lo, hi), 2)
            cust = custodio_de[ubic] if random.random() < 0.85 else random.choice(NOMBRES)
            bienes.append(dict(codigo=f"ESP-{n:06d}", descripcion=d, marca=marca, modelo=modelo, serie=f"SN{random.randint(10**7, 10**8 - 1)}",
                               tipo="02 Muebles", estado=random.choices(["Bueno", "Regular", "Malo"], [80, 15, 5])[0],
                               condicion="En uso", ubicacion=ubic, sector="ESPOCH Matriz" if "MORONA" not in ubic else "Extensión Morona Santiago",
                               custodio=cust, ingreso=ing, vc=vc, vida=vida))
    cortes = [date(2026, 8, 31), date(2026, 9, 30), date(2026, 10, 23)]
    for k, corte in enumerate(cortes):
        if k > 0:   # movimientos del mes
            for _ in range(5 if k == 1 else 4):
                if len(bienes) > 100:
                    bienes.pop(random.randrange(len(bienes)))
            for b in random.sample(bienes, 10):
                b["custodio"] = random.choice(NOMBRES + TERCEROS)
            for b in random.sample(bienes, 3):
                b["ubicacion"] = random.choice(list(UBICACIONES))
            for b in random.sample(bienes, 2):
                b["estado"] = "Malo"
            for _ in range(12 if k == 1 else 9):
                n += 1
                ubic = random.choice(list(UBICACIONES))
                d, marca, modelo, vida, lo, hi = random.choice(POOLS[UBICACIONES[ubic][0]])
                bienes.append(dict(codigo=f"ESP-{n:06d}", descripcion=d, marca=marca, modelo=modelo, serie=f"SN{random.randint(10**7, 10**8 - 1)}",
                                   tipo="02 Muebles", estado="Bueno", condicion="En uso", ubicacion=ubic, sector="ESPOCH Matriz",
                                   custodio=custodio_de[ubic], ingreso=date(corte.year, corte.month, 1), vc=round(random.uniform(lo, hi), 2), vida=vida))
        ruta = SALIDA / f"matriz_esbye_{corte.isoformat()}.csv"
        with ruta.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Código Bien", "Descripción", "Tipo Bien", "Marca", "Modelo", "Serie", "Estado", "Condición del Bien", "Nombre Bodega", "Sector",
                        "Cédula Custodio", "Custodio Actual", "Fecha Ingreso", "Fecha Última Depreciación", "Valor Contable",
                        "Valor Depreciación Acumulada", "Valor Libros", "Vida Útil"])
            for b in sorted(bienes, key=lambda x: x["codigo"]):
                da = dep_a(b["vc"], b["vida"], b["ingreso"], corte)
                w.writerow([b["codigo"], b["descripcion"], b["tipo"], b["marca"], b["modelo"], b["serie"], b["estado"], b["condicion"],
                            b["ubicacion"], b["sector"], ced[b["custodio"]], b["custodio"], b["ingreso"].isoformat(),
                            corte.replace(day=1).isoformat() if corte.day > 1 else corte.isoformat(), f"{b['vc']:.2f}", f"{da:.2f}",
                            f"{b['vc'] - da:.2f}", b["vida"]])
        print(f"{ruta.name}: {len(bienes)} bienes")


if __name__ == "__main__":
    main()

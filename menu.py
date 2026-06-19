import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError

# Cargar variables de entorno (RNF01)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

def conectar_mongodb():
    try:
        # Se establece un timeout corto para detectar caídas rápidamente (RNF02)
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Fuerza una llamada al servidor para validar la conexión
        client.admin.command('ping')
        print("✅ Conexión exitosa a MongoDB.")
        return client["EcoDrive"]
    except ConnectionFailure:
        print("❌ Error: No se pudo conectar a MongoDB. Verifique su red o URL.")
        return None
    except PyMongoError as e:
        print(f"❌ Error inesperado de MongoDB: {e}")
        return None

db = conectar_mongodb()

def registrar_vehiculo(db):
    print("\n--- Registrar Vehículo ---")
    patente = input("Patente: ").upper()
    marca = input("Marca: ")
    modelo = input("Modelo: ")
    capacidad = float(input("Capacidad de Batería (Ah): "))
    
    vehiculo = {
        "_id": patente,  # Usamos la patente como ID único o dejamos que Mongo genere un ObjectId
        "marca": marca,
        "modelo": modelo,
        "estado_disponibilidad": "Disponible",
        "bateria": {
            "capacidad_ah": capacidad,
            "salud_pct": 100.0,
            "celdas_degradadas": []
        }
    }
    try:
        db.vehiculos.insert_one(vehiculo)
        print("✅ Vehículo registrado con éxito.")
    except PyMongoError as e:
        print(f"❌ Error al registrar: {e}")

def actualizar_disponibilidad(db):
    print("\n--- Actualizar Disponibilidad ---")
    patente = input("Ingrese la patente del vehículo: ").upper()
    nuevo_estado = input("Nuevo estado (Disponible/Mantenimiento/Baja): ")
    
    try:
        resultado = db.vehiculos.update_one(
            {"_id": patente},
            {"$set": {"estado_disponibilidad": nuevo_estado}}
        )
        if resultado.modified_count > 0:
            print("✅ Estado actualizado correctamente.")
        else:
            print("⚠️ No se realizaron cambios (vehículo no encontrado o mismo estado).")
    except PyMongoError as e:
        print(f"❌ Error al actualizar: {e}")
    
def buscar_baterias_degradadas(db):
    try:
        limite_salud = float(input("Buscar vehículos con salud de batería menor a (%): "))
        
        # Uso de notación de puntos y operador relacional $lt
        query = {"bateria.salud_pct": {"$lt": limite_salud}}
        vehiculos = db.vehiculos.find(query)
        
        print(f"\n--- Vehículos con batería < {limite_salida}% ---")
        for v in vehiculos:
            print(f"Patente: {v['_id']} | Modelo: {v['modelo']} | Salud: {v['bateria']['salud_pct']}%")
    except ValueError:
        print("❌ Por favor, ingrese un número válido.")

def buscar_mantenimiento_por_fallo(db):
    palabra_clave = input("Ingrese término de fallo a buscar (ej: fren, bater): ")
    
    # Uso de expresiones regulares
    query = {"descripcion_fallo": {"$regex": palabra_clave, "$options": "i"}}
    mantenimientos = db.mantenimientos.find(query)
    
    print("\n--- Historial de Mantenimientos Encontrados ---")
    for m in mantenimientos:
        print(f"Fecha: {m['fecha']} | Vehículo: {m['vehiculo_id']} | Fallo: {m['descripcion_fallo']} | Costo: ${m['costo']}")

def filtrar_alertas_criticas(db):
    # Condición 1: Severidad Crítica Y Voltaje fuera de rango (> 400V o < 320V como ejemplo)
    # Condición 2: O que pertenezca a una lista de patentes específicas bajo observación
    patentes_observadas = ["ABCD12", "XYZW34", "EEEE99"]
    
    query = {
        "$or": [
            {
                "$and": [
                    {"severidad": "Crítica"},
                    {"$or": [{"voltaje": {"$gt": 400}}, {"voltaje": {"$lt": 320}}]}
                ]
            },
            {"patente": {"$in": patentes_observadas}}
        ]
    }
    
    alertas = db.alertas_telemetria.find(query)
    print("\n--- Alertas de Telemetría Filtradas ---")
    for a in alertas:
        print(f"ID: {a['_id']} | Vehículo: {a['patente']} | Severidad: {a['severidad']} | Voltaje: {a.get('voltaje', 'N/A')}")

def generar_reporte_consumo(db):
    print("\n--- Reporte Consolidado de Consumo Energético ---")
    anio_mes = input("Ingrese el año y mes a consultar (YYYY-MM): ") # Ej: "2026-06"
    
    pipeline = [
        # 1. Filtrar viajes del mes específico usando Regex sobre el string de fecha
        {
            "$match": {
                "fecha": {"$regex": f"^{anio_mes}"}
            }
        },
        # 2. Cruzar con la colección 'vehiculos' para obtener detalles del modelo
        {
            "$lookup": {
                "from": "vehiculos",
                "localField": "vehiculo_id",  # ID del vehículo en la colección 'viajes'
                "foreignField": "_id",         # Patente en la colección 'vehiculos'
                "as": "detalle_vehiculo"
            }
        },
        # 3. Descomponer el arreglo resultante del lookup
        {
            "$unwind": "$detalle_vehiculo"
        },
        # 4. Agrupar por el modelo del vehículo y calcular el promedio de consumo
        {
            "$group": {
                "_id": "$detalle_vehiculo.modelo",
                "promedio_consumo_kw": {"$avg": "$consumo_energetico"},
                "total_viajes": {"$sum": 1}
            }
        },
        # 5. Ordenar por mayor consumo promedio
        {
            "$sort": {"promedio_consumo_kw": -1}
        }
    ]
    
    try:
        resultados = db.viajes.aggregate(pipeline)
        print(f"\nResultados para el periodo {anio_mes}:")
        print("-" * 50)
        for res in resultados:
            print(f"Modelo: {res['_id']:<15} | Consumo Promedio: {res['promedio_consumo_kw']:.2f} kWh | Viajes: {res['total_viajes']}")
    except PyMongoError as e:
        print(f"❌ Error al procesar el reporte de agregación: {e}")

def menu():
    if db is None:
        print("⚠️ No se puede iniciar la aplicación sin conexión a la base de datos.")
        return

    while True:
        print("\n================ ECODRIVE SYSTEM ================")
        print("1. Registrar Vehículo (RF01)")
        print("2. Actualizar Estado de Disponibilidad (RF01)")
        print("3. Buscar Vehículos por Salud de Batería (RF02)")
        print("4. Buscar Mantenimientos por Coincidencia de Fallo (RF03)")
        print("5. Filtrar Alertas Críticas de Telemetría (RF04)")
        print("6. Reporte: Promedio Consumo por Modelo (RF05)")
        print("7. Salir")
        print("=================================================")
        
        opcion = input("Seleccione una opción: ")
        
        if opcion == "1":
            registrar_vehiculo(db)
        elif opcion == "2":
            actualizar_disponibilidad(db)
        elif opcion == "3":
            buscar_baterias_degradadas(db)
        elif opcion == "4":
            buscar_mantenimiento_por_fallo(db)
        elif opcion == "5":
            filtrar_alertas_criticas(db)
        elif opcion == "6":
            generar_reporte_consumo(db)
        elif opcion == "7":
            print("👋 Saliendo del sistema EcoDrive. ¡Buen viaje!")
            break
        else:
            print("❌ Opción inválida, intente nuevamente.")

if __name__ == "__main__":
    menu()


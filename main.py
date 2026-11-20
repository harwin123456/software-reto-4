from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
import logging
import re


# ==================================================
# REGISTRO DE EVENTOS Y ERRORES (ARCHIVO .LOG)
# ==================================================

# Creamos un "diario" para anotar qué pasa y qué errores ocurren.
logger = logging.getLogger("software_Fj")
logger.setLevel(logging.INFO)

if not logger.handlers:
    archivo = logging.FileHandler(
        "software_Fj.log",
        encoding="utf-8"
    )
    archivo.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    logger.addHandler(archivo)


# ==================================================
# ERRORES PERSONALIZADOS
# ==================================================

# Definir nuestras propias clases de error ayuda a saber qué falló exactamente.
class ErrorSistema(Exception):
    pass


class ErrorValidacion(ErrorSistema):
    pass


class ErrorDuplicado(ErrorSistema):
    pass


class ErrorDisponibilidad(ErrorSistema):
    pass


class ErrorReserva(ErrorSistema):
    pass


class ErrorCalculo(ErrorSistema):
    pass


# ==================================================
# FUNCIONES DE VALIDACIÓN
# ==================================================

def texto(valor, campo):
    # Verifica que el dato sea texto y no quede vacío o solo con espacios.
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion(
            f"{campo}: debe ser un texto no vacío."
        )
    return valor.strip()


def numero(valor, campo, minimo=Decimal("0"), estricto=False):
    # Usamos Decimal (en vez de float) para evitar errores de redondeo con dinero.
    try:
        if isinstance(valor, bool):
            raise ValueError("No se aceptan booleanos.")

        resultado = Decimal(str(valor))

        if not resultado.is_finite():
            raise ValueError("El número debe ser finito.")

    except (InvalidOperation, ValueError, TypeError) as error:
        raise ErrorValidacion(
            f"{campo}: número inválido."
        ) from error

    if resultado < minimo or (estricto and resultado == minimo):
        operador = "mayor que" if estricto else "mayor o igual que"
        raise ErrorValidacion(
            f"{campo}: debe ser {operador} {minimo}."
        )

    return resultado


def entero_positivo(valor, campo):
    # Verifica que sea un número entero exacto y mayor que 0.
    if type(valor) is not int or valor <= 0:
        raise ErrorValidacion(
            f"{campo}: debe ser un entero positivo."
        )
    return valor


# ==================================================
# CLASE ABSTRACTA GENERAL
# ==================================================

class Entidad(ABC):
    # Molde base para clientes, servicios y reservas.
    def __init__(self, identificador):
        self.__identificador = texto(identificador, "Identificador")

    @property
    def identificador(self):
        return self.__identificador

    @abstractmethod
    def describir(self):
        pass


# ==================================================
# CLIENTE
# ==================================================

class Cliente(Entidad):
    def __init__(self, identificador, nombre, correo, telefono):
        super().__init__(identificador)

        nombre = texto(nombre, "Nombre")
        correo = texto(correo, "Correo")
        telefono = texto(telefono, "Teléfono")

        if len(nombre) < 3:
            raise ErrorValidacion(
                "El nombre debe tener mínimo tres caracteres."
            )

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
            raise ErrorValidacion(
                "El formato del correo no es válido."
            )

        if not re.fullmatch(r"\d{7,15}", telefono):
            raise ErrorValidacion(
                "El teléfono debe tener entre 7 y 15 dígitos."
            )

        self.__nombre = nombre
        self.__correo = correo
        self.__telefono = telefono

    @property
    def nombre(self):
        return self.__nombre

    @property
    def correo(self):
        return self.__correo

    @property
    def telefono(self):
        return self.__telefono

    def describir(self):
        return f"Cliente {self.identificador}: {self.nombre}"


# ==================================================
# SERVICIO GENERAL (CLASE ABSTRACTA)
# ==================================================

class Servicio(Entidad):
    def __init__(self, identificador, nombre, tarifa):
        super().__init__(identificador)

        self.__nombre = texto(nombre, "Nombre del servicio")
        self.__tarifa = numero(tarifa, "Tarifa", estricto=True)

    @property
    def nombre(self):
        return self.__nombre

    @property
    def tarifa(self):
        return self.__tarifa

    @abstractmethod
    def validar_parametros(self, duracion):
        pass

    @abstractmethod
    def calcular_base(self, duracion):
        pass

    @abstractmethod
    def describir(self):
        pass

    # Los valores por defecto en impuesto y descuento permiten usarlo con o sin ellos.
    def calcular_costo(self, duracion, impuesto=0, descuento=0):
        try:
            horas = numero(duracion, "Duración", estricto=True)
            tasa = numero(impuesto, "Impuesto")
            rebaja = numero(descuento, "Descuento")

            if tasa > 1 or rebaja > 1:
                raise ErrorValidacion(
                    "Impuesto y descuento deben estar entre 0 y 1."
                )

            self.validar_parametros(horas)
            base = self.calcular_base(horas)

            if not base.is_finite() or base < 0:
                raise ErrorCalculo(
                    "El costo base no es válido."
                )

            # Corrección: multiplicamos por (1 - rebaja) y luego por (1 + tasa).
            total = (
                base
                * (Decimal("1") - rebaja)
                * (Decimal("1") + tasa)
            )

            return total.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        except ErrorSistema:
            raise

        except (ArithmeticError, TypeError, ValueError) as error:
            raise ErrorCalculo(
                "No se pudo calcular el costo."
            ) from error


# ==================================================
# TIPOS DE SERVICIOS (HERENCIA Y POLIMORFISMO)
# ==================================================

class Sala(Servicio):
    def __init__(self, identificador, nombre, tarifa, capacidad):
        super().__init__(identificador, nombre, tarifa)
        self.__capacidad = entero_positivo(capacidad, "Capacidad")

    def validar_parametros(self, duracion):
        if duracion > 12:
            raise ErrorValidacion(
                "La sala se puede reservar máximo 12 horas."
            )

    def calcular_base(self, duracion):
        return self.tarifa * duracion

    def describir(self):
        return (
            f"Sala: {self.nombre} | "
            f"Capacidad: {self.__capacidad} | "
            f"Tarifa por hora: ${self.tarifa:,.2f}"
        )


class Equipo(Servicio):
    def __init__(self, identificador, nombre, tarifa, seguro):
        super().__init__(identificador, nombre, tarifa)
        self.__seguro = numero(seguro, "Seguro")

    def validar_parametros(self, duracion):
        if duracion > 72:
            raise ErrorValidacion(
                "El equipo se puede alquilar máximo 72 horas."
            )

    def calcular_base(self, duracion):
        return self.tarifa * duracion + self.__seguro

    def describir(self):
        return (
            f"Equipo: {self.nombre} | "
            f"Tarifa por hora: ${self.tarifa:,.2f} | "
            f"Seguro: ${self.__seguro:,.2f}"
        )


class Asesoria(Servicio):
    def __init__(self, identificador, nombre, tarifa, especialidad):
        super().__init__(identificador, nombre, tarifa)
        self.__especialidad = texto(especialidad, "Especialidad")

    def validar_parametros(self, duracion):
        if duracion < 1 or duracion > 8:
            raise ErrorValidacion(
                "La asesoría debe durar entre 1 y 8 horas."
            )

    def calcular_base(self, duracion):
        return self.tarifa * duracion

    def describir(self):
        return (
            f"Asesoría: {self.nombre} | "
            f"Especialidad: {self.__especialidad} | "
            f"Tarifa por hora: ${self.tarifa:,.2f}"
        )


# ==================================================
# ESTADOS DE LA RESERVA
# ==================================================

# Enum evita escribir estados a mano con riesgo de errores tipográficos.
class EstadoReserva(Enum):
    PENDIENTE = "Pendiente"
    CONFIRMADA = "Confirmada"
    PROCESADA = "Procesada"
    CANCELADA = "Cancelada"


# ==================================================
# RESERVA
# ==================================================

class Reserva(Entidad):
    def __init__(self, identificador, cliente, servicio, duracion):
        super().__init__(identificador)

        if not isinstance(cliente, Cliente):
            raise ErrorValidacion("El cliente no es válido.")

        if not isinstance(servicio, Servicio):
            raise ErrorValidacion("El servicio no es válido.")

        horas = numero(duracion, "Duración", estricto=True)
        servicio.validar_parametros(horas)

        self.__cliente = cliente
        self.__servicio = servicio
        self.__duracion = horas
        self.__estado = EstadoReserva.PENDIENTE
        self.__total = None

    @property
    def servicio(self):
        return self.__servicio

    @property
    def estado(self):
        return self.__estado

    @property
    def total(self):
        return self.__total

    def confirmar(self, reservas):
        if self.estado != EstadoReserva.PENDIENTE:
            raise ErrorReserva(
                "Solo se puede confirmar una reserva pendiente."
            )

        ocupado = any(
            reserva is not self
            and reserva.servicio.identificador
            == self.servicio.identificador
            and reserva.estado == EstadoReserva.CONFIRMADA
            for reserva in reservas
        )

        if ocupado:
            raise ErrorDisponibilidad(
                "El servicio ya tiene una reserva confirmada."
            )

        self.__estado = EstadoReserva.CONFIRMADA
        logger.info("Reserva %s confirmada", self.identificador)

    def cancelar(self):
        if self.estado not in (
            EstadoReserva.PENDIENTE,
            EstadoReserva.CONFIRMADA
        ):
            raise ErrorReserva(
                "No se puede cancelar una reserva "
                "procesada o ya cancelada."
            )

        self.__estado = EstadoReserva.CANCELADA
        logger.info("Reserva %s cancelada", self.identificador)

    def procesar(self, impuesto=0, descuento=0):
        try:
            if self.estado != EstadoReserva.CONFIRMADA:
                raise ErrorReserva(
                    "La reserva debe estar confirmada."
                )

            total = self.servicio.calcular_costo(
                self.__duracion,
                impuesto=impuesto,
                descuento=descuento
            )

        except ErrorSistema as error:
            # "from error" encadena este error con el error original.
            raise ErrorReserva(
                f"No se pudo procesar la reserva "
                f"{self.identificador}: {error}"
            ) from error

        else:
            # Se ejecuta solo si no hubo errores en try.
            self.__total = total
            self.__estado = EstadoReserva.PROCESADA

            logger.info(
                "Reserva %s procesada por %s",
                self.identificador,
                total
            )
            return total

        finally:
            # Se ejecuta siempre, haya error o no.
            logger.info(
                "Terminó el intento de procesar %s",
                self.identificador
            )

    def describir(self):
        return (
            f"Reserva {self.identificador} | "
            f"Cliente: {self.__cliente.nombre} | "
            f"Servicio: {self.servicio.nombre} | "
            f"Horas: {self.__duracion} | "
            f"Estado: {self.estado.value} | "
            f"Total: {self.total}"
        )


# ==================================================
# ADMINISTRACIÓN DEL SISTEMA (EN MEMORIA, SIN BD)
# ==================================================

class Sistema:
    def __init__(self):
        self.__clientes = []
        self.__servicios = []
        self.__reservas = []

    @property
    def clientes(self):
        return tuple(self.__clientes)

    @property
    def servicios(self):
        return tuple(self.__servicios)

    @property
    def reservas(self):
        return tuple(self.__reservas)

    def __agregar(self, lista, objeto, tipo):
        if not isinstance(objeto, tipo):
            raise ErrorValidacion(
                f"Se esperaba un objeto de tipo {tipo.__name__}."
            )

        if any(
            elemento.identificador == objeto.identificador
            for elemento in lista
        ):
            raise ErrorDuplicado(
                f"El identificador {objeto.identificador} ya existe."
            )

        lista.append(objeto)
        logger.info(
            "%s registrado: %s",
            tipo.__name__,
            objeto.identificador
        )
        return objeto

    def registrar_cliente(self, cliente):
        return self.__agregar(self.__clientes, cliente, Cliente)

    def registrar_servicio(self, servicio):
        return self.__agregar(self.__servicios, servicio, Servicio)

    def buscar_cliente(self, identificador):
        for cliente in self.__clientes:
            if cliente.identificador == identificador:
                return cliente
        raise ErrorValidacion(f"No existe el cliente {identificador}.")

    def buscar_servicio(self, identificador):
        for servicio in self.__servicios:
            if servicio.identificador == identificador:
                return servicio
        raise ErrorValidacion(f"No existe el servicio {identificador}.")

    def buscar_reserva(self, identificador):
        for reserva in self.__reservas:
            if reserva.identificador == identificador:
                return reserva
        raise ErrorReserva(f"No existe la reserva {identificador}.")

    def crear_reserva(self, identificador, id_cliente, id_servicio, duracion):
        cliente = self.buscar_cliente(id_cliente)
        servicio = self.buscar_servicio(id_servicio)
        reserva = Reserva(identificador, cliente, servicio, duracion)
        return self.__agregar(self.__reservas, reserva, Reserva)

    def confirmar_reserva(self, identificador):
        reserva = self.buscar_reserva(identificador)
        reserva.confirmar(self.__reservas)


# ==================================================
# CONTROL DE OPERACIONES Y SIMULACIÓN
# ==================================================

def ejecutar_operacion(numero_operacion, descripcion, accion):
    print(f"\n{numero_operacion:02d}. {descripcion}")

    try:
        resultado = accion()

    except ErrorSistema as error:
        logger.exception(
            "Error en operación %s: %s",
            numero_operacion,
            descripcion
        )
        print(f"   ERROR CONTROLADO: {error}")
        return False

    except Exception as error:
        logger.exception(
            "Error inesperado en operación %s: %s",
            numero_operacion,
            descripcion
        )
        print(f"   ERROR CONTROLADO: {type(error).__name__}: {error}")
        return False

    else:
        logger.info(
            "Operación %s completada: %s",
            numero_operacion,
            descripcion
        )
        print("   OPERACIÓN EXITOSA")
        if isinstance(resultado, Entidad):
            print(f"   {resultado.describir()}")
        elif resultado is not None:
            print(f"   Resultado: {resultado}")
        return True

    finally:
        logger.info("Finalizó la operación %s", numero_operacion)


def main():
    sistema = Sistema()

    operaciones = [
        (
            "Registrar cliente válido",
            lambda: sistema.registrar_cliente(
                Cliente("C01", "Ana Pérez", "ana@correo.com", "3001234567")
            )
        ),
        (
            "Registrar cliente con correo inválido",
            lambda: sistema.registrar_cliente(
                Cliente("C02", "Luis Gómez", "correo-invalido", "3011234567")
            )
        ),
        (
            "Registrar otro cliente válido",
            lambda: sistema.registrar_cliente(
                Cliente("C02", "Luis Gómez", "luis@correo.com", "3011234567")
            )
        ),
        (
            "Intentar registrar cliente duplicado",
            lambda: sistema.registrar_cliente(
                Cliente("C01", "Ana Pérez", "ana@correo.com", "3001234567")
            )
        ),
        (
            "Crear sala válida",
            lambda: sistema.registrar_servicio(
                Sala("S01", "Sala de reuniones", 50000, 12)
            )
        ),
        (
            "Crear equipo válido",
            lambda: sistema.registrar_servicio(
                Equipo("S02", "Proyector", 20000, 10000)
            )
        ),
        (
            "Crear asesoría válida",
            lambda: sistema.registrar_servicio(
                Asesoria("S03", "Asesoría de software", 80000, "Programación")
            )
        ),
        (
            "Intentar crear servicio con tarifa negativa",
            lambda: sistema.registrar_servicio(
                Sala("S04", "Sala inválida", -100, 10)
            )
        ),
        (
            "Intentar crear cliente con datos faltantes",
            lambda: Cliente("C03", "Carlos")
        ),
        (
            "Crear reserva de sala",
            lambda: sistema.crear_reserva("R01", "C01", "S01", 2)
        ),
        (
            "Confirmar reserva R01",
            lambda: sistema.confirmar_reserva("R01")
        ),
        (
            "Crear otra reserva para la misma sala",
            lambda: sistema.crear_reserva("R02", "C02", "S01", 3)
        ),
        (
            "Intentar confirmar un servicio ocupado",
            lambda: sistema.confirmar_reserva("R02")
        ),
        (
            "Intentar reservar con duración negativa",
            lambda: sistema.crear_reserva("R03", "C01", "S02", -2)
        ),
        (
            "Intentar reservar con cliente inexistente",
            lambda: sistema.crear_reserva("R04", "C99", "S02", 2)
        ),
        (
            "Intentar procesar con descuento inválido",
            lambda: sistema.buscar_reserva("R01").procesar(descuento="1.50")
        ),
        (
            "Procesar R01 con impuesto y descuento",
            lambda: sistema.buscar_reserva("R01").procesar(
                impuesto="0.19",
                descuento="0.10"
            )
        ),
        (
            "Intentar cancelar una reserva procesada",
            lambda: sistema.buscar_reserva("R01").cancelar()
        ),
        (
            "Confirmar R02 con la sala disponible",
            lambda: sistema.confirmar_reserva("R02")
        ),
        (
            "Cancelar R02",
            lambda: sistema.buscar_reserva("R02").cancelar()
        ),
        (
            "Crear reserva de equipo",
            lambda: sistema.crear_reserva("R05", "C02", "S02", 4)
        ),
        (
            "Confirmar reserva de equipo",
            lambda: sistema.confirmar_reserva("R05")
        ),
        (
            "Procesar reserva de equipo",
            lambda: sistema.buscar_reserva("R05").procesar()
        ),
        (
            "Calcular asesoría sin ajustes",
            lambda: sistema.buscar_servicio("S03").calcular_costo(2)
        ),
        (
            "Calcular asesoría con impuesto",
            lambda: sistema.buscar_servicio("S03").calcular_costo(2, impuesto="0.19")
        ),
        (
            "Calcular asesoría con impuesto y descuento",
            lambda: sistema.buscar_servicio("S03").calcular_costo(
                2,
                impuesto="0.19",
                descuento="0.10"
            )
        ),
    ]

    resultados = []

    print("=" * 65)
    print("SOFTWARE RETO 4 - SISTEMA DE RESERVAS")
    print("Empresa: Software FJ")
    print("=" * 65)

    for indice, (descripcion, accion) in enumerate(operaciones, start=1):
        resultado = ejecutar_operacion(indice, descripcion, accion)
        resultados.append(resultado)

    print("\nSERVICIOS REGISTRADOS")
    for servicio in sistema.servicios:
        print(servicio.describir())

    print("\nESTADO FINAL DE LAS RESERVAS")
    for reserva in sistema.reservas:
        print(reserva.describir())

    exitosas = sum(resultados)
    fallidas = len(resultados) - exitosas

    print("\nRESUMEN")
    print(f"Operaciones ejecutadas: {len(resultados)}")
    print(f"Operaciones exitosas: {exitosas}")
    print(f"Errores controlados: {fallidas}")
    print(f"Clientes registrados: {len(sistema.clientes)}")
    print(f"Servicios registrados: {len(sistema.servicios)}")
    print(f"Reservas registradas: {len(sistema.reservas)}")
    print("Archivo de registro: software_reto_4.log")

    logger.info(
        "Simulación finalizada: %s exitosas y %s fallidas",
        exitosas,
        fallidas
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        logging.shutdown()
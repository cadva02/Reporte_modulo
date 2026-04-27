"""Clases de movimiento para controlar desplazamientos en 2D.

Este modulo define movimientos basicos que pueden usarse desde la interfaz
(PyQt5 u otra) para actualizar la posicion de un robot o cursor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Posicion:
    """Representa una posicion en el plano cartesiano."""

    x: int
    y: int


class Movimiento(ABC):
    """Contrato base para cualquier movimiento."""

    @abstractmethod
    def ejecutar(self, posicion: Posicion) -> Posicion:
        """Recibe una posicion y retorna la nueva posicion."""


class Izquierda(Movimiento):
    def ejecutar(self, posicion: Posicion) -> Posicion:
        return Posicion(posicion.x - 1, posicion.y)


class Derecha(Movimiento):
    def ejecutar(self, posicion: Posicion) -> Posicion:
        return Posicion(posicion.x + 1, posicion.y)


class Arriba(Movimiento):
    def ejecutar(self, posicion: Posicion) -> Posicion:
        return Posicion(posicion.x, posicion.y + 1)


class Abajo(Movimiento):
    def ejecutar(self, posicion: Posicion) -> Posicion:
        return Posicion(posicion.x, posicion.y - 1)

"""Async Modbus/TCP client for WAGO 750-8212 PFC200."""

from __future__ import annotations

import asyncio
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT


class WagoCommunicationError(Exception):
    """Raised when Modbus communication fails."""


class WagoModbusClient:
    """Serialize and expose Modbus/TCP access to a WAGO controller."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        reconnect_delay: float,
        unit_id: int,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.unit_id = unit_id
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=timeout,
            reconnect_delay=reconnect_delay,
        )

    @property
    def connected(self) -> bool:
        return bool(self._client.connected)

    async def async_connect(self) -> None:
        try:
            connected = await self._client.connect()
        except (OSError, ModbusException) as err:
            raise WagoCommunicationError(str(err)) from err
        if not connected:
            raise WagoCommunicationError(
                f"Unable to connect to {self.host}:{self.port}"
            )

    async def async_close(self) -> None:
        self._client.close()

    async def _ensure_connected(self) -> None:
        if not self._client.connected:
            await self.async_connect()

    @staticmethod
    def _check(response: Any, operation: str) -> Any:
        if response is None or response.isError():
            raise WagoCommunicationError(f"Modbus error while {operation}: {response!r}")
        return response

    async def _read_bits_chunk(self, table: str, address: int, count: int) -> list[bool]:
        method = (
            self._client.read_coils if table == TABLE_COIL else self._client.read_discrete_inputs
        )
        response = await method(address, count=count, device_id=self.unit_id)
        self._check(response, f"reading {table} {address}:{count}")
        return [bool(value) for value in response.bits[:count]]

    async def _read_registers_chunk(
        self, table: str, address: int, count: int
    ) -> list[int]:
        method = (
            self._client.read_holding_registers
            if table == TABLE_HOLDING
            else self._client.read_input_registers
        )
        response = await method(address, count=count, device_id=self.unit_id)
        self._check(response, f"reading {table} {address}:{count}")
        return [int(value) for value in response.registers]

    async def _read_table(self, table: str, start: int, size: int) -> dict[int, Any]:
        if size <= 0:
            return {}
        max_chunk = 2000 if table in (TABLE_COIL, TABLE_DISCRETE) else 125
        result: dict[int, Any] = {}
        offset = 0
        while offset < size:
            count = min(max_chunk, size - offset)
            address = start + offset
            if table in (TABLE_COIL, TABLE_DISCRETE):
                values = await self._read_bits_chunk(table, address, count)
            else:
                values = await self._read_registers_chunk(table, address, count)
            result.update({address + idx: value for idx, value in enumerate(values)})
            offset += count
        return result

    async def async_read_all(self, memory: dict[str, tuple[int, int]]) -> dict[str, dict[int, Any]]:
        async with self._lock:
            await self._ensure_connected()
            try:
                data: dict[str, dict[int, Any]] = {}
                for table in (TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT):
                    start, size = memory[table]
                    data[table] = await self._read_table(table, start, size)
                return data
            except (OSError, ModbusException) as err:
                raise WagoCommunicationError(str(err)) from err

    async def async_write_coil(self, address: int, value: bool) -> None:
        async with self._lock:
            await self._ensure_connected()
            try:
                response = await self._client.write_coil(
                    address, bool(value), device_id=self.unit_id
                )
            except (OSError, ModbusException) as err:
                raise WagoCommunicationError(str(err)) from err
            self._check(response, f"writing coil {address}")

    async def async_write_registers(self, address: int, values: list[int]) -> None:
        async with self._lock:
            await self._ensure_connected()
            try:
                if len(values) == 1:
                    response = await self._client.write_register(
                        address, values[0], device_id=self.unit_id
                    )
                else:
                    response = await self._client.write_registers(
                        address, values, device_id=self.unit_id
                    )
            except (OSError, ModbusException) as err:
                raise WagoCommunicationError(str(err)) from err
            self._check(response, f"writing holding register {address}")

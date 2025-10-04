from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


# --------------------------
# RS485 Bus Manager
# --------------------------
class RS485Bus:
    def __init__(self, port="/dev/ttyS0", baudrate=4800, parity="N", stopbits=1, timeout=1):
        self.client = ModbusSerialClient(
            method="rtu",
            port=port,
            baudrate=baudrate,
            stopbits=stopbits,
            bytesize=8,
            parity=parity,
            timeout=timeout
        )
        if not self.client.connect():
            raise Exception(f"Konnte RS485 Verbindung auf {port} nicht herstellen")

    def close(self):
        self.client.close()


# --------------------------
# CWT-TH01S Temp/Hum Sensor
# --------------------------
class CWT_TH01S:
    """
    Beispielklasse für Temp/Hum Sensor CWT-TH01S (Modbus RTU).
    """
    def __init__(self, bus, slave_id=1):
        self.bus = bus
        self.id = slave_id

    def read(self):
        try:
            rr = self.bus.client.read_input_registers(0x0000, 2, unit=self.id)
            if rr.isError():
                print(f"Fehler beim Lesen CWT-TH01S {self.id}: {rr}")
                return None
            regs = rr.registers
            return {
                "temperature": regs[0] / 10.0,  # °C
                "humidity": regs[1] / 10.0      # %RH
            }
        except ModbusException as e:
            print(f"Modbus Exception CWT-TH01S {self.id}: {e}")
            return None


# --------------------------
# Halisense Soil Sensor (TH-EC-PH-NPK)
# --------------------------
class SoilSensorTH_EC_PH_NPK:
    def __init__(self, bus, slave_id=1):
        self.bus = bus
        self.id = slave_id

    def read_all(self):
        try:
            rr = self.bus.client.read_holding_registers(
                address=0x0000,
                count=7,
                unit=self.id
            )
            if rr.isError():
                print(f"Fehler beim Lesen Soil Sensor {self.id}: {rr}")
                return None

            regs = rr.registers
            return {
                "humidity": regs[0] / 10.0,        # %RH
                "temperature": regs[1] / 10.0,     # °C
                "ec": regs[2],                     # µS/cm
                "ph": regs[3] / 10.0,              # pH
                "nitrogen": regs[4],               # mg/kg
                "phosphorus": regs[5],             # mg/kg
                "potassium": regs[6],              # mg/kg
            }

        except ModbusException as e:
            print(f"Modbus Exception Soil Sensor {self.id}: {e}")
            return None

    def set_slave_id(self, new_id):
        try:
            rq = self.bus.client.write_register(0x07D0, new_id, unit=self.id)
            if rq.isError():
                print(f"Fehler beim Setzen Slave ID {self.id}->{new_id}")
                return False
            self.id = new_id
            return True
        except ModbusException as e:
            print(f"Modbus Exception beim Setzen Slave ID: {e}")
            return False


# --------------------------
# Beispielmain
# --------------------------
if __name__ == "__main__":
    # RS485 Bus starten
    bus = RS485Bus(port="/dev/ttyS0", baudrate=4800)

    # Sensoren am Bus (IDs musst du entsprechend konfigurieren!)
    th01_1 = CWT_TH01S(bus, slave_id=1)
    th01_2 = CWT_TH01S(bus, slave_id=2)
    th01_3 = CWT_TH01S(bus, slave_id=3)

    soil = SoilSensorTH_EC_PH_NPK(bus, slave_id=4)

    # Abfragen
    print("Sensor 1 (CWT-TH01S):", th01_1.read())
    print("Sensor 2 (CWT-TH01S):", th01_2.read())
    print("Sensor 3 (CWT-TH01S):", th01_3.read())
    print("Soil Sensor:", soil.read_all())

    # Bus schließen
    bus.close()

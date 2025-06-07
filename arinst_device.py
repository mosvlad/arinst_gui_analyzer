from serial import Serial
import serial.tools.list_ports
import platform
import time

class ArinstCommand:
    GENERATOR_ON = "gon"
    GENERATOR_OFF = "gof"
    GENERATOR_SET_FREQUENCY = "scf"
    GENERATOR_SET_AMPLITUDE = "sga"
    SCAN_RANGE = "scn20"
    SCAN_RANGE_TRACKING = "scn22"

class ArinstDevice:
    def __init__(self, device=None, baudrate=115200, timeout=1.0):
        if device is None:
            device = self._find_device()
        
        self.__serial = Serial(port=device, baudrate=baudrate, timeout=timeout)
        self.__command_terminate = '\r\n'
        self.__package_index = 0
        self.__command_count_terminate = {
            ArinstCommand.GENERATOR_ON: 2,
            ArinstCommand.GENERATOR_OFF: 2,
            ArinstCommand.GENERATOR_SET_FREQUENCY: 3,
            ArinstCommand.GENERATOR_SET_AMPLITUDE: 2,
            ArinstCommand.SCAN_RANGE: 4,
            ArinstCommand.SCAN_RANGE_TRACKING: 4
        }

    def _find_device(self):
        """Automatically find Arinst device on Windows/Linux"""
        ports = serial.tools.list_ports.comports()
        
        # For Windows, look for common COM ports
        if platform.system() == "Windows":
            # Try common COM ports first
            for port in ports:
                if "USB" in port.description or "Serial" in port.description:
                    return port.device
            # If no USB device found, return the first available port
            if ports:
                return ports[0].device
            else:
                raise Exception("No serial ports found")
        else:
            # Linux/Unix default
            return '/dev/ttyACM0'

    @staticmethod
    def list_available_ports():
        """List all available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [(port.device, port.description) for port in ports]

    def is_connected(self):
        """Check if device is connected"""
        return self.__serial.is_open if hasattr(self.__serial, 'is_open') else True

    def _write(self, command: str, *args):
        msg = command + "".join([f' {arg}' for arg in args]) + " " + str(self.__package_index) + self.__command_terminate
        self.__serial.write(bytes(msg, 'ascii'))
        self.__package_index += 1

    def _read(self, command: str) -> bytes:
        msg = b''
        for _ in range(self.__command_count_terminate[command]):
            msg += self.__serial.read_until(bytes(self.__command_terminate, 'ascii'))

        self.__serial.reset_input_buffer()
        self.__serial.reset_output_buffer()
        return msg

    def send_command(self, command: str, *args):
        self._write(command, *args)
        response = self._read(command)
        response = response.split(bytes(self.__command_terminate, 'ascii'))
        try:
            while True:
                response.pop(response.index(b''))
        except ValueError:
            pass
        response = [resp.split(b' ') for resp in response]
        return response

    def on(self) -> bool:
        command = ArinstCommand.GENERATOR_ON
        response = self.send_command(command)
        return response[-1][0] == b"complete" and str(response[0][0], 'ascii') == command

    def off(self) -> bool:
        command = ArinstCommand.GENERATOR_OFF
        response = self.send_command(command)
        return response[-1][0] == b"complete" and str(response[0][0], 'ascii') == command

    def set_frequency(self, frequency: int) -> bool:
        command = ArinstCommand.GENERATOR_SET_FREQUENCY
        response = self.send_command(command, frequency)
        if len(response) == 3:
            return response[-1][0] == b"complete" and str(response[0][0], 'ascii') == command and str(response[1][0], 'ascii') == "success"
        else:
            return False
        
    def set_amplitude(self, amplitude: int) -> bool:
        if -25 <= amplitude <= -15:
            command = ArinstCommand.GENERATOR_SET_AMPLITUDE
            amplitude = ((amplitude + 15) * 100) + 10000
            response = self.send_command(command, amplitude)
            return response[-1][0] == b"complete" and str(response[0][0], 'ascii') == command
        else:
            return False

    def __decode_data(self, response, attenuation):
        amplitudes = []
        # Debug: print raw response length and first few bytes
        print(f"Debug: Raw response length: {len(response)} bytes")
        print(f"Debug: First 20 bytes: {response[:20]}")
        
        for i in range(0, len(response), 2):
            if i + 1 < len(response):  # Fixed: should be i+1, not i+2
                first = int.from_bytes(response[i:i + 1], byteorder='little')
                second = int.from_bytes(response[i + 1:i + 2], byteorder='little')  # Fixed: i+1 to i+2
                val = first << 8 | second
                data = val & 0b0000011111111111
                amplitude = (800.0 - data)/10.0 - attenuation/100.0
                amplitudes.append(amplitude)
        
        print(f"Debug: Decoded {len(amplitudes)} amplitude points")
        print(f"Debug: Sample amplitudes: {amplitudes[:5]}")
        return amplitudes

    def get_scan_range(self, start=1500000000, stop=1700000000, step=1000000, attenuation=0, tracking=False):
        # Validate parameters
        if not (1000000 <= start <= 6000000000):
            print(f"Debug: Invalid start frequency: {start} Hz (must be 1MHz - 6GHz)")
            return None
            
        if not (1000000 <= stop <= 6000000000):
            print(f"Debug: Invalid stop frequency: {stop} Hz (must be 1MHz - 6GHz)")
            return None
            
        if start >= stop:
            print(f"Debug: Start frequency must be less than stop frequency")
            return None
            
        if step < 1000:
            print(f"Debug: Step size too small: {step} Hz (minimum 1000 Hz)")
            return None
            
        if step > (stop - start):
            print(f"Debug: Step size too large: {step} Hz (max {stop - start} Hz)")
            return None
            
        # Calculate number of scan points
        num_points = int((stop - start) / step) + 1
        max_points = 2000  # Reasonable limit for Arinst device
        
        if num_points > max_points:
            print(f"Debug: Too many scan points: {num_points} (max {max_points})")
            print(f"Debug: Try larger step size or smaller frequency range")
            return None
            
        print(f"Debug: Scan will have {num_points} points")
        
        if -30 <= attenuation <= 0:
            command = None
            if tracking:
                command = ArinstCommand.SCAN_RANGE_TRACKING
            else:
                command = ArinstCommand.SCAN_RANGE
            attenuation_param = (attenuation * 100) + 10000
            
            print(f"Debug: Sending scan command - Start: {start} Hz, Stop: {stop} Hz, Step: {step} Hz")
            response = self.send_command(command, start, stop, step, 200, 20, 10700000, attenuation_param)
            
            print(f"Debug: Got response with {len(response)} parts")
            for i, part in enumerate(response):
                print(f"Debug: Response part {i}: {part}")
            
            if len(response) >= 3:
                if response[-1][0] == b"complete" and str(response[0][0], 'ascii') == command:
                    print(f"Debug: Command successful, decoding data from response[1][0]")
                    print(f"Debug: Raw data length: {len(response[1][0])} bytes")
                    return self.__decode_data(response[1][0][0:-2], attenuation)
                else:
                    print(f"Debug: Command failed - response[-1][0]: {response[-1][0]}, response[0][0]: {response[0][0]}")
            else:
                print(f"Debug: Insufficient response parts: {len(response)}")
        else:
            print(f"Debug: Invalid attenuation: {attenuation}")
        return None

    def close(self):
        """Close the serial connection"""
        if self.__serial.is_open:
            self.__serial.close()

    def __del__(self):
        """Destructor to ensure serial connection is closed"""
        try:
            self.close()
        except:
            pass 
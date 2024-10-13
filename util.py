class Int4:
    def __init__(self, value=0):
        # enforce 4-bit range
        # 0xF (15) masks the lowest 4 bits
        self.value = value & 0xF

    def __repr__(self):
        return f"{self.value:0{4}b}"

    def __int__(self):
        return self.value

    def set_value(self, value):
        # Set the value while enforcing 4-bit range
        self.value = value & 0xF

    def to_int(self):
        # Convert the 4-bit value to an integer
        return self.value[0]

    def to_bytes(self):
        # Convert the 4-bit value to a single byte
        return bytes([int(self.value)])

    # Overriding arithmetic operators
    def __add__(self, other):
        return Int4((self.value + int(other)) & 0xF)

    def __sub__(self, other):
        return Int4((self.value - int(other)) & 0xF)

    def __and__(self, other):
        return Int4(self.value & int(other))

    def __or__(self, other):
        return Int4(self.value | int(other))

    def __xor__(self, other):
        return Int4(self.value ^ int(other))

    # Other bitwise operations
    def __lshift__(self, bits):
        return Int4((self.value << bits) & 0xF)

    def __rshift__(self, bits):
        return Int4(self.value >> bits)

    # Comparison operators
    def __eq__(self, other):
        return self.value == int(other)

    def __ne__(self, other):
        return not self.__eq__(other)
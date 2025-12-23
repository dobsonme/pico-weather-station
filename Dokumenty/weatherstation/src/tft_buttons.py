"""
input pins for ws_pico_2
"""

from machine import Pin

class Buttons():
    """
    Buttons class for examples, modify for your device.

    Attributes:
        name (str): The name of the device.
        left (Pin): The Pin object representing the left button.
        right (Pin): The Pin object representing the right button.
        fire (Pin): The Pin object representing the fire button.
        thrust (Pin): The Pin object representing the thrust button.
        hyper (Pin): The Pin object representing the hyper button.
    """

    def __init__(self):
        self.name = "ws_pico_2"
        self.key0 = Pin(15, Pin.IN, Pin.PULL_UP)    # Top Right
        self.key1 = Pin(17, Pin.IN, Pin.PULL_UP)    # Bottom Right
        self.key2 = Pin(2, Pin.IN, Pin.PULL_UP)     # Bottom Left
        self.key3 = Pin(3, Pin.IN, Pin.PULL_UP)     # Top Left

        # for roids.py in landscape mode

        self.left = self.key2 #top left
        self.right = self.key3 #top right
        self.fire = self.key1
        self.thrust = self.key0
        self.hyper = None
        
    def check_buttons(self, ssid, password):
        """
        Funkcja sprawdzająca naciśnięcie przycisków.
        Naciśnięcie key0 łączy z WiFi, key1 resetuje WiFi.
        """
        if not self.key0.value():  # Jeśli przycisk key0 jest naciśnięty
            print("Przycisk naciśnięty. Próba połączenia z WiFi...")
            if connect_wifi(ssid, password):
                print("Połączenie z WiFi zakończone sukcesem.")
            else:
                print("Połączenie z WiFi nie powiodło się.")
        
        if not self.key1.value():  # Jeśli przycisk key1 jest naciśnięty
            print("Przycisk key1 naciśnięty. Resetowanie WiFi...")
            reset_wifi()  # Resetowanie WiFi
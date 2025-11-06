from gpiozero import LED
import time

# GPIO pin mapping (update based on your actual wiring)
left_imag = LED(17)   # Left arm imagery
left_move = LED(27)   # Left arm actual
fault_led = LED(22)   # Fault detector
right_move = LED(23)  # Right arm actual
right_imag = LED(24)  # Right arm imagery

leds = [left_imag, left_move, fault_led, right_move, right_imag]
labels = ["Left Imagery", "Left Actual", "Fault", "Right Actual", "Right Imagery"]

print("Starting LED test sequence. Press Ctrl+C to stop.\n")

try:
    while True:
        for led, name in zip(leds, labels):
            print(f"→ {name} ON")
            led.on()
            time.sleep(1)
            led.off()
            print(f"   {name} OFF\n")
        print("Cycle complete.\n")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("Test stopped by user. Turning all LEDs off...")
    for led in leds:
        led.off()
    print("All LEDs OFF.")

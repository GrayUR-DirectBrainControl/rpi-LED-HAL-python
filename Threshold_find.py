import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, WindowOperations, DetrendOperations 
from datetime import datetime #saving data with timestamps
import csv  #For csv writing
import os       #For file path operations
import keyboard  # For keypress detection 
from gpiozero import LED #For GPIO LED control
import numpy as np #For numerical operations(mean and std)



'''
Remeber to enter virtual environment if running via RPI : 
Run in terminal: 
 To activate: source ~/repos/rpi-LED-HAL-python/venv/bin/activate
 To deactivate: deactivate
'''

def add_csv_to_path(base="Band_Powers",out_dir="Recordings"):     
    #Create 'data/bands_YYYY-MM-DD_HH-MM-SS.csv'..  
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{base}_{ts}.csv")


def get_band_powers(data, sampling_rate, channel, nfft):
    DataFilter.detrend(data[channel], DetrendOperations.LINEAR.value)
    psd = DataFilter.get_psd_welch(
    data[channel],       # EEG data from one channel (1D numpy array)
    nfft,                # Number of FFT points (length of window)
    nfft // 2,           # Overlap between segments (50%)
    sampling_rate,       # Sampling rate of your EEG board (e.g., 250 Hz)
    WindowOperations.BLACKMAN_HARRIS.value  # Window function to apply to each segment
    )
    '''
    Using welch method, which is bascially just a more stable version of a raw FFT,
    it averages the fft and applies a window function(BLACKMAN HARRIS). 
    '''
    alpha = DataFilter.get_band_power(psd, 8.0, 13.0) 
    beta = DataFilter.get_band_power(psd, 13.0, 30.0) 
    gamma = DataFilter.get_band_power(psd, 30.0, 50.0) 

    return alpha, beta, gamma

def relative(a, b, g):
    tot = a + b + g
    if tot == 0:
        return 0.0, 0.0, 0.0
    return a/tot, b/tot, g/tot


def main():
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)

    params = BrainFlowInputParams()
    params.serial_port = '/dev/ttyUSB0'
    # PC = 'COMX'(X is a number i.e 3 - find in device manager(windows)) ; RPI = '/dev/ttyUSB0' 
    board_id = BoardIds.CYTON_BOARD.value  

    sampling_rate = BoardShim.get_sampling_rate(board_id)
    nfft = DataFilter.get_nearest_power_of_two(sampling_rate)

    board = BoardShim(board_id, params)

    #CSV setup (timestamped filename, single 'data/' dir)
    bands_csv_path = add_csv_to_path(base="Band_Powers", out_dir="Recordings")
    bands_csv = open(bands_csv_path, mode='w', newline='')
    bands_writer = csv.writer(bands_csv)
    bands_writer.writerow(['Timestamp','Alpha_L','Beta_L','Gamma_L','Alpha_R','Beta_R','Gamma_R',
                'AlphaL_rel','BetaL_rel','GammaL_rel','AlphaR_rel','BetaR_rel','GammaR_rel','Marker'])  # header
    print(f"Writing EEG band data to: {bands_csv_path}")

    # GPIO setup
    left_imag  = LED(17)
    left_move  = LED(27)
    right_imag = LED(24)
    right_move = LED(23)
    fault_led  = LED(22) 

    try:
        board.prepare_session()
        board.start_stream()
        print("Reading EEG data... Press Ctrl+C to stop.\n")

        eeg_channels = BoardShim.get_eeg_channels(board_id)

        #target_channel = eeg_channels[2]  # Only one EEG channel for simplicity - Using C3(right hand movement)
        #check for drops in alpha and beta band power.
        #Channel 2 = NP3 on the cyton boards

        c3_channel = eeg_channels[2]  # C3 Right hand motor cortex
        c4_channel = eeg_channels[3]  # C4 Left hand motor cortex

        #Pre-session baseline calibration
        print("\nBaseline calibration starting soon.")
        print("Play 10 Hz relaxation tone when countdown begins (eyes closed recommended).")
        time.sleep(3)
        for i in range(10, 0, -1):
            print(f"Calibrating... {i}s remaining")
            time.sleep(1)

        baseline_samples = []
        t0 = time.time()
        while time.time() - t0 < 10:
            data = board.get_current_board_data(sampling_rate * 2)
            if data.shape[1] < sampling_rate:
                time.sleep(0.5)
                continue
            aL, bL, gL = get_band_powers(data, sampling_rate, c4_channel, nfft)
            aR, bR, gR = get_band_powers(data, sampling_rate, c3_channel, nfft)
            alphaL_rel, betaL_rel, gammaL_rel = [x / (aL+bL+gL) if (aL+bL+gL)!=0 else 0 for x in [aL,bL,gL]]
            alphaR_rel, betaR_rel, gammaR_rel = [x / (aR+bR+gR) if (aR+bR+gR)!=0 else 0 for x in [aR,bR,gR]]
            baseline_samples.append([alphaL_rel, betaL_rel, gammaL_rel, alphaR_rel, betaR_rel, gammaR_rel])
            time.sleep(1)

        baseline = np.array(baseline_samples)
        mean_vals = np.mean(baseline, axis=0)
        std_vals  = np.std(baseline, axis=0)

        mean_alphaL, mean_betaL, mean_gammaL, mean_alphaR, mean_betaR, mean_gammaR = mean_vals
        std_alphaL, std_betaL, std_gammaL, std_alphaR, std_betaR, std_gammaR = std_vals

        TH_ALPHA_DROP = std_alphaL  # same magnitude for both sides(**Pending confirmation**)
        TH_BETA_RISE  = std_betaL
        TH_GAMMA_HIGH = mean_gammaL + 1.5 * std_gammaL

        print(f"Calibration complete.")
        print(f"Thresholds = Alpha: {TH_ALPHA_DROP:.3f}, Beta: {TH_BETA_RISE:.3f}, Gamma: {TH_GAMMA_HIGH:.3f}\n")
        # End baseline calibration

        event_num = 1  # Marker index
        while True:
            time.sleep(1)  # Wait 1 second for full window
            data = board.get_current_board_data(sampling_rate * 2)

            if data.shape[1] < sampling_rate:
                continue

            '''
            alpha, beta, gamma = get_band_powers(data, sampling_rate, target_channel, nfft)
            print(f"Alpha: {alpha:.2f} | Beta: {beta:.2f} | Gamma: {gamma:.2f}")

            Remove all statements below and uncomment the above line
            to see the raw values of alpha, beta and gamma.
            '''

            #alpha, beta, gamma = get_band_powers(data, sampling_rate, target_channel, nfft)
             # Get bands for left and right
            alpha_L, beta_L, gamma_L = get_band_powers(data, sampling_rate, c4_channel, nfft)
            alpha_R, beta_R, gamma_R = get_band_powers(data, sampling_rate, c3_channel, nfft)

            total_L = alpha_L + beta_L + gamma_L
            total_R = alpha_R + beta_R + gamma_R

            # Fault detection: no valid data
            # if total_L == 0 or total_R == 0:
            #     fault_led.on() 
            #     print("Fault: no valid EEG data.")
            #     continue
            # else:
            #     fault_led.off()

            # Fault Detection Logic 
            if total_L == 0 or total_R == 0:        # Lower fault: no valid data
                fault_led.on()
                print("Fault: no valid EEG data.")
                continue
            elif total_L < 1e-6 or total_R < 1e-6:  # Lower fault: extremely low power (basically noise floor)
                fault_led.on()
                print("Fault: EEG data too low.")
                continue
            elif total_L > 1200 or total_R > 1200:  # Upper fault: impossible EEG value (artifact / hardware issue)
                fault_led.on()
                print("Fault: EEG power excessively high (artifact/hardware issue).")
                continue
            else:
                fault_led.off()


            alphaL_rel = alpha_L / total_L
            betaL_rel = beta_L / total_L
            gammaL_rel = gamma_L / total_L

            alphaR_rel = alpha_R / total_R
            betaR_rel = beta_R / total_R
            gammaR_rel = gamma_R / total_R

            # Right Hand (C4)
            alpha_drop_L = alphaL_rel < (mean_alphaL - TH_ALPHA_DROP)
            beta_rise_L = betaL_rel > (mean_betaL + TH_BETA_RISE)
            gamma_rise_L = gammaL_rel > TH_GAMMA_HIGH

            # left hand(C3)
            alpha_drop_R = alphaR_rel < (mean_alphaR - TH_ALPHA_DROP)
            beta_rise_R = betaR_rel > (mean_betaR + TH_BETA_RISE)
            gamma_rise_R = gammaR_rel > TH_GAMMA_HIGH

            #LED Logic 
            #**Look into adding tug-of-war style control where one hand movement can cancel the other i.e only the stronger LED lights up**
            # Right hand detection (C4 activity)
            if alpha_drop_L and beta_rise_L and not gamma_rise_L:
                right_imag.on()
                right_move.off()
                print("Right-hand imagery detected.")
            elif alpha_drop_L and beta_rise_L and gamma_rise_L:
                right_move.on()
                right_imag.off()
                print("Right-hand movement detected.")
            else:
                right_imag.off()
                right_move.off()

            # Left hand detection (C3 activity)
            if alpha_drop_R and beta_rise_R and not gamma_rise_R:
                left_imag.on()
                left_move.off()
                print("Left-hand imagery detected.")
            elif alpha_drop_R and beta_rise_R and gamma_rise_R:
                left_move.on()
                left_imag.off()
                print("Left-hand movement detected.")
            else:
                left_imag.off()
                left_move.off()

            # Print values
            print(f"L: Alpha={alphaL_rel:.3f} | Beta={betaL_rel:.3f} | Gamma={gammaL_rel:.3f} | "
                  f"R: Alpha={alphaR_rel:.3f} | Beta={betaR_rel:.3f} | Gamma={gammaR_rel:.3f}")

            #print(f"Alpha: {alpha_rel:.3f} | Beta: {beta_rel:.3f} | Gamma: {gamma_rel:.3f} (Relative Powers)")


            # Save to CSV with timestamp
            ts = datetime.now().isoformat(timespec="seconds") 

            marker = ""
            if keyboard.is_pressed("space"):
                marker = f"EVENT_{event_num}"
                print(f"Marker added at {ts}")
                event_num += 1
                time.sleep(0.3)  # debounce to avoid duplicates

            bands_writer.writerow([
                ts,
                f"{alpha_L:.3f}", f"{beta_L:.3f}", f"{gamma_L:.3f}",
                f"{alpha_R:.3f}", f"{beta_R:.3f}", f"{gamma_R:.3f}",
                f"{alphaL_rel:.3f}", f"{betaL_rel:.3f}", f"{gammaL_rel:.3f}",
                f"{alphaR_rel:.3f}", f"{betaR_rel:.3f}", f"{gammaR_rel:.3f}",
                marker
            ])

             #Save files in a dedicated folder with timestamped filenames

            bands_csv.flush() # Ensure data is written to file

        

    except KeyboardInterrupt:   #Ctrl + C to stop
        print("\nStopped by user.")
    finally:
        board.stop_stream()
        board.release_session()
        bands_csv.flush()
        bands_csv.close()
        left_imag.off(); left_move.off(); right_imag.off(); right_move.off(); fault_led.off()
        print("Session released. All LEDs off.")

if __name__ == '__main__':
    main()

import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, WindowOperations, DetrendOperations 

'''
Remeber to enter virtual environment if running via RPI : 
Run in terminal: 
 To activate: source ~/repos/rpi-LED-HAL-python/venv/bin/activate
 To deactivate: deactivate
'''


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

    try:
        board.prepare_session()
        board.start_stream()
        print("Reading EEG data... Press Ctrl+C to stop.\n")

        eeg_channels = BoardShim.get_eeg_channels(board_id)
        target_channel = eeg_channels[2]  # Only one EEG channel for simplicity - Using C3(right hand movement)
        #Channel 2 = NP3 on the cyton boards

        #c3_channel = eeg_channels[2]  # C3 Right hand movement
        #c4_channel = eeg_channels[3]  # C4 Left hand movement

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

            alpha, beta, gamma = get_band_powers(data, sampling_rate, target_channel, nfft)

            total_power = alpha + beta + gamma

            # Prevent division by zero
            if total_power == 0:
                alpha_rel = beta_rel = gamma_rel = 0.0
            else:
                alpha_rel = alpha / total_power
                beta_rel = beta / total_power
                gamma_rel = gamma / total_power

            print(f"Alpha: {alpha_rel:.3f} | Beta: {beta_rel:.3f} | Gamma: {gamma_rel:.3f} (Relative Powers)")


    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        board.stop_stream()
        board.release_session()
        print("Session released.")

if __name__ == '__main__':
    main()

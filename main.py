# test_brainflow.py
<<<<<<< HEAD
from brainflow.board_shim
import BoardShim, BrainFlowInputParams, BoardIds
=======
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
>>>>>>> 7af493a098d9722683cebbe6ca444830c7fe62dc

BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
board = BoardShim(BoardIds.SYNTHETIC_BOARD, params)
board.prepare_session()
board.start_stream()
print("Streaming from synthetic board!")
board.stop_stream()
board.release_session()
